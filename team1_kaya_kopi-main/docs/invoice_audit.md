# Invoice and Chat/Email Audit

**Workstream:** B
**Status:** Template - source inventory not yet verified.

Inventory the expected 70 invoice scans and the chat/email documents, including
suppliers, date ranges, scan quality, and traps. Feed verified findings into the
extraction prompt and [trap_list.md](trap_list.md).

Record sanitized metadata only. Do not copy invoice images, message contents,
PII, or credentials into this document.

## Coverage reconciliation

- Expected invoice scans: 70 (provided scope; actual count not yet verified).
- Observed invoice scans: TODO.
- Missing, duplicate, or unreadable scans: TODO.
- Chat/email documents observed: TODO.
- Verification method and date: TODO.

## Invoice scan inventory

Use one entry per scan. Use a sanitized supplier identifier where necessary.
Distinguish unreadable or uncertain fields from confirmed values.

| ID | Source reference | Supplier reference | Invoice date/date range | Pages | Scan quality/readability | Traps or uncertainty | Trap IDs | Status |
|---|---|---|---|---|---|---|---|---|

## Chat/email document inventory

Use one entry per document and N/A for fields that do not apply.

| ID | Source reference | Type | Supplier references | Date range | Page count | Text/scan quality | Traps or uncertainty | Trap IDs | Status |
|---|---|---|---|---|---|---|---|---|---|

## Extraction prompt handoff

| Inventory IDs | Observed issue | Required extraction/validation behavior | Prompt or test reference | Verification result |
|---|---|---|---|---|

TODO: Record verified layout variations, date and amount formats, uncertain
fields, and source citation requirements. Link the actual extraction prompt and
tests when available; do not claim extraction accuracy before testing.

## OCR and source-conflict verification

- Vision/OCR pipeline module and reproducible run command: TODO.
- Sanitized extraction test reference and independently checked result: TODO.
- Unreadable/uncertain extraction behavior and retry policy: TODO.
- Week 2 end-to-end image retrieval and citation trace: TODO.
- Final invoice and chat/email ingestion coverage evidence: TODO.
- Chat/email text ingestion and retrieval are implemented independently of
  invoice OCR: see [document_processing.md](document_processing.md) and
  `tests/documents/test_document_integration.py`. This does not verify invoice/image
  ingestion or an assistant answer.
- Stale system prices versus scanned invoices: document the brief's invoice
  source-of-truth rule, effective dates, and any uncertainty. Record both sources
  and show the trust rationale in conflict answers.
- Purchase totals versus invoice totals/GST: TODO; record evidence rather than
  assuming GST is the cause.

## Findings and follow-up

For each trap, record reproducible evidence and its fix or disclosure decision
in [trap_list.md](trap_list.md). Summarize supplier price freshness, GST
mismatches, and extraction issues in [dq_report_b.md](dq_report_b.md).
Reconcile source coverage with [data_audit.md](data_audit.md).
