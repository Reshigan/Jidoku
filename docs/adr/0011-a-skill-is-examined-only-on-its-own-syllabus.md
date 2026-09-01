# ADR-0011: A skill is examined only on its own syllabus

Status: accepted.

Invariant 7 says the agent is always builder, never approver. The promotion gate in
`services/agent/skills.py` is where that invariant meets learning: a skill sitting in the library
does nothing until a human grader records a K5 exam pass, and only then does its text reach the
system prompt. The gate held on the human-grader side and leaked on the grading side.

## What was wrong

Grading ran every skill against the whole scenario bank. Two consequences, both fatal to the gate:

A results file answering *someone else's* questions promoted a skill. Nine scenarios, one skill's
result file recording nine passes, and cutover discipline was certified by an integration question.
The exam examined doctrine the skill does not teach, which is not an exam.

Worse, a skill that no scenario examines scored a vacuous 100% — zero questions, zero failures,
threshold met — and promoted itself into the system prompt. The gate was strictest against skills
somebody had bothered to write questions for.

## The rule

A scenario declares the skill it examines, via a `skill:` key. `_exam_for` grades a skill against
those scenarios and no others. A skill nobody wrote questions for returns an *empty* result rather
than no result: empty cannot pass, and `gate_status` reports it as "no exam scenario certifies this
skill" rather than the generic "never sat the K5 exam", so the two failure modes stay distinguishable
to whoever is reading why the library is silent.

`PASS_THRESHOLD = 0.9` and human grading are unchanged. Autochecks may still only overturn a pass,
never grant one — a model marking its own exam is not governance.

## The exam bank and the library must stay in step

The bank drifted from the library once already: R-502 was tested by K5-007 and taught by nothing, so
that question could only ever be failed for the wrong reason. `test_every_scenario_examines_a_skill_
that_exists_and_teaches_its_rule` expands the skills' declared rule ranges and asserts every scenario
names a real skill and cites a rule that skill teaches. Grown from a real failure, which is where the
exam is supposed to grow from.

## Consequence

All five in-repo skills are currently withheld: no `evals/results/` exists, so none has sat the exam.
That is the gate working, not a defect. The alternatives are a named senior grading them, or an
explicit decision to delete the four T2-draft skills — both human acts.
