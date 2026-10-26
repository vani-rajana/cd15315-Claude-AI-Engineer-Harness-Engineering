# Reflection Brief — Harness Engineering Capstone

**Name:** VEERA SATYAVANI RAJANA
**Date:** October 26, 2026

**Environment**

- Model(s): `claude-haiku-4-5-20251001`
- OS / Python: Windows 11 / Python 3.11.5
- Approx. API spend: ~$0.05 USD total across all 4 systems (System 1: $0.0473 USD across 8 fixtures; System 4: $0.00 offline recorded response; System 3: $0.00 local validator)

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** Quote the `stop_reason` sequence from one trace. Name the file and function that decides continue-vs-stop, and how.
   → In the trace file `traces/claim_01_kitchen_fire.jsonl` (run `20261026_124534`), the recorded `stop_reason` sequence across turns 1 to 6 is:
   ```json
   ["tool_use", "tool_use", "tool_use", "tool_use", "tool_use", "end_turn"]
   ```
   The file and function that controls the loop is `claims_intake/loop.py` in `run()`. The function evaluates `response.stop_reason` in an explicit `while True` loop: if `stop_reason == "tool_use"`, it dispatches all tool calls via `tool_executor`, appends the resulting `tool_result` blocks as a user message, and continues the loop; if `stop_reason == "end_turn"`, it returns a `FinalState` dataclass containing the accumulated messages and token usage; and if any unexpected reason appears (such as `max_tokens` or `stop_sequence`), it raises an `UnexpectedStopReason` exception rather than failing silently.

2. **Anti-pattern.** Name one anti-pattern `test_antipatterns.py` checks for. What would break in your run if the loop used it?
   → `test_antipatterns.py` checks for `test_no_string_membership_against_text_in_loop` and `test_no_integer_literal_iteration_cap_in_loop`. If the loop relied on an integer-literal iteration cap such as `for _ in range(5)`, multi-step ambiguous claims such as `claim_06_low_confidence_escalation` (which required policy lookup, fact extraction, clarification question/response, and escalation synthesis across 5+ turns) would be cut off prematurely before executing the terminal `escalate_to_human` tool. Similarly, if the loop checked for substring tokens like `"routed"` or `"done"` inside assistant prose, minor stylistic variations in Claude's output would cause the harness to misidentify loop termination, either hanging or dropping claims.

3. **Tool design.** Pick two tools with overlapping inputs. How do the descriptions prevent misrouting? What did a structured tool error let the agent do that a generic string would not?
   → `route_to_adjuster` and `escalate_to_human` in `claims_intake/tools.py` both accept terminal routing payloads and close the claim session. Their descriptions prevent misrouting by establishing mutually exclusive, strictly defined confidence thresholds: `route_to_adjuster` explicitly specifies `"Call this exactly once when classification confidence is at least 0.6 and severity has been assessed"`, whereas `escalate_to_human` states `"Call this exactly once when classification confidence is below 0.6 even after clarification, or when the claim cannot be routed safely"`. When a tool fails, returning a structured JSON error (`{"is_error": true, "error_category": "permanent", "is_retryable": false, "message": "..."}`) allows Claude to recognize whether the issue is transient (retryable) or permanent (non-retryable), enabling it to pivot to asking claimant clarification or escalating rather than repeating invalid inputs in a hallucinated loop.

4. **Your numbers.** Quote the turn count and cost for one claim. How does it differ from the README sample, and why?
   → For `claim_01_kitchen_fire` in `runs/20261026_124534/summary.md`, the session finished in 6 turns, consuming 4,590 input tokens and 292 output tokens, resulting in an estimated cost of **$0.0060 USD** and routing to `property_damage` with `medium` severity. For `claim_06_low_confidence_escalation`, the session finished in 5 turns with 1 clarification asked, 3,620 input tokens, 267 output tokens, costing **$0.0050 USD** and escalating to human review. The total run cost across all 8 fixtures was **$0.0473 USD**. This closely tracks the README benchmark ($0.04–$0.08) because our prompt assembly and tool sequence strictly adhered to the minimal schema contract without conversational drift.

---

### System 2 — Context strategy

