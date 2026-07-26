# Deterministic Strategy Decision State

Strategy decisions are evaluated by a deterministic in-process module. The
module accepts configured rules plus verified report state and returns rule
results together with one Action Readiness value: `ready`, `blocked`, or
`waiting_for_condition`.

Each rule condition is evaluated as `passed`, `failed`, or `blocked`. Missing or
incompatible evidence blocks the rule instead of being inferred. Any blocked
enabled rule prevents a decision candidate, which is intentionally conservative
for missing safety evidence. Triggered blocking rules take precedence, followed
by configured numeric priority.

A `ready` result is only a Decision Candidate. Human approval is always required
and the system does not generate or execute orders. GPT tasks may explain rule
results and missing evidence, but they must not create or modify strategy rules.

Action sizing is a separate deterministic step. It accepts only a Decision
Candidate, a configured Daily Investment Budget, and a matching Action Sizing
Policy, and returns Execution Readiness plus an optional proposed amount. A
missing sizing policy or budget blocks that step without changing the rule
condition result; even a sized candidate is never execution authorization.

Daily Action Readiness, candidate action, candidate symbol, triggering rule,
rule states, and reasons are persisted in `decision_states`. Re-running a date
updates that day's snapshot; later dates remain queryable as decision-state
history.
