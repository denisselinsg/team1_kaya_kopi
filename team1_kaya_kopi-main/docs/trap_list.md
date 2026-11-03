# Data Quality Trap List

## 1. Overview

**Workstreams:** A (trap-list coordination), B (document findings),
C (retrieval), D (policies/evals).

A-D denote workstreams, not people; contributor assignments are separate.

**Scope:** Findings currently cover two emails and one partial WhatsApp export,
plus investigation leads linking them to other sources. Text findings checked
on 1 Nov 2026; cross-source and calendar claims still need validation.

### Status key

- **Implemented:** Handling exists and has passed relevant checks.
- **Open:** The issue is verified, but handling is unfinished.
- **Pending verification:** The underlying claim still needs checking.
- **Client confirmation:** External clarification is needed.

Partial fixes remain Open; a proposed resolution is not a completed fix.

## 2. SQL traps

No source-specific findings recorded yet; this does not mean no problems exist.
For the reported transaction-to-outlet join loss, see
[DOC-E2](#doc-e2---joins-may-drop-sales) under Cross-source traps.

## 3. Document traps

### 3.1 Emails

For invoice/GST reconciliation and ingredient costs, see
[DOC-E4](#doc-e4---gst-explanations-are-unconfirmed) and
[DOC-E5](#doc-e5---item-prices-are-not-total-ingredient-costs).

#### DOC-E1 - The rename email has limits

**Problem:** The vendor confirms a POS rename, but not the outlet's identity in every other system or its full history.
**Resolution:** Keep the reviewed POS mapping and ask the client to confirm daily-file and roster mappings and supply the earlier email thread.

*Status: Client confirmation | Workstreams: B, A | Evidence: [Q1](#q1-source-review)*

#### DOC-E3 - The pricing question needs more evidence

**Problem:** Finance asks whether to raise Kopi prices by 10 cents, but an email alone cannot establish margins or justify that decision.
**Resolution:** Verify the available inputs, explain what they can support, and leave the decision to the business owner.

*Status: Pending verification | Workstreams: B, D | Evidence: [Q1](#q1-source-review), [Q3](#q3-cross-source-checks)*

### 3.2 WhatsApp

For measured wastage and invoice linkage, see
[DOC-C7](#doc-c7---wastage-comments-cannot-rank-outlets) and
[DOC-C11](#doc-c11---chat-cannot-prove-overcharging).

#### DOC-C2 - Chat messages are out of order

**Problem:** There are 77 backwards steps between neighbouring messages, so the last line is not necessarily the latest event.
**Resolution:** Sort retrieval results by parsed message date and time while keeping original line numbers for citations.

*Status: Implemented | Workstreams: B, C | Evidence: [Q4](#q4-chat-checks), [retrieval](../etl/documents/document_store.py)*

#### DOC-C3 - Repeated messages are not separate incidents

**Problem:** The 160 messages repeat eight templates, so counting messages can exaggerate real events.
**Resolution:** Preserve the records but describe them as staff reports rather than confirmed incident counts, and test that the assistant respects this distinction.

*Status: Open | Workstreams: B, C | Evidence: [Q4](#q4-chat-checks)*

#### DOC-C4 - Requests do not prove outcomes

**Problem:** Chat requests and complaints do not establish measured prices, approved opening hours or completed orders.
**Resolution:** Require supporting transaction or approval records before presenting a request as a completed action.

*Status: Open | Workstreams: B, C | Evidence: [Q1](#q1-source-review), [Q7](#q7-answer-tests)*

#### DOC-C5 - Holiday claims need checking

**Problem:** The report claims that 21 of 22 holiday statements are wrong, but that comparison is not independently verified here.
**Resolution:** Check each claimed date against an authoritative holiday calendar rather than using chat to explain sales patterns.

*Status: Pending verification | Workstreams: B, D | Evidence: [Q6](#q6-holiday-check)*

#### DOC-C6 - Fridge complaints are not failure counts

**Problem:** Chat repeats "third time this month" without three matching messages for any outlet and month, so the wording cannot establish failure frequency.
**Resolution:** Report fault mentions only and explain that a partial export cannot prove or disprove the claimed number of failures.

*Status: Open | Workstreams: B, C | Evidence: [Q4](#q4-chat-checks)*

#### DOC-C8 - Chat still uses the old outlet code

**Problem:** Chat contains 15 AMK-03 mentions, including nine in 2026, but none for AMK-3A, so searching only the new code misses evidence.
**Resolution:** Search both codes through the implemented outlet mapping while preserving the original wording.

*Status: Implemented | Workstreams: B, A | Evidence: [Q4](#q4-chat-checks), [alias tests](../tests/documents/test_document_integration.py)*

#### DOC-C9 - Sender labels do not identify the outlet

**Problem:** The sender's outlet prefix differs from the message's outlet in 56 of 69 comparable messages, making attribution by sender unreliable.
**Resolution:** Extract outlet codes from message text only and leave the outlet unknown when no code appears.

*Status: Implemented | Workstream: B | Evidence: [Q4](#q4-chat-checks), [parser](../etl/documents/document_parser.py)*

#### DOC-C10 - Supplier names are incomplete

**Problem:** Chat names only two suppliers, so assigning unnamed complaints by ingredient could blame the wrong supplier.
**Resolution:** Verify supplier-name mappings against source records and leave unnamed suppliers unknown.

*Status: Open | Workstream: B | Evidence: [Q4](#q4-chat-checks), [Q3](#q3-cross-source-checks)*

#### DOC-C1 - File formatting can break parsing

**Problem:** The export has a header, day-first dates, no final newline and no timezone, which can cause missing records or wrong dates.
**Resolution:** Parse message boundaries explicitly, preserve source lines, and leave the timezone unspecified until confirmed.

*Status: Implemented | Workstream: B | Evidence: [Q4](#q4-chat-checks), [parser tests](../tests/documents/test_document_parser.py)*

#### DOC-C12 - Missing messages prove nothing

**Problem:** The partial export covers 127 distinct days unevenly, so silence does not prove there were no incidents.
**Resolution:** State the coverage limits and do not invent explanations for gaps in chat, sales or daily records.

*Status: Open | Workstreams: B, A | Evidence: [Q4](#q4-chat-checks)*

#### DOC-C15 - Abbreviations hide relevant messages

**Problem:** Literal searches for expanded phrases such as "public holiday" miss abbreviated chat wording such as "PH".
**Resolution:** Add reviewed synonyms and test common rephrasings without changing the original evidence.

*Status: Open | Workstreams: B, C | Evidence: [Q4](#q4-chat-checks)*

### 3.3 Shared document safety

#### DOC-C13 - Retrieved text contains personal information

**Problem:** Original bodies and sender labels can expose personal information or encourage unsafe links to staff pay records.
**Resolution:** Restrict access, keep sensitive content out of logs and Git, and agree on answer-level privacy controls and any change to stored identities.

*Status: Open | Workstreams: B, D | Evidence: [Q7](#q7-answer-tests), [current privacy policy](document_processing.md#scope-and-privacy-decision)*

#### DOC-C14 - Documents are not instructions

**Problem:** Requests inside retrieved documents could be mistaken for instructions or permission to act, although no malicious instruction is established in the current files.
**Resolution:** Keep retrieval read-only and test that the future assistant ignores planted instructions in synthetic documents.

*Status: Open | Workstreams: C, D | Evidence: [Q7](#q7-answer-tests)*

## 4. Tabular traps

No source-specific findings recorded yet; this does not mean no problems exist.
For comparisons between chat comments and measured wastage, see
[DOC-C7](#doc-c7---wastage-comments-cannot-rank-outlets).

## 5. Image traps

No source-specific findings recorded yet; this does not mean no problems exist.
For invoice reconciliation, see [DOC-E4](#doc-e4---gst-explanations-are-unconfirmed),
[DOC-E5](#doc-e5---item-prices-are-not-total-ingredient-costs) and
[DOC-C11](#doc-c11---chat-cannot-prove-overcharging).

## 6. Cross-source traps

Each trap appears once; links from the source sections point here rather than
repeat the finding. Statuses below remain unchanged by this reorganization.

### DOC-E2 - Joins may drop sales

**Problem:** The report claims that joining transactions to the outlet master loses 1,236 rows covering 1,232 transaction IDs, which could understate sales.
**Resolution:** Verify those counts in raw SQL, map the outlet codes, and check that no rows disappear without explanation.

*Status: Pending verification | Workstream: A | Evidence: [Q2](#q2-pos-join-check)*

### DOC-E4 - GST explanations are unconfirmed

**Problem:** Finance suspects GST and "nett" pricing explain mismatched totals, but these are hypotheses and the report gives inconsistent scan counts.
**Resolution:** Compare purchase records with invoice subtotals, GST and totals, then state exactly which invoices were checked and what remains uncertain.

*Status: Pending verification | Workstream: B | Evidence: [Q3](#q3-cross-source-checks)*

### DOC-E5 - Item prices are not total ingredient costs

**Problem:** Changes in individual ingredient prices do not establish a combined cost trend or per-cup margin without quantities and recipes.
**Resolution:** Verify dated item prices and pack sizes, obtain the missing quantities and recipes, and confirm the financial-year definition with the client.

*Status: Pending verification | Workstream: B | Evidence: [Q3](#q3-cross-source-checks)*

### DOC-C7 - Wastage comments cannot rank outlets

**Problem:** The 18 wastage comments mention nine outlet codes but provide no measured quantities for a reliable ranking.
**Resolution:** Verify the daily-file coverage, units and date windows, then compare only outlets with suitable measurements.

*Status: Pending verification | Workstreams: A, B | Evidence: [Q3](#q3-cross-source-checks), [Q4](#q4-chat-checks)*

### DOC-C11 - Chat cannot prove overcharging

**Problem:** Chat complaints lack reliable invoice links, so similar dates or ingredients do not prove that a supplier overcharged.
**Resolution:** Match explicit identifiers and units, check delivery and credit-note records, and disclose unresolved contradictions.

*Status: Pending verification | Workstream: B | Evidence: [Q3](#q3-cross-source-checks)*

## 7. Evidence index

Keep raw bodies, names and addresses out of reports and test output.
Document retrieval does not fix POS joins or prove assistant guardrails.

### Q1: Source review

Review the two files in `data/docs/emails/` and the partial export in
`data/docs/whatsapp_exports/` locally. Record filename/line citations, not copied
personal content. The vendor dates the POS change to **1 Jan 2026**; the email
itself is dated **18 May 2026**. Finance concerns are attributed statements, not
independently proven financial facts. Earlier reply-thread content is unavailable.

### Q2: POS join check

Run read-only in the raw POS MySQL database. The reported counts remain unverified:

```sql
SELECT p.outlet_code, COUNT(*) AS unmatched_rows,
       COUNT(DISTINCT p.tx_id) AS distinct_transaction_ids
FROM pos_transactions AS p
LEFT JOIN outlets AS o ON o.outlet_code = p.outlet_code
WHERE o.outlet_code IS NULL
GROUP BY p.outlet_code;
```

After an agreed POS alias fix, rerun and require no unexplained row loss.
Check de-duplication separately.

### Q3: Cross-source checks

Validation across workstreams A and B requires executable query/script
references and results before closing:
invoice GST/subtotals, dated item prices and pack units, supplier identity,
measurement coverage, wastage windows, recipes/weights, and credit-note inventory.
The supplied report's invoice percentages, 70/179 coverage, 32,895 deduplicated
POS total, and wastage percentiles are **not independently verified here**.
Do not assume its proposed SQL views exist.

### Q4: Chat checks

Run the [aggregate audit script](../etl/documents/audit_traps.py) from repo root:

```powershell
python -m etl.documents.audit_traps
```

It outputs metadata only and fails if parsing fails. The entries record the
1 Nov baseline; changed inputs require renewed review, not forced old counts.

### Q6: Holiday check

The report claims 21 mismatches out of 22 holiday requests. Validation across
workstreams B and D requires a versioned authoritative 2025/2026 calendar,
including replacement-day rules, and comparison of each request date plus one
day. No external calendar is verified here.

### Q7: Answer tests

See [document trap scenarios](hostile_test.md#document-trap-scenarios) for pending
assistant tests and [document tests](../tests/documents/) for implemented service
checks. Record actual test commands, trace IDs, revisions and outcomes before
marking a semantic/policy fix Implemented.

### Client confirmations

Confirm cross-system outlet identity, earlier email thread, chat completeness
and timezone, actual hours changes, delivery/credit notes, "nett" definitions,
FY end and pricing inputs/authority. Singapore timezone and pseudonymized
storage are report recommendations, **not current implementation**: the API
retains unspecified chat timezone and original bodies for authenticated local
callers. Any privacy-policy change needs agreement.
