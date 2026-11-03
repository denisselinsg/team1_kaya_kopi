"""API budget tracker for the team's OpenAI key (Workstream D, docs/budget.md).

Library use: route every LLM call through ``tracked_chat`` / ``tracked_embeddings``.
They refuse calls that would cross the hard stop and log tokens, latency and an
estimated cost to ``logs/api_usage.jsonl`` (git-ignored, no prompts or responses).

CLI use (all output is JSON; exit 0 ok, 1 warning, 2 hard stop / rule failure):
    python -m agent.budget_tracker check-key
    python -m agent.budget_tracker status
    python -m agent.budget_tracker reconcile --verified-spend 3.42 --source "OpenAI usage dashboard"
    python -m agent.budget_tracker demo-cost [--request-id req-xxxx] [--record]
    python -m agent.budget_tracker checkpoints [--apply]
    python -m agent.budget_tracker init --hard-budget 50 --currency USD \
        --period-start 2026-10-31 --period-end 2026-11-21

Estimates are never treated as provider-confirmed: only ``reconcile`` records a
verified figure, read by a human from the OpenAI usage dashboard.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://api.openai.com/v1"
KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
PURPOSE_PATTERN = re.compile(r"^[a-z0-9_\-]{1,40}$")
# Rough per-image token allowance used only for the pre-call budget check.
IMAGE_TOKEN_ESTIMATE = 1500
USAGE_FIELDS = {
    "type", "request_id", "ts", "model", "purpose", "status", "input_tokens",
    "cached_input_tokens", "output_tokens", "latency_ms", "cost", "currency",
}
CHECKPOINT_ITEMS = [
    {"id": "week2_api_spend", "file": "CHECKPOINTS.md", "mode": "tick",
     "item": "API spend checked against budget"},
    {"id": "harness_weekly_spend", "file": "HARNESS_CHECKLIST.md", "mode": "tick",
     "item": "You track cumulative spend against your team's API budget \u2014 weekly at minimum."},
    {"id": "harness_request_logging", "file": "HARNESS_CHECKLIST.md", "mode": "report",
     "item": "Every request logs its tool calls, latency, and token usage."},
]

log = logging.getLogger("budget_tracker")


class BudgetError(RuntimeError):
    pass


class BudgetExceeded(BudgetError):
    pass


@dataclass(frozen=True)
class Paths:
    root: Path = REPO_ROOT

    @property
    def config(self) -> Path:
        return self.root / "agent" / "budget_config.json"

    @property
    def records(self) -> Path:
        return self.root / "agent" / "budget_records.json"

    @property
    def ledger(self) -> Path:
        return self.root / "logs" / "api_usage.jsonl"

    @property
    def budget_doc(self) -> Path:
        return self.root / "docs" / "budget.md"

    @property
    def env(self) -> Path:
        return self.root / ".env"


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------- storage

def load_config(paths: Paths) -> dict:
    if not paths.config.exists():
        raise BudgetError(f"Missing {paths.config.name}; run the init command first")
    return json.loads(paths.config.read_text(encoding="utf-8"))


def load_records(paths: Paths) -> dict:
    if not paths.records.exists():
        return {"reviews": [], "demo_requests": []}
    data = json.loads(paths.records.read_text(encoding="utf-8"))
    data.setdefault("reviews", [])
    data.setdefault("demo_requests", [])
    return data


def load_ledger(paths: Paths) -> list[dict]:
    if not paths.ledger.exists():
        return []
    entries = []
    for line in paths.ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _read_text(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _check_safe_text(value: str, field: str, max_len: int = 120) -> str:
    value = value.strip()
    if not value or len(value) > max_len:
        raise BudgetError(f"{field} must be 1-{max_len} characters")
    if KEY_PATTERN.search(value):
        raise BudgetError(f"{field} looks like it contains an API key; refusing to store it")
    return value


def append_ledger(paths: Paths, entry: dict) -> None:
    unknown = set(entry) - USAGE_FIELDS
    if unknown:
        raise BudgetError(f"Ledger entry has non-allow-listed fields: {sorted(unknown)}")
    for key, value in entry.items():
        if isinstance(value, str) and KEY_PATTERN.search(value):
            raise BudgetError(f"Ledger field '{key}' looks like an API key; refusing to store it")
    paths.ledger.parent.mkdir(parents=True, exist_ok=True)
    with paths.ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def get_api_key(paths: Paths) -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key and paths.env.exists():
        for line in paths.env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise BudgetError("OPENAI_API_KEY is not set in the environment or .env")
    return key


# ---------------------------------------------------------------- pricing

def price_for(config: dict, model: str) -> dict | None:
    models = config["pricing"]["models"]
    matches = [name for name in models if model == name or model.startswith(name + "-")]
    return models[max(matches, key=len)] if matches else None


def compute_cost(rates: dict, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    uncached = max(input_tokens - cached_tokens, 0)
    cost = (uncached * rates["input"] + cached_tokens * rates.get("cached_input", rates["input"])
            + output_tokens * rates["output"]) / 1_000_000
    return round(cost, 8)


def _estimate_input_tokens(messages) -> int:
    chars = images = 0
    for message in messages if isinstance(messages, list) else [messages]:
        content = message.get("content", "") if isinstance(message, dict) else message
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    chars += len(part)
                elif part.get("type") in ("image_url", "input_image"):
                    images += 1
                else:
                    chars += len(str(part.get("text", "")))
    return chars // 4 + 1 + images * IMAGE_TOKEN_ESTIMATE


# ---------------------------------------------------------------- spend

def spend_summary(config: dict, records: dict, ledger: list[dict]) -> dict:
    usage = [e for e in ledger if e.get("type") == "usage"]
    estimated = sum(e["cost"] for e in usage)
    reviews = sorted(records["reviews"], key=lambda r: r["recorded_at"])
    last = reviews[-1] if reviews else None
    effective = estimated
    if last:
        reviewed_at = _parse_ts(last["recorded_at"])
        since = sum(e["cost"] for e in usage if _parse_ts(e["ts"]) > reviewed_at)
        effective = max(estimated, last["verified_cumulative"] + since)
    budget = config["hard_budget"]
    by_purpose: dict[str, float] = {}
    by_model: dict[str, float] = {}
    for entry in usage:
        by_purpose[entry["purpose"]] = by_purpose.get(entry["purpose"], 0) + entry["cost"]
        by_model[entry["model"]] = by_model.get(entry["model"], 0) + entry["cost"]
    return {
        "estimated_cumulative": round(estimated, 6),
        "verified_cumulative": last["verified_cumulative"] if last else None,
        "last_reconciled": last["date"] if last else None,
        "discrepancy": last["discrepancy"] if last else None,
        "effective_cumulative": round(effective, 6),
        "basis": "verified + estimated since review" if last else "estimated only",
        "remaining": round(budget - effective, 6),
        "pct_used": round(effective / budget * 100, 2),
        "requests": len(usage),
        "failed_requests": sum(1 for e in usage if e.get("status") != "ok"),
        "input_tokens": sum(e["input_tokens"] for e in usage),
        "output_tokens": sum(e["output_tokens"] for e in usage),
        "by_purpose": {k: round(v, 6) for k, v in sorted(by_purpose.items())},
        "by_model": {k: round(v, 6) for k, v in sorted(by_model.items())},
    }


def threshold_state(config: dict, fraction_used: float) -> dict:
    crossed = [t for t in config["warn_thresholds"] if fraction_used >= t]
    if fraction_used >= config["hard_stop"]:
        state = "hard_stop"
    elif crossed:
        state = "warning"
    else:
        state = "ok"
    return {"warn": config["warn_thresholds"], "hard_stop": config["hard_stop"],
            "crossed": crossed, "state": state}


# ---------------------------------------------------------------- tracked calls

def _default_client(paths: Paths):
    from openai import OpenAI

    return OpenAI(api_key=get_api_key(paths))


def _preflight(paths: Paths, config: dict, client, model: str, purpose: str,
               est_input: int, est_output: int) -> tuple[dict, dict]:
    if not PURPOSE_PATTERN.match(purpose):
        raise BudgetError("purpose must be a short slug such as 'ocr', 'agent' or 'eval'")
    rates = price_for(config, model)
    if rates is None:
        raise BudgetError(f"No price configured for model '{model}'; add it to agent/budget_config.json")
    base_url = str(getattr(client, "base_url", DEFAULT_BASE_URL)).rstrip("/")
    if base_url not in config["allowed_base_urls"]:
        raise BudgetError("Client endpoint is not the class-provided OpenAI endpoint")
    summary = spend_summary(config, load_records(paths), load_ledger(paths))
    projected = compute_cost(rates, est_input, 0, est_output)
    limit = config["hard_stop"] * config["hard_budget"]
    if summary["effective_cumulative"] + projected >= limit:
        raise BudgetExceeded(
            f"Call refused: spend {summary['effective_cumulative']:.4f} + projected "
            f"{projected:.4f} {config['currency']} would reach the hard stop of "
            f"{limit:.2f} {config['currency']}")
    return rates, summary


def _record(paths: Paths, config: dict, before: dict, *, model: str, purpose: str, rates: dict,
            input_tokens: int, cached: int, output_tokens: int, latency_ms: int, status: str) -> dict:
    entry = {
        "type": "usage",
        "request_id": f"req-{uuid.uuid4().hex[:12]}",
        "ts": _now().isoformat(timespec="seconds"),
        "model": model,
        "purpose": purpose,
        "status": status,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost": compute_cost(rates, input_tokens, cached, output_tokens),
        "currency": config["currency"],
    }
    append_ledger(paths, entry)
    after = (before["effective_cumulative"] + entry["cost"]) / config["hard_budget"]
    previous = before["effective_cumulative"] / config["hard_budget"]
    for threshold in config["warn_thresholds"]:
        if previous < threshold <= after:
            log.warning("API budget warning: %.0f%% of %.2f %s used",
                        after * 100, config["hard_budget"], config["currency"])
    return entry


def _usage_tokens(usage) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    return input_tokens, cached, output_tokens


def tracked_chat(messages: list, *, model: str, purpose: str, client=None,
                 max_output_tokens: int | None = None, paths: Paths = Paths(), **kwargs):
    """Budget-checked chat completion. Returns ``(response, usage_entry)``."""
    if kwargs.get("stream"):
        raise BudgetError("Streaming is not supported by tracked_chat; usage would not be recorded")
    config = load_config(paths)
    client = client or _default_client(paths)
    max_out = max_output_tokens or config["default_max_output_tokens"]
    rates, before = _preflight(paths, config, client, model, purpose,
                               _estimate_input_tokens(messages), max_out)
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, max_completion_tokens=max_out, **kwargs)
    except Exception:
        _record(paths, config, before, model=model, purpose=purpose, rates=rates, input_tokens=0,
                cached=0, output_tokens=0, status="error",
                latency_ms=int((time.perf_counter() - started) * 1000))
        raise
    input_tokens, cached, output_tokens = _usage_tokens(getattr(response, "usage", None))
    entry = _record(paths, config, before, model=model, purpose=purpose, rates=rates,
                    input_tokens=input_tokens, cached=cached, output_tokens=output_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000), status="ok")
    return response, entry


def tracked_embeddings(inputs, *, model: str, purpose: str, client=None, paths: Paths = Paths()):
    """Budget-checked embeddings call. Returns ``(response, usage_entry)``."""
    config = load_config(paths)
    client = client or _default_client(paths)
    items = inputs if isinstance(inputs, list) else [inputs]
    rates, before = _preflight(paths, config, client, model, purpose,
                               sum(len(str(i)) for i in items) // 4 + 1, 0)
    started = time.perf_counter()
    try:
        response = client.embeddings.create(model=model, input=inputs)
    except Exception:
        _record(paths, config, before, model=model, purpose=purpose, rates=rates, input_tokens=0,
                cached=0, output_tokens=0, status="error",
                latency_ms=int((time.perf_counter() - started) * 1000))
        raise
    input_tokens, _, _ = _usage_tokens(getattr(response, "usage", None))
    entry = _record(paths, config, before, model=model, purpose=purpose, rates=rates,
                    input_tokens=input_tokens, cached=0, output_tokens=0,
                    latency_ms=int((time.perf_counter() - started) * 1000), status="ok")
    return response, entry


# ---------------------------------------------------------------- key check

def check_key(paths: Paths, opener=urllib.request.urlopen, timeout: float = 10) -> dict:
    """Validate the key via the free GET /v1/models endpoint. Never returns the key."""
    request = urllib.request.Request(
        f"{DEFAULT_BASE_URL}/models", headers={"Authorization": f"Bearer {get_api_key(paths)}"})
    try:
        with opener(request, timeout=timeout) as response:
            models = [m.get("id", "") for m in json.loads(response.read()).get("data", [])]
    except urllib.error.HTTPError as exc:
        reason = "key rejected" if exc.code in (401, 403) else "provider error"
        return {"valid": False if exc.code in (401, 403) else None,
                "http_status": exc.code, "detail": reason}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"valid": None, "http_status": None, "detail": f"network error ({type(exc).__name__})"}
    config = load_config(paths)
    priced = sorted(m for m in models if price_for(config, m) is not None)
    return {"valid": True, "http_status": 200, "models_visible": len(models),
            "priced_models_visible": len(priced),
            "detail": "key accepted; listing models is free and does not affect spend"}


# ---------------------------------------------------------------- rules

def _rule(rule_id: str, rule: str, status: str, detail: str) -> dict:
    return {"id": rule_id, "rule": rule, "status": status, "detail": detail}


def _secret_leaks(paths: Paths) -> list[str]:
    try:
        key = get_api_key(paths)
    except BudgetError:
        key = ""
    leaks = []
    for path in (paths.ledger, paths.records, paths.config, paths.budget_doc):
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if KEY_PATTERN.search(text) or (key and key in text):
                leaks.append(path.relative_to(paths.root).as_posix())
    return leaks


def evaluate_rules(paths: Paths, config: dict, records: dict, ledger: list[dict],
                   summary: dict, today: date) -> list[dict]:
    rules = []
    usage = [e for e in ledger if e.get("type") == "usage"]

    leaks = _secret_leaks(paths)
    bad_fields = [e.get("request_id", "?") for e in usage if set(e) - USAGE_FIELDS]
    if leaks or bad_fields:
        rules.append(_rule("R1", "No keys, account IDs or request/response content stored", "fail",
                           f"key-like text in {leaks}; non-allow-listed fields in {len(bad_fields)} entries"))
    else:
        rules.append(_rule("R1", "No keys, account IDs or request/response content stored", "pass",
                           "ledger fields allow-listed; no key-like text found"))

    verified = [r["verified_cumulative"] for r in sorted(records["reviews"], key=lambda r: r["recorded_at"])]
    negative = [e["request_id"] for e in usage if e["cost"] < 0]
    decreasing = any(b < a for a, b in zip(verified, verified[1:]))
    rules.append(_rule(
        "R2", "Ledger records incremental charges; cumulative is derived", "fail" if negative or decreasing else "pass",
        "negative charge or decreasing verified cumulative" if negative or decreasing
        else "per-request costs only; cumulative computed from them"))

    currencies = {e["currency"] for e in usage} | {config["currency"]}
    same = currencies == {config["pricing"]["currency"]}
    rules.append(_rule("R3", "One currency, conversions documented", "pass" if same else "fail",
                       f"all figures in {config['currency']}" if same
                       else f"mixed currencies {sorted(currencies)} without documented conversion"))

    state = threshold_state(config, summary["effective_cumulative"] / config["hard_budget"])
    rules.append(_rule("R4", "Warn at thresholds, stop before the hard budget",
                       {"ok": "pass", "warning": "warn", "hard_stop": "fail"}[state["state"]],
                       f"{summary['pct_used']}% used; warnings at {config['warn_thresholds']}, "
                       f"calls refused at {config['hard_stop']}"))

    if summary["verified_cumulative"] is None:
        rules.append(_rule("R5", "Estimates are not provider-confirmed charges", "warn",
                           "no verified figure yet; run reconcile with the OpenAI usage dashboard total"))
    else:
        rules.append(_rule("R5", "Estimates are not provider-confirmed charges", "pass",
                           f"verified {summary['verified_cumulative']:.2f} on {summary['last_reconciled']}"))

    interval = config["review_interval_days"]
    period_start = date.fromisoformat(config["period_start"])
    if summary["last_reconciled"] is None:
        overdue = (today - period_start).days > interval
        rules.append(_rule("R6", "Reconcile at least weekly, including the Week 2 checkpoint",
                           "fail" if overdue else "warn",
                           f"no review yet; first due by {period_start + timedelta(days=interval)}"))
    else:
        age = (today - date.fromisoformat(summary["last_reconciled"])).days
        rules.append(_rule("R6", "Reconcile at least weekly, including the Week 2 checkpoint",
                           "fail" if age > interval else "pass", f"last review {age} days ago"))

    env_url = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
    allowed = not env_url or env_url in config["allowed_base_urls"]
    rules.append(_rule("R7", "Only the class-provided OpenAI endpoint", "pass" if allowed else "fail",
                       f"allowed: {config['allowed_base_urls']}" if allowed
                       else "OPENAI_BASE_URL points at a non-allowed endpoint"))

    incomplete = [e["request_id"] for e in usage
                  if not {"latency_ms", "input_tokens", "output_tokens"} <= set(e)]
    if not usage:
        r8 = ("warn", "no tracked requests yet; route LLM calls through tracked_chat")
    elif incomplete:
        r8 = ("fail", f"{len(incomplete)} entries missing latency or token usage")
    else:
        r8 = ("pass", f"{len(usage)} requests logged with tokens and latency")
    rules.append(_rule("R8", "Every request logs token usage and latency", *r8))
    return rules


# ---------------------------------------------------------------- checkpoints

def _weekly_coverage(config: dict, records: dict, today: date) -> tuple[bool, str]:
    dates = sorted(date.fromisoformat(r["date"]) for r in records["reviews"])
    if not dates:
        return False, "no reconciliations recorded"
    end = min(today, date.fromisoformat(config["period_end"]))
    points = [date.fromisoformat(config["period_start"]), *dates, end]
    worst = max((b - a).days for a, b in zip(points, points[1:]))
    ok = worst <= config["review_interval_days"]
    return ok, f"{len(dates)} reviews; longest gap {worst} days"


def evaluate_checkpoints(paths: Paths, config: dict, records: dict, rules: list[dict],
                         summary: dict, today: date) -> list[dict]:
    status = {r["id"]: r["status"] for r in rules}
    results = []
    for spec in CHECKPOINT_ITEMS:
        path = paths.root / spec["file"]
        text = _read_text(path) if path.exists() else ""
        ticked = f"- [x] {spec['item']}" in text
        if spec["id"] == "week2_api_spend":
            conditions = {
                "baseline_set": config["hard_budget"] > 0,
                "verified_by_reconciliation": status["R5"] == "pass",
                "reviewed_within_interval": status["R6"] == "pass",
                "budget_remaining": summary["remaining"] > 0 and status["R4"] != "fail",
                "process_rules_pass": all(status[r] == "pass" for r in ("R1", "R2", "R3", "R7")),
            }
            evidence = "docs/budget.md#review-cadence-and-request-cost"
        elif spec["id"] == "harness_weekly_spend":
            covered, detail = _weekly_coverage(config, records, today)
            conditions = {"weekly_reviews": covered, "verified_by_reconciliation": status["R5"] == "pass"}
            evidence = f"docs/budget.md#review-cadence-and-request-cost ({detail})"
        else:
            conditions = {"token_and_latency_logged": status["R8"] == "pass",
                          "tool_calls_logged": False}
            evidence = "logs/api_usage.jsonl covers tokens/latency; tool-call logging belongs to the agent layer"
        results.append({
            "id": spec["id"], "file": spec["file"], "item": spec["item"], "mode": spec["mode"],
            "conditions": conditions,
            "eligible": spec["mode"] == "tick" and all(conditions.values()),
            "ticked": ticked, "evidence": evidence,
        })
    return results


def apply_checkpoints(paths: Paths, checkpoints: list[dict]) -> None:
    """Tick eligible items. Never unticks anything."""
    for item in checkpoints:
        if not item["eligible"] or item["ticked"]:
            continue
        path = paths.root / item["file"]
        text = _read_text(path)
        unticked = f"- [ ] {item['item']}"
        if unticked in text:
            _write_text(path, text.replace(unticked, f"- [x] {item['item']}", 1))
            item["ticked"] = True
        else:
            item["ticked"] = "item_not_found"


# ---------------------------------------------------------------- docs/budget.md

def _money(value: float | None, currency: str, places: int = 2) -> str:
    return "not yet verified" if value is None else f"{value:.{places}f} {currency}"


def _replace_block(text: str, name: str, lines: list[str]) -> str:
    start, end = f"<!-- budget-tracker:{name}:start -->", f"<!-- budget-tracker:{name}:end -->"
    if start not in text or end not in text:
        raise BudgetError(f"docs/budget.md is missing the {name} marker block")
    newline = "\r\n" if "\r\n" in text else "\n"
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}{newline}{newline.join(lines)}{newline}{end}{tail}"


def render_budget_doc(paths: Paths, config: dict, records: dict, ledger: list[dict], summary: dict) -> None:
    cur = config["currency"]
    budget = config["hard_budget"]
    reviews = sorted(records["reviews"], key=lambda r: r["recorded_at"])
    status = ("Tracked by `agent/budget_tracker.py`; reconciled against the provider dashboard."
              if reviews else "Tracked by `agent/budget_tracker.py`; no reconciliation recorded yet.")
    baseline = [
        f"**Status:** {status}",
        "",
        f"- Hard budget: {budget:.2f} {cur}.",
        f"- Currency: {cur} (provider bills in {config['pricing']['currency']}; no conversion).",
        f"- Budget period: {config['period_start']} to {config['period_end']}.",
        f"- Last reconciliation date: {summary['last_reconciled'] or 'none yet'}.",
        f"- Verified cumulative spend: {_money(summary['verified_cumulative'], cur)}"
        f" (local estimate {summary['estimated_cumulative']:.4f} {cur}).",
        f"- Remaining budget (hard budget minus cumulative spend): {summary['remaining']:.2f} {cur}"
        f" ({summary['basis']}).",
    ]

    usage = [e for e in ledger if e.get("type") == "usage"]
    ledger_rows = ["| Date/period | Provider/model | Purpose | Usage | Incremental cost | Cumulative cost | Remaining budget | Verification source |",
                   "|---|---|---|---|---|---|---|---|"]
    review_rows = ["| Review date | Period covered | Verified cumulative spend | Remaining budget | Discrepancy/action | Next review due |",
                   "|---|---|---|---|---|---|"]
    previous_date, previous_total, previous_ts = config["period_start"], 0.0, None
    for review in reviews:
        window = [e for e in usage if (previous_ts is None or _parse_ts(e["ts"]) > previous_ts)
                  and _parse_ts(e["ts"]) <= _parse_ts(review["recorded_at"])]
        purposes = ", ".join(sorted({e["purpose"] for e in window})) or "not tracked locally"
        models = ", ".join(sorted({e["model"] for e in window})) or "all models"
        period = f"{previous_date} to {review['date']}"
        remaining = budget - review["verified_cumulative"]
        ledger_rows.append(
            f"| {period} | OpenAI ({models}) | {purposes} | {len(window)} tracked requests, "
            f"{sum(e['input_tokens'] for e in window)} in / {sum(e['output_tokens'] for e in window)} out tokens "
            f"| {review['verified_cumulative'] - previous_total:.2f} {cur} | {review['verified_cumulative']:.2f} {cur} "
            f"| {remaining:.2f} {cur} | {review['source']} |")
        next_due = date.fromisoformat(review["date"]) + timedelta(days=config["review_interval_days"])
        action = review.get("action") or "none"
        review_rows.append(
            f"| {review['date']} | {period} | {review['verified_cumulative']:.2f} {cur} | {remaining:.2f} {cur} "
            f"| {review['discrepancy']:+.4f} {cur} vs local estimate; {action} | {next_due} |")
        previous_date, previous_total, previous_ts = review["date"], review["verified_cumulative"], _parse_ts(review["recorded_at"])

    pricing = config["pricing"]
    demo_rows = ["| Sanitized request/trace ID | Model | Input/output tokens and other billed usage | Rate basis/date | Request cost/currency | Trace reference |",
                 "|---|---|---|---|---|---|"]
    for demo in records["demo_requests"]:
        demo_rows.append(
            f"| {demo['request_id']} | {demo['model']} | {demo['input_tokens']} in ({demo['cached_input_tokens']} cached)"
            f" / {demo['output_tokens']} out | {pricing['tier']} rates {pricing['unit']}, checked {pricing['checked_on']}"
            f" | {demo['cost']:.6f} {demo['currency']} (estimate) | [first_answer_trace.md](first_answer_trace.md) |")

    text = _read_text(paths.budget_doc)
    text = _replace_block(text, "baseline", baseline)
    text = _replace_block(text, "ledger", ledger_rows)
    text = _replace_block(text, "reviews", review_rows)
    text = _replace_block(text, "demo", demo_rows)
    _write_text(paths.budget_doc, text)


# ---------------------------------------------------------------- report / CLI

def build_report(paths: Paths, apply: bool = False) -> dict:
    now = _now()
    config, records, ledger = load_config(paths), load_records(paths), load_ledger(paths)
    summary = spend_summary(config, records, ledger)
    rules = evaluate_rules(paths, config, records, ledger, summary, now.date())
    checkpoints = evaluate_checkpoints(paths, config, records, rules, summary, now.date())
    if apply:
        apply_checkpoints(paths, checkpoints)
    thresholds = threshold_state(config, summary["effective_cumulative"] / config["hard_budget"])
    statuses = {r["status"] for r in rules}
    if thresholds["state"] == "hard_stop" or "fail" in statuses:
        exit_code = 2
    elif thresholds["state"] == "warning" or "warn" in statuses:
        exit_code = 1
    else:
        exit_code = 0
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "budget": {"hard_budget": config["hard_budget"], "currency": config["currency"],
                   "period": f"{config['period_start']}/{config['period_end']}"},
        "spend": summary,
        "thresholds": thresholds,
        "rules": rules,
        "checkpoints": checkpoints,
        "demo_request": records["demo_requests"][-1] if records["demo_requests"] else None,
        "exit_code": exit_code,
    }


def _cmd_init(paths: Paths, args) -> dict:
    if args.hard_budget <= 0:
        raise BudgetError("--hard-budget must be positive")
    start, end = date.fromisoformat(args.period_start), date.fromisoformat(args.period_end)
    if end <= start:
        raise BudgetError("--period-end must be after --period-start")
    config = load_config(paths)
    if args.currency.upper() != config["pricing"]["currency"]:
        raise BudgetError(f"Pricing is in {config['pricing']['currency']}; add a documented conversion first")
    config.update(hard_budget=float(args.hard_budget), currency=args.currency.upper(),
                  period_start=start.isoformat(), period_end=end.isoformat())
    _write_json(paths.config, config)
    if not paths.records.exists():
        _write_json(paths.records, load_records(paths))
    return _rendered_report(paths)


def _cmd_reconcile(paths: Paths, args) -> dict:
    if args.verified_spend < 0:
        raise BudgetError("--verified-spend cannot be negative")
    config, records, ledger = load_config(paths), load_records(paths), load_ledger(paths)
    previous = max((r["verified_cumulative"] for r in records["reviews"]), default=0.0)
    if args.verified_spend < previous:
        raise BudgetError(f"Verified cumulative spend cannot decrease (last verified {previous:.2f})")
    now = _now()
    estimated = spend_summary(config, records, ledger)["estimated_cumulative"]
    records["reviews"].append({
        "date": args.date or now.date().isoformat(),
        "recorded_at": now.isoformat(timespec="seconds"),
        "verified_cumulative": round(args.verified_spend, 4),
        "estimated_cumulative": round(estimated, 6),
        "discrepancy": round(args.verified_spend - estimated, 6),
        "source": _check_safe_text(args.source, "--source"),
        "action": _check_safe_text(args.action, "--action") if args.action else None,
    })
    _write_json(paths.records, records)
    return _rendered_report(paths)


def _cmd_demo_cost(paths: Paths, args) -> dict:
    config = load_config(paths)
    usage = [e for e in load_ledger(paths) if e.get("type") == "usage" and e.get("status") == "ok"]
    if args.request_id:
        usage = [e for e in usage if e["request_id"] == args.request_id]
    if not usage:
        raise BudgetError("No matching successful request in logs/api_usage.jsonl")
    entry = usage[-1]
    demo = {key: entry[key] for key in ("request_id", "ts", "model", "purpose", "input_tokens",
                                        "cached_input_tokens", "output_tokens", "latency_ms",
                                        "cost", "currency")}
    demo["rates"] = price_for(config, entry["model"])
    demo["rate_basis"] = f"{config['pricing']['tier']} {config['pricing']['unit']}, checked {config['pricing']['checked_on']}"
    if args.record:
        records = load_records(paths)
        records["demo_requests"] = [d for d in records["demo_requests"]
                                    if d["request_id"] != demo["request_id"]] + [demo]
        _write_json(paths.records, records)
        _rendered_report(paths)
    return {"demo_request": demo, "recorded": bool(args.record), "exit_code": 0}


def _rendered_report(paths: Paths) -> dict:
    config, records, ledger = load_config(paths), load_records(paths), load_ledger(paths)
    render_budget_doc(paths, config, records, ledger, spend_summary(config, records, ledger))
    return build_report(paths)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m agent.budget_tracker",
                                     description="Track OpenAI API spend against the team budget.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="set the budget baseline")
    init.add_argument("--hard-budget", type=float, required=True)
    init.add_argument("--currency", default="USD")
    init.add_argument("--period-start", required=True)
    init.add_argument("--period-end", required=True)
    sub.add_parser("check-key", help="validate OPENAI_API_KEY via the free models endpoint")
    sub.add_parser("status", help="show spend, thresholds, rules and checkpoints")
    rec = sub.add_parser("reconcile", help="record the provider-dashboard cumulative spend")
    rec.add_argument("--verified-spend", type=float, required=True)
    rec.add_argument("--source", required=True, help="where the figure came from, e.g. 'OpenAI usage dashboard'")
    rec.add_argument("--action", help="discrepancy follow-up, if any")
    rec.add_argument("--date", help="review date (YYYY-MM-DD), default today")
    demo = sub.add_parser("demo-cost", help="show the cost of one tracked request")
    demo.add_argument("--request-id")
    demo.add_argument("--record", action="store_true", help="save it to docs/budget.md")
    cp = sub.add_parser("checkpoints", help="evaluate checkpoint items")
    cp.add_argument("--apply", action="store_true", help="tick eligible items (never unticks)")
    return parser


def main(argv: list[str] | None = None, paths: Paths = Paths()) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            result = _cmd_init(paths, args)
        elif args.command == "check-key":
            result = check_key(paths)
            result["exit_code"] = 0 if result["valid"] else 2
        elif args.command == "status":
            result = build_report(paths)
        elif args.command == "reconcile":
            result = _cmd_reconcile(paths, args)
        elif args.command == "demo-cost":
            result = _cmd_demo_cost(paths, args)
        else:
            result = build_report(paths, apply=args.apply)
            result["applied"] = bool(args.apply)
    except (BudgetError, ValueError) as exc:
        result = {"error": str(exc), "exit_code": 2}
    print(json.dumps(result, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
