# CLAUDE.md — jidoka-adapters
One adapter per SAP product; implement base.Adapter exactly. The tier_map must be HONEST — declare UI-locked
objects as Tier C, never fake a write path (no RPA/DOM automation, ever; see ADR-0003). Adapters are certified
per SAP release: pin the release in the adapter, re-run fixture suites when it changes. SuccessFactors is the
reference: extraction injected (live client or fixtures) so everything tests offline; live writes dry-run by default.
Next adapters (ROADMAP E8): S/4/ECC transport-native (writes go INTO transport requests), BTP via Terraform.
