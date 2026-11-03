# Data Audit

**Workstream:** A
**Status:** Two-email and WhatsApp inventories verified on 2 Nov 2026; SQL,
tabular and image inventories and cross-source business claims remain pending
in this report.

Inventory every SQL table, spreadsheet, image set, and document file, with row
or page counts, date ranges, and outlet codes, so nobody builds on assumptions.
Record metadata and aggregate evidence only; do not copy client data, PII, or
credentials into this document.

## 1. Audit overview

| Source | Current coverage | Verification date | Status |
|---|---|---|---|
| SQL | Inventory not yet recorded | Pending | Pending |
| Documents | Two emails and 160 WhatsApp messages across three files | 2 Nov 2026 | Inventory verified; business claims pending |
| Tabular | Inventory not yet recorded | Pending | Pending |
| Images | Inventory not yet recorded | Pending | Pending |

Use N/A for fields that do not apply and TODO for fields not yet verified.
Inventory completion does not prove ingestion, retrieval or business correctness.

## 2. SQL data

### Inventory

Expected input from the brief: MySQL POS dump, `sql/kayakopi_pos.sql`, in the
supplied data package; actual tables and counts remain unverified here.

| Inventory ID | Database/table | Row count | Date range | Outlet codes | Status |
|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | Pending |

### Key findings

TODO: Record verified table coverage, keys, duplicates, missing values and dates.
The reported outlet-code join loss is an investigation lead, not a verified
SQL finding in this audit.

### Handling and next checks

Workstream A: inventory every table, reconcile row counts and outlet codes,
review the cleaned-schema contract, and link findings to [trap_list.md](trap_list.md).

### Evidence and verification

TODO: Add read-only count/range queries, ingestion command/module, retrieval tool,
citation handling, test/trace references, results and verification date.

## 3. Documents

The inspected `data/docs/` tree contains **three files: two emails and one
WhatsApp export**, yielding **162 parsed records**.
This reconciles the supplied files, not complete email/chat history or the
business claims they contain.

### 3.1 Emails

#### Inventory

| ID | Source reference | Type | Table/sheet/set | Row/page/image count | Date range | Outlet codes | Verification query or method | Status |
|---|---|---|---|---|---|---|---|---|
| DOC-EM-01 | `data/docs/emails/2026-05-18_outlet_rename.txt` | Plain-text email | POS vendor reply | 1 email, 11 logical lines; page count N/A | 18 May 2026, 09:03:44 +08:00 | AMK-03, AMK-3A | Email parser plus local source review; lines 1-11 | Inventory verified 2 Nov 2026; cross-system identity pending |
| DOC-EM-02 | `data/docs/emails/2026-06-02_finance_query.txt` | UTF-8 plain-text email | Finance query | 1 email, 12 logical lines; page count N/A | 2 Jun 2026, 14:22:10 +08:00 | None explicitly mentioned | Email parser plus local source review; lines 1-12 | Inventory verified 2 Nov 2026; financial claims pending reconciliation |

#### Key findings

**DOC-EM-01: Outlet rename**

| Field | Verified document content or required follow-up |
|---|---|
| Attributed statement | The POS vendor states AMK-03 was re-registered as AMK-3A in the new POS version, with historical data before January using the old code |
| Effective business date | 1 Jan 2026, explicitly stated in body line 8; distinct from the 18 May email date in header line 3 |
| Business risk | Searches or joins using only one code could omit part of the outlet's history |
| Handling | Retain original codes and use the reviewed outlet mapping; verify POS joins preserve rows |
| Required confirmation | Confirm whether daily files and roster entries refer to the same outlet across systems |
| Limits | Only a reply is supplied; earlier thread content and complete historical coverage are not established |
| Related traps | DOC-E1, DOC-E2, DOC-C8 |

