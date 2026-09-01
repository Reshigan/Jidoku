"""Honest tier declaration for SuccessFactors, kept as data.

A = SF publishes a real writable OData entity set (SFOData / PLT). Every Tier-A entry names
    that entity set below — the name IS the write target, so a guess here is a live-write bug.
B = no write API; a human loads it through Import & Export Data / a Data Migration template.
C = Admin Center or Provisioning UI only, done by a person. No API exists, and none is faked.

THE HONESTY NOTE (mirrors s4hana's): in SF the *instances* are frequently Tier A while the
*configuration that defines their shape* is not. Concretely:
  - MDF object instances (an object's records) are writable via their generated entity set, but
    the MDF object *definition* (Configuration UI / Manage Data Object Definitions) is not —
    MDF_OBJECT_DEFINITION and the *_CONFIG_UI entries below are Tier C.
  - PickListV2 / PicklistOption values are API-writable; the picklist's *binding* into a field
    (Manage Business Configuration, the succession data model) is not — Tier B/C.
  - Position instances (Position) are Tier A; Position Management *settings* are Tier C.
  - EmpJob / EmpCompensation rows are Tier A; the event reason derivation rules and the
    workflow that gates them are business rules authored in the UI — Tier C.
  - Time account *instances* and time types are Tier A; the accrual rules that create them are
    UI-authored business rules — Tier C.
Master data being writable is not permission to claim its configuration is.

Where the exact entity set name was not certain, the entity is deliberately Tier B or C.
A wrong Tier-A URL is worse than an honest Tier C: the platform would try to write it.
"""

# entity -> the SF OData entity set it writes through. Only Tier-A entities need one.
# (SFOData v2 unless noted; the generic upsert endpoint is /odata/v2/upsert.)
ENTITY_SETS = {
    # --- EC Foundation Objects (legacy FO, exposed as SFOData entity sets) ---
    "FOCompany": "FOCompany",
    "FOBusinessUnit": "FOBusinessUnit",
    "FODivision": "FODivision",
    "FODepartment": "FODepartment",
    "FOCostCenter": "FOCostCenter",
    "FOLocation": "FOLocation",
    "FOLocationGroup": "FOLocationGroup",
    "FOGeozone": "FOGeozone",
    "FOJobCode": "FOJobCode",
    "FOJobFunction": "FOJobFunction",
    "FOPayGrade": "FOPayGrade",
    "FOPayRange": "FOPayRange",
    "FOPayGroup": "FOPayGroup",
    "FOPayComponent": "FOPayComponent",
    "FOPayComponentGroup": "FOPayComponentGroup",
    "FOFrequency": "FOFrequency",
    "FOEventReason": "FOEventReason",
    "FOWorkOrder": "FOWorkOrder",
    "FODynamicRole": "FODynamicRole",
    "FOCorporateAddressDEFLT": "FOCorporateAddressDEFLT",

    # --- Person / Employment (EC employee data) ---
    "PerPerson": "PerPerson",
    "PerPersonal": "PerPersonal",
    "PerEmail": "PerEmail",
    "PerPhone": "PerPhone",
    "PerNationalId": "PerNationalId",
    "PerAddressDEFLT": "PerAddressDEFLT",
    "PerEmergencyContacts": "PerEmergencyContacts",
    "EmpEmployment": "EmpEmployment",
    "EmpJob": "EmpJob",
    "EmpJobRelationships": "EmpJobRelationships",
    "EmpCompensation": "EmpCompensation",
    "EmpPayCompRecurring": "EmpPayCompRecurring",
    "EmpPayCompNonRecurring": "EmpPayCompNonRecurring",
    "EmpWorkPermit": "EmpWorkPermit",
    "EmpGlobalAssignment": "EmpGlobalAssignment",
    "User": "User",

    # --- Position Management (position instances only; settings are Tier C) ---
    "Position": "Position",
    "PositionMatrixRelationship": "PositionMatrixRelationship",

    # --- Picklists (values; the field binding is not Tier A) ---
    "PickListV2": "PickListV2",
    "PicklistOption": "PicklistOption",

    # --- Time Off / Time Sheet (config objects with real MDF-backed entity sets) ---
    "TimeType": "TimeType",
    "TimeAccountType": "TimeAccountType",
    "TimeAccount": "TimeAccount",
    "TimeAccountDetail": "TimeAccountDetail",
    "EmployeeTime": "EmployeeTime",
    "TimeProfile": "TimeProfile",
    "WorkSchedule": "WorkSchedule",
    "WorkScheduleDay": "WorkScheduleDay",
    "HolidayCalendar": "HolidayCalendar",
    "Holiday": "Holiday",
    "EmployeeTimeSheet": "EmployeeTimeSheet",
    "TimeSheetEntry": "TimeSheetEntry",
}