5. **The reduction.** From `budget.json`: baseline tokens, assembled tokens, reduction %. Which section dominates the assembled context, and why keep it verbatim?
   → From `runs/20261026-124321/budget.json`, the baseline transcript token count was **47,144 tokens**, the assembled context was **19,874 tokens**, achieving a **57.84% token reduction**. The `active` section heavily dominates the assembled context at **19,538 tokens** (~98.3% of the assembled context). It is preserved verbatim because turns 29–48 represent the live, unresolved customer issue (updating credit card details), which contains sensitive error codes (`AVS_MISMATCH`), partial card digits (`7782`), bank verification history, and emotional nuance where lossy compression could discard critical facts necessary for the agent to resolve the immediate next turn.

6. **Summarize vs preserve.** State the rule for what gets summarized vs kept byte-exact, citing your per-section token numbers.
   → The architectural rule enforced by `retail_context/compressor.py` and `assemble.py` is: resolved past issues are compressed into structured 300–500 token summaries, while the currently active issue is preserved 100% byte-exact verbatim. As recorded in `budget.json`:
   - `case_facts`: 149 tokens (structured top-boundary anchor)
   - `resolved_refund`: 84 tokens (condensed from 18,200 raw turns)
   - `resolved_subscription`: 93 tokens (condensed from 14,500 raw turns)
   - `active`: 19,538 tokens (turns 29–48 preserved verbatim)
   Resolved segments are past history whose procedural turns no longer matter, whereas active turns represent the immediate problem space.

7. **Facts block.** Compare `eval.jsonl` to `eval_control.jsonl`. Which question regressed, and what does that prove?
   → In `eval.jsonl`, all 6 evaluation questions passed (6/6). In `eval_control.jsonl` (where the `# Case Facts` block was removed), **Q1** (*"What was the actual refund amount processed for order ORD-77310?"*) regressed from `PASS` ($22.14) to `FAIL` ("unknown"), and **Q6** (*"What is the structured status of the payment-method update issue..."*) regressed from `PASS` (`in_progress`) to `FAIL`. This proves that the `# Case Facts` block is load-bearing: granular transactional metadata (exact dollar amounts, system status tokens, and account IDs) is lost during narrative compression and cannot be recovered without a dedicated structured scratchpad anchored at the top of context.

---

### System 3 — Claude Code config

8. **Path-scoped rules.** Quote the glob frontmatter from one rule file. Why is it better than a directory-level CLAUDE.md for cross-cutting conventions?
   → The frontmatter from `.claude/rules/tests.md` is:
   ```yaml
   ---
   description: Conventions for test files (co-located *.test.ts and *.test.tsx)
   paths:
     - "**/*.test.tsx"
     - "**/*.test.ts"
   ---
   ```
   This is superior to directory-level `CLAUDE.md` files because testing conventions are cross-cutting: test files are co-located alongside source code across disparate directories (`src/components/`, `src/api/`, etc.). A directory-level `CLAUDE.md` would require duplicate configuration files in every single folder or would force mixing testing guidelines into general feature development prompts. Path-scoped glob rules activate only when matching files are edited, keeping prompt overhead orthogonal and lean.

9. **Forked skill.** Quote the `context: fork` and `allowed-tools` lines. What does running forked + read-only buy you? What breaks without it?
   → From `.claude/skills/deploy-check/SKILL.md`:
   ```yaml
   context: fork
   allowed-tools:
     - Read
     - Grep
     - Glob
     - Bash(git status:*)
     - Bash(git diff:*)
     - Bash(git log:*)
     - Bash(git rev-parse:*)
     - Bash(git ls-files:*)
     - Bash(gh pr view:*)
     - Bash(gh pr checks:*)
   ```
   Running forked + read-only isolates verbose inspection output (extensive `git diff` outputs, porcelain status, and file scans) inside a temporary sub-agent session, returning only a structured pass/fail verdict to the parent conversation. Read-only tool constraints guarantee that the validation skill cannot accidentally modify files, stage incomplete commits, or trigger unauthorized deployments. Without it, verbose command outputs flood the main conversation context, degrading reasoning quality, and unconstrained bash tools risk mutating repository state during a pre-flight check.

