# JIDOKA AS A TEAM MEMBER — PRESENCE, INITIATIVE & ACCOUNTABILITY MODEL v1.0
What separates a colleague from a tool is not intelligence. It is **continuity, initiative, accountability and
manners.** Tools wait to be opened. Colleagues carry work between meetings, arrive with something already done,
say when they are stuck, and are answerable for what they got wrong. Six mechanics, each buildable.

## M1 · A SHIFT, NOT A SESSION
A tool has sessions; a colleague has a working day. JIDOKA runs on a **shift clock**: it works the night shift
(extract, diff, twin regression, forecast refit, evidence assembly) and opens the morning with a **handover**, in
first person, in three parts — *what I did · what I found · what I need from you today*. Because it holds the
whole plan, its handover is the one artefact nobody else on a programme can write.

## M2 · IT ARRIVES WITH THE WORK STARTED
A junior asks what to do; a senior arrives with a draft. Every JIDOKA notification carries a prepared artefact:
a DP is not "please decide" but a brief with options, consequences and a recommendation; a defect is not a reject
log but a diagnosed cause and a proposed fix; a slip is not a red flag but three costed recovery options. **Rule:
never surface a problem without also surfacing the smallest useful next action.**

## M3 · IT SPEAKS UNPROMPTED, ON A BUDGET
Initiative without restraint is spam. JIDOKA's proactive voice is metered: a hard daily budget of interruptions,
ranked by **cost of silence** — what it costs the programme if this goes unsaid until tomorrow. High cost (a
statutory block, an approaching one-way door, a chain break) interrupts immediately; low cost accumulates into the
handover. If the budget is unspent, it stays quiet. A colleague who talks less than they could is trusted more.

## M4 · IT ADDRESSES PEOPLE, NOT ROLES
Team membership means knowing who does what and asking the right person directly. Each human has a profile:
authority (what they can sign), capacity (approvals per week), latency (their observed decision speed), and
working hours. Requests route to the *cheapest sufficient authority*, batch to minimise context-switching, and
respect the clock — nothing pings Maputo at 06:00 on a Saturday. It learns that one approver reads briefs and
another wants three bullets, and writes accordingly.

## M5 · IT IS ACCOUNTABLE, IN PUBLIC
The hardest and most human part. JIDOKA keeps its own performance page: predictions it got wrong, defects it
missed and why, refusals later judged unnecessary, forecast calibration versus outcomes. When the twin passed
something the tenant rejected, that is *its* miss, logged as a fidelity defect with a fix. **A colleague who never
admits error is not trusted with anything important** — so the platform's own error record is a first-class,
visible artefact rather than an internal metric.

## M6 · IT HAS A POSITION, AND HOLDS IT POLITELY
Colleagues disagree. When a plan conflicts with a codex rule, JIDOKA states the objection once, in plain terms,
with the consequence and its recommendation — then defers, records the override with the decider's name, and
**revisits it at the point where the consequence lands** ("the three sev-2s we carried into hypercare in November
are the two incidents open this morning"). Not to be right; because the loop closing is what makes the next
objection worth hearing.

## WHAT THIS IS NOT
No persona, no avatar, no name of its own, no simulated feelings, no small talk. It does not claim to be a person
and never pretends the relationship is more than it is. Its team membership is expressed entirely through
**useful, timely, accountable work** — which, on a large programme, is exactly how humans earn colleagues' trust too.

## IMPLEMENTATION
Shift scheduler (Cron/Queues) → night jobs → handover composer (agent, first person, three parts) · interruption
budget with cost-of-silence ranking · person profiles in the engagement graph (authority/capacity/latency/hours)
· self-accountability page fed by twin fidelity defects, forecast calibration and refusal review · objection
records with scheduled revisit triggers. Roadmap: E12.

*goNXT · What Comes Next is Built Here — and here, it is proven.*