# Key field per entity where it is not externalCode. SF has no universal key either.
KEY_FIELDS = {
    "PerPerson": "personIdExternal",
    "PerPersonal": "personIdExternal",
    "PerEmail": "personIdExternal",
    "PerPhone": "personIdExternal",
    "PerNationalId": "personIdExternal",
    "PerAddressDEFLT": "personIdExternal",
    "PerEmergencyContacts": "personIdExternal",
    "EmpEmployment": "personIdExternal",
    "EmpJob": "userId",
    "EmpJobRelationships": "userId",
    "EmpCompensation": "userId",
    "EmpPayCompRecurring": "userId",
    "EmpPayCompNonRecurring": "userId",
    "EmpWorkPermit": "personIdExternal",
    "EmpGlobalAssignment": "userId",
    "User": "userId",
    "Position": "code",
    "EmployeeTime": "externalCode",
    "TimeAccount": "externalCode",
}

TIER_MAP = {
    # === A: a real writable SFOData entity set exists (named in ENTITY_SETS) ===
    **{e: "A" for e in ENTITY_SETS},

    # A custom MDF object's instances ARE writable, through the entity set SF generates from the
    # object's externalName (cust_<object>). That name is per-tenant, so it cannot be listed here:
    # register the concrete entity in ENTITY_SETS when the tenant's object definition is known.

    # === B: no write API — a human loads a file (Import & Export Data / Data Migration template) ===
    "MDF_OBJECT_DEFINITION_EXPORT": "B",   # definition ships as a CSV a human imports; not writable
    "PICKLIST_IMPORT_FILE": "B",           # legacy picklist import (Picklist Management upload)
    "RBP_PERMISSION_GROUP_MEMBERS": "B",   # group membership loaded via import; group itself is UI
    "COMPETENCY_LIBRARY": "B",
    "JOB_PROFILE_CONTENT": "B",            # JPB content import
    "EC_PAYROLL_WAGE_TYPE_MAPPING": "B",   # PTP/wage type mapping worksheet, loaded by a person
    "PAYROLL_TIME_TYPE_MAPPING": "B",
    "LEGACY_TIME_ACCOUNT_BALANCES": "B",   # opening balances: import, then a recalculation run
    "FORM_TEMPLATE_XML": "B",
    "ROLE_BASED_PERMISSION_MATRIX": "B",   # design workbook -> a person builds the roles in Admin Center
    "TRANSLATION_BUNDLE": "B",

    # === C: Admin Center / Provisioning UI only. A person clicks it. No API. ===
    "MDF_OBJECT_DEFINITION": "C",          # Configuration UI / Manage Data Object Definitions
    "MDF_CONFIGURATION_UI": "C",
    "BUSINESS_RULE": "C",                  # Rule Engine — authored in the UI
    "WORKFLOW_CONFIG": "C",                # Manage Organization, Pay and Job Structures
    "DATA_MODEL_XML": "C",                 # succession data model (Provisioning)
    "COUNTRY_SPECIFIC_DATA_MODEL_XML": "C",
    "CORPORATE_DATA_MODEL_XML": "C",
    "PROVISIONING_SWITCH": "C",            # Provisioning only — partners, not customers, not APIs
    "RBP_PERMISSION_ROLE": "C",            # Manage Permission Roles
    "RBP_PERMISSION_GROUP": "C",           # Manage Permission Groups
    "RBP_TARGET_POPULATION": "C",
    "POSITION_MANAGEMENT_SETTINGS": "C",   # Position Management Settings object, UI-maintained
    "POSITION_ORG_CHART_CONFIG": "C",
    "EVENT_REASON_DERIVATION": "C",        # rule-driven, authored in the UI
    "TIME_OFF_ACCRUAL_RULE": "C",          # accrual/takeover rules are business rules
    "TIME_VALUATION": "C",                 # Time Sheet valuation config
    "ABSENCE_COUNTING_RULE": "C",
    "EC_PAYROLL_POINT_TO_POINT_CONFIG": "C",   # PTP replication config, UI/IPS
    "PAYROLL_SYSTEM_CONFIG": "C",
    "MANAGE_BUSINESS_CONFIGURATION": "C",  # MBC: field/picklist binding — no write API
    "HOME_PAGE_CONFIG": "C",
    "EMAIL_NOTIFICATION_TEMPLATE": "C",
    "PROXY_MANAGEMENT": "C",
    "IPS_PROVISIONING_JOB": "C",
}