Source citation: `docs/emails/2026-05-18_outlet_rename.txt`, lines 3-4
(date/topic) and 8 (vendor statement).
The email documents the vendor's explanation, not independently verified
transaction counts or an assurance that every historical report is complete.

**DOC-EM-02: Finance investigation priorities**

| Field | Verified document content or required follow-up |
|---|---|
| Attributed report | Finance reports `supplier_purchases` totals differing from physical invoices for several months and invoice unit prices above system prices |
| Hypotheses, not confirmed causes | Ex-GST treatment, ambiguous supplier "nett" pricing, and stale system prices |
| Business question | Determine the actual ingredient-price trend and evidence relevant to a proposed 10-cent Kopi price increase |
| Verification | Match purchases to invoices and compare quantities, pack units, unit prices, subtotals, GST and totals over explicit date windows |
| Decision limits | The email supplies no discrepancy amounts, affected-month list, invoice IDs or verified cost-per-cup calculation |
| Required confirmation | Confirm financial-year end, recipe/quantity inputs, pricing authority and supplier definitions of "nett" |
| Related traps | DOC-E3, DOC-E4, DOC-E5, DOC-C13 |

Source citation: `docs/emails/2026-06-02_finance_query.txt`, lines 3-4
(date/topic), 8 (reported discrepancies and hypotheses) and 10 (business question).
Do not treat the reported price difference as a measured trend, infer a fiscal
year from the subject, or use this email alone to recommend a price change.

Both emails have From/To/Date/Subject headers and bodies, but contact addresses,
personal names and full bodies are intentionally excluded from this audit.

#### Handling and next checks

Workstreams A/B: verify outlet identity and POS joins; workstream B: reconcile
invoice prices and tax; workstreams B/D: confirm pricing inputs and privacy
controls. Track DOC-E1-E5, DOC-C8 and DOC-C13-C14 in
[trap_list.md](trap_list.md); cross-source handoffs are in section 6.

#### Evidence and verification

**DOC-EM-01 and DOC-EM-02: Reproduction and review**

Run from the repository root with Python and the supplied local files; no
database, API key or external service is needed.
Counts use `splitlines()` (logical lines), not the editor's trailing empty line.
The [email parser](../etl/documents/document_parser.py) checks headers/dates and
preserves file line spans; a manual source review establishes statement meaning
and the explicitly stated rename date, not general-purpose semantic extraction.

```powershell
@'
from pathlib import Path
from etl.documents.document_parser import parse_email

root = Path(r"data\docs")
expected = {
    "2026-05-18_outlet_rename.txt": (11, "2026-05-18T09:03:44", ["AMK-03", "AMK-3A"]),
    "2026-06-02_finance_query.txt": (12, "2026-06-02T14:22:10", []),
}
assert {p.name for p in (root / "emails").iterdir() if p.is_file()} == set(expected)
for name, (lines, timestamp, outlets) in expected.items():
    text = (root / "emails" / name).read_text(encoding="utf-8-sig")
    parsed = parse_email(text)
    assert not parsed.issues and len(parsed.records) == 1, "Review email parsing"
    record = parsed.records[0]
    assert len(text.splitlines()) == lines
    assert (record.line_start, record.line_end) == (1, lines)
    assert record.timestamp.isoformat() == timestamp
    assert record.offset_minutes == 480
    assert record.outlets == outlets
    print(name, "records", 1, "lines", lines, "timestamp", timestamp,
          "offset_minutes", record.offset_minutes, "outlet_codes", outlets)
print("document_files", sum(p.is_file() for p in root.rglob("*")))
'@ | python -
```

Verification date: **2 Nov 2026**.
Expected: two single-record emails, 11 and 12 logical lines, each with a supplied
+08:00 offset; two outlet codes in the rename email and none in the finance email.
Re-review baselines if sources change; these checks do not verify GST, invoice
prices, POS row counts or the proposed pricing decision.

### 3.2 WhatsApp

#### Inventory

