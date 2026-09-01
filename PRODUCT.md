# PRODUCT.md — goNXT JIDOKA console

## What this is
JIDOKA (自働化 — automation with a human touch) turns signed design intent into verified SAP
configuration under a hash-chained governance ledger. The console (`apps/web`) is the human side
of that contract: consultants, approvers and client signatories watch the line, resolve decision
points, approve plans, and read the ledger. The machine builds; only people approve.

## Register
product — the design serves the task. Dense, governed, trustworthy. Users are SAP consultants and
programme leads in long working sessions; familiarity and state clarity beat spectacle.

## Platform
web (React/Vite SPA, `apps/web`). Desktop-first, dense; collapses to a bottom bar on narrow screens.

## Users
- Consultants (builders): live in Work / Configure / Verify / Intent.
- Approvers & client signatories: live in Decisions / Ledger / Documents. SoD refusals must be
  verbatim and legible — a 403 here is the product working, not an error.
- Programme leads: Line / Milestones / Landscape at a glance.

## Voice
Calm, exact, jidoka-honest. Refusals quoted verbatim. Empty states invite, never apologize.
Milestones are EARNED only. No fake numbers, no decorative optimism.

## Design language — "Aizome & Seal"
Japanese industrial heritage, earned: jidoka and andon are Toyota words; a signed record carries
a seal. Deep aizome indigo ground; vermillion (shu) hanko seal as the mark of signature and
approval; washi-grain surfaces; lamp semantics retained (stop/call/run/idle) in Japanese pigment
hues. Logo: a carved square seal. Full token spec in DESIGN.md once built.

## Non-negotiables surfaced in UI
State comes from the API, never local truth. 403 SoD messages verbatim in the refusal modal.
Open decision points visibly block planning. The agent is always builder, never approver.
