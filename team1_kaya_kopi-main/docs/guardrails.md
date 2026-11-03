# Guardrail Specification

**Workstream:** D
**Status:** Draft - rules and test cases awaiting agreement.

Use the [harness checklist](../HARNESS_CHECKLIST.md) as the acceptance baseline.
Document intended behavior separately from verified implementation.

## Input refusals

Require deterministic, code-enforced refusal of out-of-scope and
policy-violating requests, ideally before any LLM call. Record whether each test
made an LLM call. A system-prompt instruction alone does not satisfy this rule.

| Rule ID | Request category | Detection/decision rule | Safe response | Implementation | Test IDs |
|---|---|---|---|---|---|

## Output PII scrubbing

TODO: Specify protected fields, detection and redaction rules, application points
(answers, tool results, logs, and errors), and tests for accidental disclosure.
Use synthetic examples only.

Checks must run in code between the model and the user and cover both PII and
other policy violations. Link the module and an eval proving it holds.

## Data protection and PDPA rationale

TODO: Identify sensitive fields found during the audit, permitted uses, access
boundaries, minimization/redaction rules, storage/retention decisions, and safe
logging. Explain how these decisions address the discovered data-protection
risks, and prepare a non-sensitive explanation for demo-day PDPA questions.

## Grounding and safe limitations

TODO: Specify behavior for insufficient evidence, contradictory sources, and
unavailable tools. Require explicit limitations instead of guessing. Document
source precedence and conflict disclosure, not silent source selection.

## Kill-shot question

- Canonical question: TODO.
- Why it is a kill-shot: TODO.
- Required refusal or safe handling: TODO.

| Test ID | Synthetic test phrasing | Expected behavior | Actual behavior | Result |
|---|---|---|---|---|

Test at least five distinct phrasings, including direct, indirect, and rephrased
variants. Record results for each; five unexecuted placeholders are not evidence.

| Required variant | Eval case reference | LLM call made? | Evidence reference | Result |
|---|---|---|---|---|
| 1 | TODO | TODO | TODO | Pending |
| 2 | TODO | TODO | TODO | Pending |
| 3 | TODO | TODO | TODO | Pending |
| 4 | TODO | TODO | TODO | Pending |
| 5 | TODO | TODO | TODO | Pending |

## Verification

TODO: Link automated tests and their run command. Record adversarial results in
[hostile_test.md](hostile_test.md).