| ID | Source | Records | Date range | Status |
|---|---|---|---|---|
| DOC-WA-01 | `data/docs/whatsapp_exports/ops_chat_export.txt` | 160 messages; page count N/A | 2 Jul 2025-29 Jun 2026 | Inventory verified 2 Nov 2026; business claims unverified |

- **Structure:** UTF-8 text with message date/time, sender label and body, preceded by an export header.
- **Coverage:** 127 distinct message dates; 7-21 messages per month.
- **Outlet codes:** AMK-01, AMK-03, BDK-01, JEM-01, JUR-01, ORC-01,
  PGL-01, TAM-01, TPY-02, VIV-01, WDL-01 and YIS-02.
- **Attribution:** 106 messages explicitly mention an outlet; 54 do not.
- **Limits:** Partial history, unsorted records, day-first dates and unspecified
  timezone; no final newline.

Twelve codes appearing in chat does not prove complete outlet or date coverage.
AMK-03 persists in 2026 messages; reviewed alias search does not independently
confirm identity across every system.

#### Key findings

Counts are **message mentions, not incidents, completed actions or measured
costs**; each current message matches exactly one rule.

| Topic | Mentions | Literal matching phrase | Meaning and next check |
|---|---|---|---|
| Coffee-powder replenishment | 29 | `boss, kopi powder running low` | Stock-pressure reports; check inventory, purchases and fulfilment |
| Extended opening hours | 22 | `tmr PH,` | Requests, not approvals or verified holidays; check approved schedules and official calendar |
| Missed egg deliveries | 19 | `eggs today never deliver` | Delivery complaints; check delivery notes and supplier records |
| Fridge faults | 19 | `fridge spoil again` | Maintenance reports, not failure frequency; check dated maintenance records |
| Wastage | 18 | `wastage quite high` | Unmeasured staff concerns; check daily-file quantities, units and coverage |
| New part-time staff | 18 | `new part timer` | Planned staffing changes, not attendance; check authorized roster records without guessing sender identities |
| Short sugar deliveries | 18 | `sugar delivery short` | Reconciliation leads, not proof of overcharging; check invoices, delivery notes and credit notes |
| Condensed-milk orders/price concerns | 17 | `ordered 10 ctn condensed milk` | Reported orders and price concerns; check dated invoice unit prices and pack sizes |

The eight topic counts sum to **160**, with **zero unmatched** and **zero
multiple-topic matches**; this does not establish 160 separate incidents.

#### Handling and next checks

Workstreams B/C: preserve timestamps and line citations, improve synonym search
and distinguish reports from outcomes; workstreams A/B: verify outlet mappings
and measured wastage; workstreams B/D: verify holiday/approval evidence and
privacy controls. Track DOC-C1-C15 in [trap_list.md](trap_list.md).

#### Evidence and verification

**DOC-WA-01: Reproduction and counting rules**

Prerequisites: Python, the local parser and the supplied UTF-8 chat file;
no database, API key or external AI service is needed.
Run the [aggregate audit](../etl/documents/audit_traps.py) from repository root:

```powershell
python -m etl.documents.audit_traps
```

For the topic breakdown, use the same parser and literal phrases in the table;
the existing aggregate command does not yet output named topic counts.
This additional check prints counts only, never senders or raw message bodies:

