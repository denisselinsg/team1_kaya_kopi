import io
import json
import shutil
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import budget_tracker as bt

REPO = Path(__file__).resolve().parents[2]
SGT = timezone(timedelta(hours=8))
FAKE_KEY = "sk-proj-" + "A" * 40


class FakeClient:
    def __init__(self, prompt_tokens=1000, completion_tokens=200, cached=0,
                 base_url="https://api.openai.com/v1/", error=None):
        self.base_url = base_url
        self.calls = []
        usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                                prompt_tokens_details=SimpleNamespace(cached_tokens=cached))

        def create(**kwargs):
            self.calls.append(kwargs)
            if error:
                raise error
            return SimpleNamespace(usage=usage, choices=[])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        self.embeddings = SimpleNamespace(create=create)


def set_now(monkeypatch, value):
    monkeypatch.setattr(bt, "_now", lambda: value)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "agent").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copy(REPO / "agent" / "budget_config.json", tmp_path / "agent")
    shutil.copy(REPO / "docs" / "budget.md", tmp_path / "docs")
    for name in ("CHECKPOINTS.md", "HARNESS_CHECKLIST.md"):
        text = (REPO / name).read_text(encoding="utf-8").replace("- [x] ", "- [ ] ")
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    set_now(monkeypatch, datetime(2026, 11, 13, 9, 0, tzinfo=SGT))
    return bt.Paths(root=tmp_path)


def run(paths, capsys, *argv):
    code = bt.main(list(argv), paths=paths)
    return code, json.loads(capsys.readouterr().out)


def chat(paths, client, model="gpt-4o-mini", purpose="agent"):
    return bt.tracked_chat([{"role": "user", "content": "secret prompt text"}],
                           model=model, purpose=purpose, client=client, paths=paths)


def test_pricing_uses_longest_model_prefix_and_cached_rate():
    config = json.loads((REPO / "agent" / "budget_config.json").read_text(encoding="utf-8"))
    assert bt.price_for(config, "gpt-4o-mini-2024-07-18")["input"] == 0.15
    assert bt.price_for(config, "gpt-4o-2024-08-06")["input"] == 2.5
    assert bt.price_for(config, "unknown-model") is None
    rates = {"input": 0.15, "cached_input": 0.075, "output": 0.6}
    assert bt.compute_cost(rates, 1_000_000, 500_000, 1_000_000) == pytest.approx(0.6 + 0.1125)


def test_tracked_chat_logs_usage_without_content(repo):
    client = FakeClient(prompt_tokens=1000, completion_tokens=200)
    _, entry = chat(repo, client)
    assert client.calls[0]["max_completion_tokens"] == 1024
    assert entry["cost"] == pytest.approx((1000 * 0.15 + 200 * 0.6) / 1e6)
    ledger = repo.ledger.read_text(encoding="utf-8")
    assert "secret prompt text" not in ledger
    assert set(json.loads(ledger)) <= bt.USAGE_FIELDS


def test_tracked_embeddings_logs_input_tokens(repo):
    _, entry = bt.tracked_embeddings(["kaya toast"], model="text-embedding-3-small", purpose="rag",
                                     client=FakeClient(prompt_tokens=500_000), paths=repo)
    assert entry["cost"] == pytest.approx(0.01)


def test_failed_call_is_logged_and_reraised(repo):
    with pytest.raises(TimeoutError):
        chat(repo, FakeClient(error=TimeoutError("slow")))
    assert bt.load_ledger(repo)[0]["status"] == "error"


@pytest.mark.parametrize("kwargs,message", [
    ({"model": "mystery-model"}, "No price configured"),
    ({"purpose": "Tell me the CEO salary"}, "purpose must be"),
])
def test_preflight_rejects_unpriced_models_and_free_text_purposes(repo, kwargs, message):
    client = FakeClient()
    with pytest.raises(bt.BudgetError, match=message):
        chat(repo, client, **kwargs)
    assert client.calls == []


def test_non_class_endpoint_is_refused(repo):
    client = FakeClient(base_url="https://proxy.example.com/v1")
    with pytest.raises(bt.BudgetError, match="class-provided"):
        chat(repo, client)
    assert client.calls == []


def test_hard_stop_refuses_before_sending(repo, capsys):
    run(repo, capsys, "reconcile", "--verified-spend", "47.495", "--source", "OpenAI usage dashboard")
    client = FakeClient()
    with pytest.raises(bt.BudgetExceeded):
        chat(repo, client, model="gpt-5")
    assert client.calls == []


def test_warning_threshold_is_logged(repo, capsys, caplog):
    run(repo, capsys, "reconcile", "--verified-spend", "24.99", "--source", "OpenAI usage dashboard")
    chat(repo, FakeClient(prompt_tokens=10_000, completion_tokens=10_000), model="gpt-4o")
    assert "API budget warning" in caplog.text


