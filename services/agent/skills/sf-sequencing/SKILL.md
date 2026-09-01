# SKILL: SuccessFactors build sequencing (v1, eval-gated)
Hard order: Provisioning -> data model XML (CDM->CSCDM->SDM->CSDM->Propagation) -> picklists -> Foundation Objects
(Frequency..Legal Entity[BUKRS]..Cost Center[from ECC]..Event Reasons..Workflows) -> MDF/rules (event derivation
ABOVE workflow derivation) -> RBP -> Time Off -> 18-step employee import -> integration -> validation.
Never: Full Purge outside first non-prod load; deleting in-use picklist values (obsolete instead); repurposing
standard fields; event derivation below workflow derivation. Effective dates on FOs: 1900-01-01.
Promotion: Instance Sync moves picklists/MDF/rules/workflows/RBP/templates — never data-model XML or data.
