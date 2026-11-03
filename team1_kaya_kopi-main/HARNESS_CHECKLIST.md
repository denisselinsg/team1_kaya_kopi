# The Harness Checklist

*Capstone handout — SCTP AI Engineering, Module 5. Distribute to all teams. Companion to notebook `00_anatomy_of_an_agent_harness` (session 5.1, capstone briefing).*

Your app will be graded live, by a skeptical customer, on messy data. The model will not save you; the harness will. Before demo day, your team should be able to tick every box below — and show the evidence in your repo.

## 1. Grounding: every number is computed, never remembered

- [ ] Facts and figures in answers come from a tool call (SQL query, retrieval, calculation) made *at question time* — not from text pasted into the prompt at startup.
- [ ] Cross-source questions (SQL × spreadsheet × scanned image) are joined by your code, not by hoping the model lines them up.
- **Evidence:** point to the tool definitions; show the tool trace for one hard question.

## 2. Citations: every answer says where it came from

- [ ] Answers cite the table, file, or document image they were derived from.
- [ ] When sources conflict (they will), the answer says so and states which one it trusts and why.
- **Evidence:** three demo answers with visible citations, one involving a conflict.

## 3. Guardrails: policy lives in code, not in the prompt

- [ ] Output guardrail: PII / policy violations are caught by code between the model and the user (regex or classifier), not just discouraged in the system prompt.
- [ ] Input guardrail: requests your app must refuse (out-of-scope, policy-violating) are refused deterministically — ideally without an LLM call.
- [ ] You know your scenario's "kill-shot question" — the one where a naive answer is a violation — and you have tested it with at least five phrasings.
- **Evidence:** the guardrail module + an eval case proving it holds.

## 4. Error handling: honest degradation, never invention

- [ ] A failing tool (timeout, bad file, unparseable image) produces an honest "I couldn't check X" — never a confident made-up value.
- [ ] Tool exceptions are caught; the app cannot crash mid-demo from one bad input.
- [ ] Retries/fallbacks exist where they make sense (flaky OCR, slow queries).
- **Evidence:** kill one dependency on purpose and screenshot the app's answer.

## 5. State: the conversation survives

- [ ] Multi-turn context works — "and what about last month?" resolves correctly.
- [ ] A restart (or crash) does not lose the session (checkpointer, NB 03 pattern).
- **Evidence:** demo a follow-up question and an app restart mid-conversation.

## 6. Human-in-the-loop: risky actions have a gate

- [ ] Any action with real-world consequences in your scenario (refund, booking, report filing) pauses for approval (`interrupt()`, NB 06 pattern) or is explicitly out of scope in your design doc.
- **Evidence:** one gated action in the demo, or one sentence in the architecture doc saying why none is needed.

## 7. Observability: you can answer "what did it just do, and what did it cost?"

- [ ] Every request logs its tool calls, latency, and token usage.
- [ ] You track cumulative spend against your team's API budget — weekly at minimum.
- [ ] When an answer is wrong, you can replay the trace and find which layer failed.
- **Evidence:** the log/trace for one request; your spend figure when asked.

## 8. Evals: you knew it worked before you plugged in the projector

- [ ] You keep a suite of ≥20 eval questions with checkable expectations: normal questions, trap questions from your data audit, and at least two whose correct answer is a **refusal**.
- [ ] The suite runs with one command, and you ran it after every significant change.
- [ ] Failures from the suite turned into fixes (your git history shows this).
- **Evidence:** the eval script + its latest pass/fail output, committed.

---

## Smells that you're vibe-coding (each one loses marks on demo day)

- Your "ingestion" is pasting CSV contents into the system prompt.
- Answers change every time you ask the same question.
- No answer ever says "I don't know" or "the source is unavailable."
- You can't say what a demo question costs, or where its number came from.
- The first time anyone asked your app an adversarial question was during the demo.

*Rule of thumb: if the model disappeared tomorrow and was replaced by a different one, how much of your app would still be yours? That part is the harness. Make it the part you're proud of.*
