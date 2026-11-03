# Client Brief — Kaya Kopi Holdings Pte Ltd

*From: Serene Lim, Finance & Admin Manager (your client contact)*

We run 12 kopitiam and mall drink stalls island-wide. Boss wants to know if we should raise kopi
price by 10 cents, but honestly we don't even know our real costs. Our POS vendor exported
everything they have (see `sql/`), each outlet manager keeps their own daily Excel/CSV
(don't ask why all different format), and supplier invoices are the paper kind — we scanned
a year's worth into `images/supplier_invoices/`.

**What we want:** an assistant our ops team can ask things like "what's our margin on Kopi at
mall outlets this quarter", "which supplier raised prices the most this year", "which outlet has
the worst wastage", and it answers from OUR data with the evidence shown.

**Things I already know are confusing, good luck:**
- The system supplier prices look stale; the scanned invoices are the truth.
- Something happened to outlet AMK-03 in January, the reports lost it.
- Finance says the purchase table doesn't tally with the invoice totals. GST maybe?

**Data manifest:** `sql/kayakopi_pos.sql` (MySQL Workbench import), `tabular/` (8 outlet daily
files + staff roster xlsx), `images/supplier_invoices/` (70 scans), `docs/` (ops WhatsApp export, emails).

---

## Engagement rules (same for all teams)

You are a squad of **forward deployed engineers**. The client is non-technical.
A panel of judges will role-play your client contact at the demo.

**You must deliver, on presentation day (Sat 21 Nov 2026; per team: 5-minute pitch, 5-minute live demo, then Q&A from the panel; time slots to be scheduled):**

1. A working AI application using the LLM API endpoint provided in class (open API, key issued per team). No other paid AI services.
2. Ingestion of ALL data source types in this package (SQL, tabular, images, documents). The app must answer from *this* data, not model memory.
3. An architecture diagram and at least two Mermaid diagrams (e.g. data flow, sequence diagram of one query, ER diagram of your cleaned schema).
4. A one-page data quality report: what was wrong with the client's data and what you did about it.
5. A live demo in which the client (the judging panel) will ask unscripted questions.

**Constraints:**
- The raw data is too large to paste into a prompt. You are expected to build retrieval / pipelines, not a mega-prompt.
- Answers must cite their source (table, file, or image) so the client can verify.
- If the data cannot answer a question, the app must say so instead of guessing.
- Handle the data-protection issues you find. You may be asked about PDPA on demo day.

**Marking signal (what the client cares about):** correct answers on messy cross-source questions,
graceful handling of contradictions and missing data, clear architecture, and a demo that survives
questions you did not rehearse.