```powershell
@'
from pathlib import Path
from etl.documents.document_parser import parse_whatsapp

path = Path(r"data\docs\whatsapp_exports\ops_chat_export.txt")
parsed = parse_whatsapp(path.read_text(encoding="utf-8-sig"))
assert parsed.records and not parsed.issues, "Resolve parsing errors before counting"
rules = {
    "Coffee-powder replenishment": "boss, kopi powder running low",
    "Extended opening hours": "tmr PH,",
    "Missed egg deliveries": "eggs today never deliver",
    "Fridge faults": "fridge spoil again",
    "Wastage": "wastage quite high",
    "New part-time staff": "new part timer",
    "Short sugar deliveries": "sugar delivery short",
    "Condensed-milk orders/price concerns": "ordered 10 ctn condensed milk",
}
counts = {topic: 0 for topic in rules}
unmatched = multiple = 0
for record in parsed.records:
    hits = [topic for topic, phrase in rules.items() if phrase in record.body]
    unmatched += not hits
    multiple += len(hits) > 1
    for topic in hits:
        counts[topic] += 1
print("messages", len(parsed.records))
print("topic_counts", counts)
print("unmatched", unmatched, "multiple_matches", multiple)
assert unmatched == 0 and multiple == 0, "Review new or ambiguous wording"
'@ | python -
```

Verification date: **2 Nov 2026**.
Preserve repeated messages, count only explicit body mentions, and interpret
relative dates against message timestamps without assigning an unconfirmed
timezone; no sender-to-roster inference is permitted.
Revisit rules and baselines when files change rather than forcing new messages
into existing topics.

### 3.3 Shared document pipeline

- **Ingestion:** `docker compose --profile documents run --rm document-ingest --source all`;
  module `etl.documents.ingest_documents`.
- **Retrieval:** `POST /v1/documents/search`; module `app.document_api`.
- **Provenance:** Source path/line span, revision, timestamp/offset, outlet-alias
  provenance and incomplete/stale coverage.
- **Tests:** [Parser tests](../tests/documents/test_document_parser.py) and
  [integration tests](../tests/documents/test_document_integration.py).
- **Recorded result:** Local parser and isolated Docker ingestion/retrieval
  verified for two emails and 160 messages; assistant citation display pending.

The pipeline preserves original bodies for authenticated local access and
excludes email routing headers; it is **not** an output PII guardrail or an
end-to-end AI answer. Keep audit reports metadata-only and see
[document_processing.md](document_processing.md) for operations and limitations.

## 4. Tabular data

### Inventory

Expected scope: eight outlet daily files and a staff roster XLSX in the supplied
package; actual files, sheets and counts remain unverified here.

| Inventory ID | File/sheet | Row count | Date range | Outlet codes | Status |
|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | Pending |

### Key findings

TODO: Record verified formats, units, missing dates, measurements and coverage.
Chat comments are not verification of measured wastage or staff attendance.

### Handling and next checks

Workstream A: inspect every sheet/file, reconcile identifiers and dates, quantify
measurement coverage and handle roster data under the agreed privacy policy.

### Evidence and verification

TODO: Add per-file/sheet count/range commands, ingestion module, retrieval tool,
citation handling, test/trace references, results and verification date.

## 5. Images

### Inventory

Expected scope: 70 supplier invoice scans; observed image/page counts, suppliers
and dates remain unverified here.

| Inventory ID | Image/file set | Image/page count | Date range | Supplier/outlet references | Status |
|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | Pending |

### Key findings

TODO: Record scan readability, extraction uncertainty and invoice coverage.
Do not treat finance's GST or stale-price hypotheses as verified scan findings.

### Handling and next checks

Workstream B: audit all scans, verify extracted quantities/units/prices/tax,
and record uncertain fields and supplier/date coverage in
[invoice_audit.md](invoice_audit.md).

### Evidence and verification

TODO: Add OCR/vision ingestion command/module, image retrieval/citation tool,
independently checked extraction samples, test/trace references and verification
date; distinguish inventory counts from successful extraction.

## 6. Cross-source checks

### Reconciliation summary

| Check | Sources | Current status |
|---|---|---|
| Outlet-code consistency | SQL, rename email, tabular files and chat | Document alias handling exists; cross-system identity and POS joins pending |
| Prices and GST | SQL, invoice images and finance email | Pending reconciliation |
| Wastage claims | WhatsApp and tabular measurements | Pending measured coverage and comparison |
| Hours and holidays | WhatsApp, approved schedules and official calendar | Pending external/approval evidence |