10. **Scope.** From the validator output: project-level vs user-level scope. Give one example of each from this config.
    → As validated by `python -m ecommerce_team_config .` (which exited `0` with `OK`), **project-level scope** resides in version-controlled files shared by the entire engineering team, such as `./CLAUDE.md` importing `@.claude/standards/api.md` and `.claude/commands/review.md`. Conversely, **user-level scope** lives outside version control in `~/.claude/CLAUDE.md` or `~/.claude/commands/`, reserved for individual developer preferences, personal terminal shortcuts, or private workflow aliases that must not be forced upon teammates.

---

### System 4 — Orchestration

11. **Push work down.** Defects the SQL query returned vs warm-tier total. Name the indexed query. Why does the model never see the full history?
    → In our shift run, the SQLite warm store (`data/warm.sqlite`) held **40 defects** total, but the SQL query returned only **0 defects** matching the fresh shift window. The indexed query in `shift_monitor/warm.py` is:
    ```sql
    SELECT * FROM defects WHERE ts > ? ORDER BY ts DESC LIMIT 50
    ```
    backed by `CREATE INDEX IF NOT EXISTS idx_defects_ts ON defects(ts)`. The model never sees the full defect history because over months of continuous factory operation across three daily shifts, defect logs grow to tens of thousands of records. Pushing temporal filtering down to indexed SQLite queries executes in sub-millisecond time and bounds input payloads, preventing context saturation, attention degradation, and excessive token expenditure.

12. **Crash recovery.** The resume-vs-fresh decision and its staleness threshold (`recovery.py`). Why is a fresh start with an injected summary sometimes more reliable than resuming?
    → In `shift_monitor/recovery.py`, the threshold is set to `STALE_RESUME_THRESHOLD_MINUTES = 30`. If the time elapsed since the last recorded step in `manifest.json` is $\le 30$ minutes, `decide()` returns `"resume"`; if $> 30$ minutes or if the manifest is completed/empty, it returns `"fresh"`. A fresh start with an injected summary is more reliable after 30 minutes because in-flight turn state becomes obsolete as physical line conditions evolve. Attempting to resume a stale mid-turn session risks compounding hallucinations or re-executing broken partial tool calls, whereas restarting fresh grounded by a synthesized summary provides clean conversational state.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → The generated `data/hot_state.json` file is **658 bytes**, well within the strict limit enforced by `HOT_STATE_BYTE_BUDGET = 5120` (5 KB) and `MAX_RECENT_HASHES = 20`. This budget is critical because an industrial quality monitoring system operates across 3 shifts per day, 365 days a year (>1,000 runs annually). Without a strict byte ceiling and ring-buffer eviction, state would monotonically accumulate over time, ultimately exceeding prompt limits, degrading model recall, increasing inference costs, and causing unrecoverable context crashes.

---

## Part 2 — Synthesis

14. **Three layers.** Point to a file/artifact for each layer and justify.
    → **Model:** `claude-haiku-4-5-20251001` (invoked in `claims_intake/client.py`). It provides raw natural language comprehension and next-token/tool predictions based solely on weights and current context.
    → **Harness:** `claims_intake/loop.py` (System 1) and `retail_context/assemble.py` (System 2). The harness governs the single execution lifecycle: managing the `stop_reason`-driven dispatch loop, enforcing token budgets, executing tools, pruning verbose tool JSON, and laying out context sections.
    → **Orchestration:** `shift_monitor/pipeline.py` (System 4). Orchestration coordinates multiple harness invocations across long time horizons: querying tiered storage (SQLite warm tier), maintaining hot state across shifts, executing crash recovery policies, and managing isolated sub-agent forks.

15. **Deterministic vs prompt.** Cite one behavior guaranteed in code (terminal tool, read-only allowlist, atomic write, byte budget) and one guided by prompt. When is each right?
    → **Guaranteed in code:** The atomic state write and byte budget enforcement in `shift_monitor/state.py` (`HotState.write_atomic()`), which checks `len(payload) <= 5120` and writes via a temporary file with `os.fsync` before atomic replacement. Code enforcement is mandatory for system invariants, access controls, data durability, and financial/budget limits.
    → **Guided by prompt:** The qualitative summarization of resolved customer disputes in `retail_context/prompts/compression_prompt.md`. Prompt guidance is right when synthesizing unstructured natural language, resolving ambiguous user intent, or distilling narrative nuances where rigid boolean code cannot capture conversational context.

