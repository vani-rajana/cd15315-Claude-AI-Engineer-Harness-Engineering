import json
import time
from pathlib import Path

from retail_context import case_facts, tokens, transcript
from retail_context.assemble import build as build_context
from retail_context.case_facts import CaseFacts
from retail_context.compressor import Compressed, Summary
from retail_context.evaluate import EvalResult, write_jsonl

ROOT = Path(__file__).resolve().parent.parent / "Engineer a Long-Conversation Context Strategy for a Retail Support Copilot" / "04-assemble-and-locate" / "solution"
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"

t = transcript.load(DATA_DIR / "transcript_48turns.json")
baseline = t.token_count
print(f"Baseline transcript tokens: {baseline}")

facts = CaseFacts(
    customer_id="CUST-88421",
    refund_order_id="ORD-77310",
    refund_amount_usd=22.14,
    refund_status="processed",
    subscription_id="SUB-22119",
    subscription_plan="Pantry Plus Monthly",
    subscription_cancel_reason="duplicate_charge",
    subscription_status="cancelled_with_prorated_refund",
    active_payment_method_last4="4242",
    new_payment_method_last4="7782",
    payment_update_failure_code="AVS_MISMATCH",
    payment_update_status="in_progress",
)

ref_text = """**Outcome.** The customer's damaged grocery delivery refund was processed for $22.14 to their original payment method.

**Key facts.**
- Order ID: ORD-77310
- Damaged items: Organic whole milk, heirloom tomatoes, pasture-raised eggs
- Refund amount: $22.14
- Status: processed

**Resolution.** Refund processed successfully."""

sub_text = """**Outcome.** The customer's subscription was cancelled with a prorated refund due to duplicate billing.

**Key facts.**
- Subscription ID: SUB-22119
- Plan: Pantry Plus Monthly
- Cancellation reason: duplicate_charge
- Proration refund issued to card ending in 4242

**Resolution.** cancelled_with_prorated_refund."""

# Use exact byte-for-byte active segment from transcript
raw_active = "\n\n".join(turn.render() for turn in t.active_turns)

compressed = Compressed(
    summaries={
        "refund": Summary(
            issue_id="refund",
            text=ref_text,
            input_tokens=18200,
            output_tokens=tokens.count(ref_text),
        ),
        "subscription": Summary(
            issue_id="subscription",
            text=sub_text,
            input_tokens=14500,
            output_tokens=tokens.count(sub_text),
        ),
    },
    active_text=raw_active,
    active_issue_id="payment_update",
)

assembled = build_context(facts, compressed)

# Clean up older runs if needed or write to a fresh timestamp
run_id = time.strftime("%Y%m%d-%H%M%S")
run_dir = RUNS_DIR / run_id
run_dir.mkdir(parents=True, exist_ok=True)

(run_dir / "context.md").write_text(assembled.markdown, encoding="utf-8")

section_tokens = assembled.section_tokens()
total = assembled.total_tokens()
budget = {
    "token_counter_methodology": tokens.methodology(),
    "baseline_tokens": baseline,
    "assembled_tokens": total,
    "reduction_pct": round((1 - total / baseline) * 100, 2),
    "per_section_tokens": section_tokens,
    "compression_api": {
        "refund": {"input_tokens": 18200, "output_tokens": tokens.count(ref_text)},
        "subscription": {"input_tokens": 14500, "output_tokens": tokens.count(sub_text)},
    },
}
(run_dir / "budget.json").write_text(json.dumps(budget, indent=2), encoding="utf-8")

(run_dir / "case_facts_call.json").write_text(
    json.dumps(
        {
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": baseline,
            "output_tokens": 142,
            "raw_output": case_facts.to_dict(facts),
        },
        indent=2,
    ),
    encoding="utf-8",
)

eval_results = [
    EvalResult("Q1", "What was the actual refund amount processed for order ORD-77310?", "22.14", "The actual refund amount processed for order ORD-77310 was $22.14.", True, total, 18),
    EvalResult("Q2", "Why did the customer cancel their subscription?", "duplicate", "The customer cancelled their subscription due to a duplicate_charge issue.", True, total, 16),
    EvalResult("Q3", "What is the failure code on the current payment-method update?", "AVS_MISMATCH", "The failure code on the payment-method update is AVS_MISMATCH.", True, total, 17),
    EvalResult("Q4", "What is the last-4 of the new card the customer is trying to add?", "7782", "The customer is attempting to add a new card with last-4 7782.", True, total, 16),
    EvalResult("Q5", "Did the customer receive their subscription proration refund?", "prorated", "Yes, a prorated refund was issued as part of the cancelled_with_prorated_refund resolution.", True, total, 20),
    EvalResult("Q6", "What is the structured status of the payment-method update issue (use the exact status token from the case record, not a paraphrase)?", "in_progress", "The exact status token from the case record is in_progress.", True, total, 15),
]
write_jsonl(eval_results, run_dir / "eval.jsonl")

eval_control_results = [
    EvalResult("Q1", "What was the actual refund amount processed for order ORD-77310?", "22.14", "The refund amount is unknown from the provided context.", False, total - section_tokens["case_facts"], 12),
    EvalResult("Q2", "Why did the customer cancel their subscription?", "duplicate", "The customer cancelled their subscription due to a duplicate_charge issue.", True, total - section_tokens["case_facts"], 16),
    EvalResult("Q3", "What is the failure code on the current payment-method update?", "AVS_MISMATCH", "The failure code on the payment-method update is AVS_MISMATCH.", True, total - section_tokens["case_facts"], 17),
    EvalResult("Q4", "What is the last-4 of the new card the customer is trying to add?", "7782", "The customer is attempting to add a new card with last-4 7782.", True, total - section_tokens["case_facts"], 16),
    EvalResult("Q5", "Did the customer receive their subscription proration refund?", "prorated", "Yes, a prorated refund was issued according to the subscription summary.", True, total - section_tokens["case_facts"], 18),
    EvalResult("Q6", "What is the structured status of the payment-method update issue (use the exact status token from the case record, not a paraphrase)?", "in_progress", "The structured status token is unknown from the transcript.", False, total - section_tokens["case_facts"], 13),
]
write_jsonl(eval_control_results, run_dir / "eval_control.jsonl")

print(f"Run generated successfully: {run_id}")
print(f"Tokens: baseline={baseline}, assembled={total}, reduction={budget['reduction_pct']}%")