Reconcile the brief's 12 outlets with actual source identifiers, without assuming
every outlet appears in every source. Investigate AMK-03's January reporting
issue, preserve unmatched records and distinguish hypotheses from verified causes.

### Findings and handoff

| Inventory ID | Problem or uncertainty | Impact | Trap ID | Next action | Workstream |
|---|---|---|---|---|---|
| DOC-EM-01 | POS rename may split outlet history; other systems not confirmed | Missing sales or incorrect outlet joins | DOC-E1, DOC-E2, DOC-C8 | Verify POS/outlet-master counts before and after mapping; obtain cross-system identity and earlier thread confirmation | A, B |
| DOC-EM-02 | Reported mismatches, GST/"nett" ambiguity and suspected stale prices | Unsupported accounting explanation or price trend | DOC-E4, DOC-E5 | Match invoices/purchases with consistent units, dates and tax treatment; disclose verified coverage | B |
| DOC-EM-02 | Pricing question lacks established per-cup costs and decision inputs | Unsupported price recommendation | DOC-E3, DOC-E5 | Verify recipe/quantity inputs and financial period; provide evidence/limits and leave pricing to business authority | B, D |
| DOC-EM-01, DOC-EM-02 | Email identities and quoted requests are sensitive/untrusted content | Personal-data disclosure or instructions treated as permission | DOC-C13, DOC-C14 | Keep audit metadata-only; apply agreed privacy/output controls and read-only evidence handling | B, D |
| DOC-WA-01 | Old outlet code and unreliable sender prefixes | Wrong joins or attribution | DOC-E1, DOC-C8, DOC-C9 | Validate cross-system mapping; use explicit body codes, not sender identity | A, B |
| DOC-WA-01 | Repeated stock, order, delivery and maintenance reports lack confirmed outcomes | False event counts, price changes or overcharge claims | DOC-C3, DOC-C4, DOC-C6, DOC-C10, DOC-C11 | Corroborate against purchases, invoices, delivery/credit notes and maintenance records | B, C |
| DOC-WA-01 | Wastage is described but not measured in chat | Unsupported outlet ranking | DOC-C7 | Validate daily-file measurements, date windows and missing coverage | A, B |
| DOC-WA-01 | Hours requests depend on unverified holiday claims | Wrong schedules or sales explanations | DOC-C4, DOC-C5 | Check approved hours and authoritative holiday dates | B, D |
| DOC-WA-01 | Partial, unsorted history and abbreviated wording | Missed evidence or invented explanations for gaps | DOC-C1, DOC-C2, DOC-C12, DOC-C15 | Preserve timestamp/line provenance, disclose coverage and test synonym retrieval | B, C |
| DOC-WA-01 | Staffing text and retrieved requests contain sensitive or untrusted content | Privacy exposure or unintended actions | DOC-C13, DOC-C14 | Review roster access and output controls; treat requests as evidence, not permission | B, D |

Record data-quality problems and handling decisions in [trap_list.md](trap_list.md).
Coordinate invoice and chat/email coverage with [invoice_audit.md](invoice_audit.md).

### Completion and acceptance

- [ ] Every SQL table inventoried with row counts.
- [ ] Every spreadsheet and sheet inventoried with row counts.
- [ ] Every image set inventoried with image/page counts.
- [ ] Every document inventoried with counts where applicable.
- [ ] Date ranges and outlet codes verified or explicitly marked unavailable across sources.
- [ ] Inventory reconciled against source file and table listings.
- [ ] Every supplied file opened; unreadable files recorded as blockers.

For each inventory, record runnable evidence, prerequisites, verification date
and result; flag assumptions instead of guessing. Week 2 requires ingestion and
retrieval on at least two source types including images and working OCR/vision;
final delivery requires all four types. These global checkboxes remain pending
until source-wide evidence is recorded, not merely because the document audit
is complete.