16. **Context, two faces.** Compare context management in System 2 (intra-session) and System 4 (cross-session) with cited numbers from both. Same principle, different mechanism — how?
    → Both systems embody the fundamental harness engineering principle: *keep the model's active working context small, dense, and high-signal*.
    - **System 2 (Intra-session):** Reduces a single long conversation from **47,144 baseline tokens** to **19,874 assembled tokens** (57.84% reduction) by extracting a 149-token `# Case Facts` block, summarizing resolved past issues into 84 and 93 tokens, and keeping active turns 29–48 verbatim (19,538 tokens).
    - **System 4 (Cross-session):** Eliminates unbounded state growth across 8-hour shifts by offloading 40 defect records to an indexed SQLite database (`warm.sqlite`) and persisting only a **658-byte** `hot_state.json` ring buffer across shifts.
    System 2 achieves this in-memory via prompt decomposition and position-aware assembly; System 4 achieves this out-of-core via tiered relational storage and ring-buffered JSON state.

17. **Reliability you can't see in one run.** Name one behavior a test guarantees that a single successful run would not reveal. Why does it matter before shipping?
    → `test_run_backstop.py` in System 1 verifies that if the model prematurely emits `stop_reason == "end_turn"` without calling a terminal tool (`route_to_adjuster` or `escalate_to_human`), the runner's deterministic backstop (`_escalate_without_terminal`) catches it and writes an escalation record to `escalations.jsonl`. In any single normal run, Claude will almost always call a terminal tool correctly, hiding the danger. Without this test-verified backstop in code, an edge-case model response in production would cause a claim to silently vanish into the void without routing or notification.

18. **Blast radius.** Pick one system. What's the blast radius if it misbehaves, and what's the kill switch? Ground it in that system's tools, enforcement points, and state.
    → In System 3, the `/deploy-check` skill (`.claude/skills/deploy-check/SKILL.md`):
    - **Blast radius:** If allowed unrestricted write access and shell commands, a misbehaving agent could commit broken code, overwrite schema migrations, push unreviewed branches, or trigger invalid deployments to production.
    - **Kill switch / Enforcement:** Enforced at the harness level via `allowed-tools` (strictly limited to `Read`, `Grep`, `Glob`, and read-only `git status/diff/log` commands) and `context: fork`. The fork isolates all intermediate command executions, while the absence of write tools makes it structurally impossible for the model to mutate repository files or push commits, regardless of prompt injection or model hallucination.

---

## Part 3 — Honest assessment

19. **What broke.** One thing that failed first try in your environment, and how you fixed it. (If nothing, what you checked to be sure.)
    → Two specific environment issues occurred on Windows 11:
    1. During pip dependency installation for System 4, pip failed with `OSError: [Errno 2] No such file or directory` on `anthropic/resources/beta/organization/service_accounts/service_accounts.py` because the deeply nested solution path (`.../Build a Multi-Shift.../04-fork-scratchpad/solution/.venv/...`) reached 265 characters, hitting the Windows MAX_PATH limit (`LongPathsEnabled: 0`). We solved this by placing isolated virtual environments at the workspace root (`.venv1`, `.venv2`, `.venv4`), saving 68 characters.
    2. In System 2, `test_assembled_context_active_segment_byte_exact` failed because `Path.read_text()` defaulted to Windows ANSI codepage `cp1252`, corrupting UTF-8 em-dashes (`\u2014`) in the transcript. Setting `$env:PYTHONUTF8 = "1"` (PEP 540) enforced UTF-8 mode globally and brought the test suite to a clean 30/30 passed.

20. **What you'd change.** One architectural decision you'd make differently, grounded in what you observed.
    → In System 1 (`claims_intake/run.py`), the deterministic escalation backstop (`_escalate_without_terminal`) is triggered only *after* the agentic loop has already exited on `end_turn`. This requires injecting a synthetic tool call from outside the loop into `session.escalations`. A cleaner architectural pattern would be to handle non-terminal `end_turn` inside `loop.py` itself: when `end_turn` is received while `session.terminal_called` is false, append a system steering prompt (e.g., *"You must select a terminal tool: route_to_adjuster or escalate_to_human"*) and allow the model one final opportunity to route before forcibly escalating in code.
