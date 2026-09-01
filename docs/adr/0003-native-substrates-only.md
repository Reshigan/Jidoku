# ADR-0003: Adapters write only through native change substrates; no UI automation
Status: accepted. RPA against SAP UIs is unsupported, release-fragile, and evidentially void (no authorship
trail). Tier maps must declare UI-locked objects as Tier C -> human instruction sheets + extract-diff
verification. Transport system (ABAP), Instance Sync/imports (SF), Terraform/APIs (BTP) are the write paths.
