# JIDOKA × RAPID MODEL-COMPANY STACK — FIT ASSESSMENT v1.0
Reference: "Rapid model company implementation plan" (8-week Komatsu approach: Best Practices activation + SA
localisation, EC/Time Off/RCM/ONB, Meridian data platform, 4 weeks build + 4 to go-live) and the consolidated
64-file Greenfield Pack. Question: can JIDOKA configure that stack automatically? Answer per component, honestly.

## 01 — COMPONENT-BY-COMPONENT VERDICT

| Rapid-stack component | JIDOKA capability | Tier / verdict |
|---|---|---|
| **Best-practice activation (Upgrade Center)** | Activation is UI-only — a human clicks it (minutes). JIDOKA's job is everything around it: pre-activation checklist as gated tasks, and the **baseline extract immediately after** (already a hard pre-check on P1-1) diffed against the expected scope-item manifest — genchi genbutsu on what actually landed | Tier C execute, **Tier A verify**. The model-company approach is the MOST JIDOKA-compatible strategy: SAP's activation does the bulk config; JIDOKA proves it and builds only the delta |
| SA localisation country content | Same path: human activates, JIDOKA extracts and diffs vs the SA content manifest; gaps become IR work items automatically | Tier C + automated gap detection |
| Post-activation delta config (picklists, FOs, event reasons w/ country suffixes, ZA time types incl. 36-month sick cycle, country-scoped RBP groups) | The core Tier-A surface: OData/import writes from signed IR, twin-validated, diff-verified | **~75–80% Tier A — yes, automatic** |
| BCUI business rules (event derivation, validations) | Rule authoring is UI-locked; JIDOKA generates rule specs + instruction sheets, verifies by rule-trace probes and extract-diff | Tier C with automated verification |
| CSDM deltas for NAM/BWA/MOZ statutory fields (NUIT, INSS, Omang, SSC) | Generated XML (Git-hashed) + human Provisioning upload + Check Tool gate + diff | Tier C, artefact-automated |
| RCM req/app/offer + ONB process variants & documents | Template XML and variant files generated; two-click human imports; thread-test verification (M1/M2 task packs exist) | Tier B |
| Integration Suite prepackaged content (payroll interfaces, CC replication) | Full API deployment, versioned, replayable | **Tier A — fully automatic** |
| **Meridian (cleansing/transform/load-file production)** | Registers as a STAGING system in the registry; JIDOKA does not replace it in-flight — it wraps it: lineage source→Meridian→target, three-point recon with Meridian as the middle leg, load files consumed as Tier-B artefacts with row-count contracts | Integration, not overlap. DP-R01: post-Komatsu, migration workbench (F5.2) can subsume Meridian's role — a build-vs-keep decision, not an assumption |
| **Mozambique statutory blocks** (annual 22 vs 30 days, maternity 60 vs 90, sick pay 75% vs 50% — conflicting sources, counsel position pending) | This is JIDOKA behaving exactly as designed: STATUTORY DPs block **only the MOZ Time Off subgraph** — the planner's dependency independence lets ZA/NAM/BWA proceed while the blocked branch waits, and the DP ages visibly with a cost-of-delay line | Working as intended — the block is the feature |
| Cross-country design principles (one job catalogue; country suffixes only where statutory meaning differs; never assume ZAR in a rule; NAM work schedules modelled properly) | Encodable two ways: as IR conventions the compiler enforces, and as validators — e.g. a currency-hardcoding detector on rules/reports, a shared-leave-type blocker | Becomes machine-checked design law (codex additions R-608…) |

## 02 — THE HONEST AGGREGATE

**Yes — with the same L3 shape as everywhere else, and a favourable mix.** For this specific stack: roughly
**75–80% of post-activation configuration objects are Tier-A automatic**, the activation itself is minutes of
human clicks wrapped in automated verification, XML/rules are generated-and-verified with human hands in the
middle, and RCM/ONB rides Tier B. Nothing in the rapid stack falls outside the tier model, and nothing in it
required a capability JIDOKA lacks by design.

## 03 — WHAT JIDOKA ACTUALLY DOES TO THE 8 WEEKS

Not primarily write speed — **verification compression and decision-latency visibility**, the two things that
actually kill 8-week plans: the baseline extract + gap diff turns week-one fit-gap from workshops into a report;
the twin kills the UAT rework loop; and the MOZ-style statutory DPs stop being schedule landmines and become
visible, aging, escalating items that block only their own branch. The 8-week plan's real risk was never keying
speed — it was an unverified activation baseline and undecided statutes. JIDOKA attacks exactly those.

## 04 — GAPS NAMED (so the claim stays earned)
1. Upgrade Center activation stays human forever (no API) — wrapped, never replaced.
2. Meridian integration needs the STAGING-role adapter built (small; registry + recon contract).
3. SA localisation coverage is verified by extract, never assumed from marketing — the manifest-diff must be built (E10 item).
4. RCM/ONB template automation is generation-grade today; import stays human.

*goNXT · What Comes Next is Built Here — and here, it is proven. · Rapid Model-Company Fit Assessment*