def test_overdue_review_fails_and_nothing_is_ticked(repo, capsys):
    code, report = run(repo, capsys, "checkpoints", "--apply")
    assert code == 2
    assert report["budget"] == {"hard_budget": 50.0, "currency": "USD", "period": "2026-10-31/2026-11-21"}
    rules = {r["id"]: r["status"] for r in report["rules"]}
    assert rules["R5"] == "warn" and rules["R6"] == "fail"
    assert not any(c["eligible"] for c in report["checkpoints"])
    assert "- [ ] API spend checked against budget" in (repo.root / "CHECKPOINTS.md").read_text(encoding="utf-8")


def test_reconcile_then_checkpoints_tick_and_are_idempotent(repo, capsys, monkeypatch):
    for day, spend in ((6, "0.40"), (12, "1.10")):
        set_now(monkeypatch, datetime(2026, 11, day, 18, 0, tzinfo=SGT))
        run(repo, capsys, "reconcile", "--verified-spend", spend, "--source", "OpenAI usage dashboard")
    set_now(monkeypatch, datetime(2026, 11, 12, 19, 0, tzinfo=SGT))
    chat(repo, FakeClient())
    set_now(monkeypatch, datetime(2026, 11, 13, 9, 0, tzinfo=SGT))

    code, report = run(repo, capsys, "checkpoints", "--apply")
    by_id = {c["id"]: c for c in report["checkpoints"]}
    assert code == 0, report["rules"]
    assert by_id["week2_api_spend"]["ticked"] is True
    assert by_id["harness_weekly_spend"]["ticked"] is True
    assert by_id["harness_request_logging"]["eligible"] is False
    assert report["spend"]["verified_cumulative"] == 1.1
    assert report["spend"]["effective_cumulative"] > 1.1

    checkpoints = (repo.root / "CHECKPOINTS.md").read_text(encoding="utf-8")
    assert checkpoints.count("- [x] API spend checked against budget") == 1
    run(repo, capsys, "checkpoints", "--apply")
    assert (repo.root / "CHECKPOINTS.md").read_text(encoding="utf-8") == checkpoints
    harness = (repo.root / "HARNESS_CHECKLIST.md").read_text(encoding="utf-8")
    assert "- [ ] Every request logs its tool calls" in harness

    doc = repo.budget_doc.read_text(encoding="utf-8")
    assert "Hard budget: 50.00 USD." in doc
    assert "| 2026-11-06 to 2026-11-12 | OpenAI (all models) |" in doc
    assert "| 0.70 USD | 1.10 USD | 48.90 USD |" in doc


def test_reconcile_rejects_decreasing_spend_and_keys(repo, capsys):
    run(repo, capsys, "reconcile", "--verified-spend", "2", "--source", "dashboard")
    code, out = run(repo, capsys, "reconcile", "--verified-spend", "1", "--source", "dashboard")
    assert code == 2 and "cannot decrease" in out["error"]
    code, out = run(repo, capsys, "reconcile", "--verified-spend", "3", "--source", FAKE_KEY)
    assert code == 2 and FAKE_KEY not in json.dumps(out)


def test_key_like_text_in_ledger_fails_r1(repo, capsys):
    repo.ledger.parent.mkdir()
    repo.ledger.write_text(json.dumps({"type": "note", "text": FAKE_KEY}) + "\n", encoding="utf-8")
    code, report = run(repo, capsys, "status")
    assert code == 2
    assert {r["id"]: r["status"] for r in report["rules"]}["R1"] == "fail"
    assert FAKE_KEY not in json.dumps(report)


def test_demo_cost_records_sanitized_row(repo, capsys):
    _, entry = chat(repo, FakeClient(prompt_tokens=1830, completion_tokens=240))
    code, out = run(repo, capsys, "demo-cost", "--record")
    assert code == 0 and out["demo_request"]["request_id"] == entry["request_id"]
    assert entry["request_id"] in repo.budget_doc.read_text(encoding="utf-8")


def test_check_key_never_exposes_the_key(repo):
    def ok(request, timeout):
        assert request.get_header("Authorization") == f"Bearer {FAKE_KEY}"
        return io.BytesIO(json.dumps({"data": [{"id": "gpt-4o-mini"}, {"id": "dall-e-3"}]}).encode())

    def rejected(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(FAKE_KEY.encode()))

    good = bt.check_key(repo, opener=ok)
    assert good["valid"] is True and good["priced_models_visible"] == 1
    bad = bt.check_key(repo, opener=rejected)
    assert bad["valid"] is False and FAKE_KEY not in json.dumps(bad)


def test_rendering_preserves_crlf_line_endings(repo, capsys):
    run(repo, capsys, "init", "--hard-budget", "50", "--period-start", "2026-10-31", "--period-end", "2026-11-21")
    doc = repo.budget_doc.read_bytes()
    assert doc.count(b"\n") == doc.count(b"\r\n")
