# Data Quality Report - Workstream B

**Workstream:** B
**Status:** Draft - findings pending.

Cover stale supplier prices, GST mismatches, and invoice extraction issues.
Reference evidence by ID from [trap_list.md](trap_list.md); do not copy raw client
records.

## Findings and handling

| Trap ID | Source category | Problem | Impact | Fix or disclosure | Verification | Remaining limitation |
|---|---|---|---|---|---|---|

## Coverage

- Supplier price freshness and effective dates: TODO.
- GST mismatches and reconciliation: TODO.
- Invoice extraction errors and uncertain fields: TODO.
- Source precedence: the brief identifies scanned invoices as the truth over
  stale system supplier prices. Record effective dates, conflicting evidence,
  the trust rationale, and remaining uncertainty; verify disclosure in an answer.
- Purchase-table versus invoice-total reconciliation: TODO; test the suspected
  GST explanation rather than treating it as an established finding.

## Handoff for merged report

TODO: Summarize the highest-impact findings, handling decisions, and unresolved
limitations for merging under workstream D into [dq_report.md](dq_report.md).
