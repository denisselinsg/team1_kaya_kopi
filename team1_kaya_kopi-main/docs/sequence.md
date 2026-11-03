# Question-to-Answer Sequence

**Workstream:** C
**Status:** Proposed flow - validate against the working application.

Trace one question from chat input through guardrails, tools, source citations,
and the final answer.

```mermaid
sequenceDiagram
    actor User
    participant Chat
    participant Input as Input guardrails
    participant Agent
    participant Tools as Query/retrieval tools
    participant Sources as Data and provenance
    participant Output as Output checks
    User->>Chat: Ask a question
    Chat->>Input: Validate request
    alt Request refused
        Input-->>Chat: Safe refusal
        Chat-->>User: Refusal
    else Request allowed
        Input->>Agent: Allowed question
        Agent->>Tools: Request evidence
        Tools->>Sources: Query/retrieve
        Sources-->>Tools: Evidence and source references
        Tools-->>Agent: Results and citation metadata
        Agent->>Output: Draft answer with citations
        Output-->>Chat: PII-scrubbed, checked response
        Chat-->>User: Answer with visible citations or explicit limitation
    end
```

## Verified example

TODO: Record a non-sensitive question, tools called, citation format, failure
behavior, and implementation references. Link the first successful trace in
[first_answer_trace.md](first_answer_trace.md).

## Question-time grounding evidence

- [ ] Every fact/figure is supported by a tool call made for this question.
- [ ] Cross-source joins and calculations are performed by code, not inferred
  by the model from unrelated retrieved fragments.
- [ ] Missing evidence produces an explicit limitation, not an invented answer.
- [ ] Conflicts disclose the competing sources, trusted source, and rationale.

| Step/tool | Tool definition reference | Question-time call/trace ID | Source references | Code join/calculation | Supported claim/citation |
|---|---|---|---|---|---|

TODO: Link a hard cross-source question trace and its verified numerical
expectations. Include state restoration, error, and approval branches in the
diagram when the implementation requires them.
