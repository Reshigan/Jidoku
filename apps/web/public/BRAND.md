# goNXT JIDOKA — Brand & Interface System v1.0

## The mark
A signal tower (andon lamp stack): three lamps — red, amber, green — with a royal-blue spine running through them.
The spine is the goNXT thread; the lamps are the line's true state. Reads at 16px as a favicon, at 44px in the rail,
and can be enlarged for print. Kanji 自働化 sits as a quiet subtitle, never as the primary mark.

## Lockup
`goNXT JIDOKA 自働化` — "go" white (or navy on light), "NXT" royal blue #2B50E2, "JIDOKA" in the condensed display
face with wide letterspacing, kanji in muted grey at 60% of the wordmark size. Never set JIDOKA without goNXT.

## Palette — factory floor, not dashboard
| Role | Hex | Use |
|---|---|---|
| Floor | #0E1116 | Page ground. Charcoal of a machine shop at night — never pure black |
| Floor 2 / 3 | #151A22 / #1C222C | Cards, controls |
| Line | #28313E | Borders, rules |
| Lamp run | #3FB950 | Earned, verified, passing |
| Lamp call | #E3A008 | Waiting on a person |
| Lamp stop | #E5484D | Halted, blocked, refused |
| goNXT blue | #2B50E2 | Brand thread, primary actions, forecast data |
| Navy | #0A1245 | Mark ground, print surfaces |
Lamp colours are desaturated deliberately so they read as glass under power, not neon.

## Type
- **Display** Archivo Narrow (condensed grotesque) — factory signage. Headlines, big earned figures, the wordmark.
- **Body** Poppins — the goNXT house geometric sans.
- **Data** JetBrains Mono — hashes, timestamps, references, axis labels. Letterspaced caps for eyebrows.
The condensed display face against the geometric body is the deliberate pairing: signage over document.

## The signature element
The **andon rail**: a fixed lamp column, one lamp per build phase, always visible, never scrolled away — plus a
**stop cord** any user can pull. Toyota's rule made literal: anyone may halt the line, and the halt requires a
reason, which is logged. No enterprise platform gives every user a stop button. This one does, and it is the
brand's whole argument in one control.

## Interface voice
Plain, active, specific. Errors state what happened and what to do; they never apologise and never blur.
Refusals explain the rule and the way forward ("Ask a second qualified reviewer"). Never name internals in the UI —
"waiting on a person", not "PENDING_APPROVAL". Numbers are earned, so they are stated flatly, including bad ones.

## Edge cases the interface handles
Loading (skeleton, no fake data) · empty engagement (invitation, not apology) · offline (last verified state,
writes disabled) · broken chain (approvals suspended, red banner) · line stopped (all lamps red, reason shown) ·
blocked station (statutory DP, explains what releases it) · missing snapshot (execution refused) · SoD violation
(refusal modal, logged) · rollback without reason (refused) · statutory value without signed source (refused) ·
over-capacity approver (amber in analytics) · long text (truncated with full value in title) · keyboard (1–5 view
switch, visible focus, Escape closes modals) · reduced motion (all animation disabled) · mobile (rail becomes a
bottom bar).

*goNXT · What Comes Next is Built Here — and here, it is proven.*
