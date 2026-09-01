"""Seeded data + EDMX for the mock. Realistic enough to catch shape bugs, small enough to read.

S/4 fixtures live here deliberately: the mock must not import the s4hana adapter package.
"""

# --- SuccessFactors -------------------------------------------------------
FOCOSTCENTER = [
    {"externalCode": "CC-1000", "name": "Group Finance", "costcenterManager": "10023",
     "status": "A", "description": "Corporate finance", "cust_region": "EMEA"},
    {"externalCode": "CC-2000", "name": "People Operations", "costcenterManager": "10044",
     "status": "A", "description": "HR shared services", "cust_region": "EMEA"},
    {"externalCode": "CC-3000", "name": "Plant Maintenance", "costcenterManager": None,
     "status": "I", "description": "Decommissioned 2024", "cust_region": "APJ"},
]

PICKLISTV2 = [
    {"id": "ACTIVE_STATUS", "effectiveStartDate": "2020-01-01", "picklistId": "ACTIVE_STATUS",
     "optionId": "A", "externalCode": "A", "label_en_US": "Active"},
    {"id": "ACTIVE_STATUS", "effectiveStartDate": "2020-01-01", "picklistId": "ACTIVE_STATUS",
     "optionId": "I", "externalCode": "I", "label_en_US": "Inactive"},
    {"id": "REGION", "effectiveStartDate": "2020-01-01", "picklistId": "REGION",
     "optionId": "EMEA", "externalCode": "EMEA", "label_en_US": "Europe, Middle East & Africa"},
    {"id": "REGION", "effectiveStartDate": "2020-01-01", "picklistId": "REGION",
     "optionId": "APJ", "externalCode": "APJ", "label_en_US": "Asia Pacific & Japan"},
]

# Time-off objects. Seeded with *other* countries so a ZAF write lands on a real
# tenant rather than an empty one — an empty before-snapshot and a failed read look
# identical on a console, and the demo should not teach the operator to ignore it.
TIMEACCOUNTTYPE = [
    {"externalCode": "ANN_ACC_DEU", "unit": "DAYS", "country": "DEU",
     "accountCreationType": "RECURRING", "bookingStartDate": "2024-01-01"},
    {"externalCode": "SICK_ACC_DEU", "unit": "DAYS", "country": "DEU",
     "accountCreationType": "RECURRING", "bookingStartDate": "2024-01-01"},
]

TIMETYPE = [
    {"externalCode": "ANN_DEU", "timeTypeClass": "ABSENCE", "unit": "DAYS",
     "country": "DEU", "timeAccountType": "ANN_ACC_DEU"},
]

# --- S/4HANA (no s4hana package import — fixtures only) --------------------
A_COSTCENTER = [
    {"CostCenter": "0000100000", "ControllingArea": "1000", "ValidityEndDate": "9999-12-31",
     "ValidityStartDate": "2020-01-01", "CompanyCode": "1000", "CostCenterCategory": "1",
     "CostCtrResponsiblePersonName": "M. Okafor", "CostCenterStandardHierArea": "H1000"},
    {"CostCenter": "0000200000", "ControllingArea": "1000", "ValidityEndDate": "9999-12-31",
     "ValidityStartDate": "2020-01-01", "CompanyCode": "1000", "CostCenterCategory": "2",
     "CostCtrResponsiblePersonName": "L. Petrova", "CostCenterStandardHierArea": "H2000"},
]

A_BUSINESSPARTNER = [
    {"BusinessPartner": "1000001", "BusinessPartnerCategory": "2", "BusinessPartnerName": "Nordwind AG",
     "OrganizationBPName1": "Nordwind AG", "SearchTerm1": "NORDWIND", "BusinessPartnerIsBlocked": False},
    {"BusinessPartner": "1000002", "BusinessPartnerCategory": "1", "BusinessPartnerName": "A. Mbeki",
     "FirstName": "Ayanda", "LastName": "Mbeki", "SearchTerm1": "MBEKI", "BusinessPartnerIsBlocked": False},
]

# key property per collection — the mock needs it for upsert identity and $filter
KEYS = {
    "FOCostCenter": "externalCode",
    "PicklistV2": "id",
    "TimeAccountType": "externalCode",
    "TimeType": "externalCode",
    "A_CostCenter": "CostCenter",
    "A_BusinessPartner": "BusinessPartner",
}


def seed() -> dict[str, list[dict]]:
    """Fresh deep-ish copy so one test's writes never leak into the next."""
    return {
        "FOCostCenter": [dict(r) for r in FOCOSTCENTER],
        "PicklistV2": [dict(r) for r in PICKLISTV2],
        "TimeAccountType": [dict(r) for r in TIMEACCOUNTTYPE],
        "TimeType": [dict(r) for r in TIMETYPE],
        "A_CostCenter": [dict(r) for r in A_COSTCENTER],
        "A_BusinessPartner": [dict(r) for r in A_BUSINESSPARTNER],
    }


METADATA_XML = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices m:DataServiceVersion="2.0"
                    xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
  <Schema Namespace="SFOData" xmlns="http://schemas.microsoft.com/ado/2008/09/edm"
          xmlns:sf="http://www.successfactors.com/edm/sf">
   <EntityType Name="FOCostCenter">
    <Key><PropertyRef Name="externalCode"/></Key>
    <Property Name="externalCode" Type="Edm.String" Nullable="false" MaxLength="32"/>
    <Property Name="name" Type="Edm.String" Nullable="false" MaxLength="255"/>
    <Property Name="description" Type="Edm.String" Nullable="true" MaxLength="255"/>
    <Property Name="costcenterManager" Type="Edm.String" Nullable="true"/>
    <Property Name="status" Type="Edm.String" Nullable="true" sf:picklist="ACTIVE_STATUS"/>
    <Property Name="cust_region" Type="Edm.String" Nullable="true" sf:picklist="REGION"/>
   </EntityType>
   <EntityType Name="PicklistV2">
    <Key><PropertyRef Name="id"/><PropertyRef Name="effectiveStartDate"/></Key>
    <Property Name="id" Type="Edm.String" Nullable="false"/>
    <Property Name="effectiveStartDate" Type="Edm.DateTime" Nullable="false"/>
    <Property Name="picklistId" Type="Edm.String" Nullable="false"/>
    <Property Name="optionId" Type="Edm.String" Nullable="true"/>
    <Property Name="externalCode" Type="Edm.String" Nullable="true"/>
    <Property Name="label_en_US" Type="Edm.String" Nullable="true"/>
   </EntityType>
   <EntityType Name="A_CostCenter">
    <Key><PropertyRef Name="CostCenter"/></Key>
    <Property Name="CostCenter" Type="Edm.String" Nullable="false" MaxLength="10"/>
    <Property Name="ControllingArea" Type="Edm.String" Nullable="false" MaxLength="4"/>
    <Property Name="ValidityEndDate" Type="Edm.DateTime" Nullable="true"/>
    <Property Name="ValidityStartDate" Type="Edm.DateTime" Nullable="true"/>
    <Property Name="CompanyCode" Type="Edm.String" Nullable="true" MaxLength="4"/>
    <Property Name="CostCenterCategory" Type="Edm.String" Nullable="true" MaxLength="1"/>
    <Property Name="CostCtrResponsiblePersonName" Type="Edm.String" Nullable="true"/>
    <Property Name="CostCenterStandardHierArea" Type="Edm.String" Nullable="true"/>
   </EntityType>
   <EntityType Name="A_BusinessPartner">
    <Key><PropertyRef Name="BusinessPartner"/></Key>
    <Property Name="BusinessPartner" Type="Edm.String" Nullable="false" MaxLength="10"/>
    <Property Name="BusinessPartnerCategory" Type="Edm.String" Nullable="false" MaxLength="1"/>
    <Property Name="BusinessPartnerName" Type="Edm.String" Nullable="true"/>
    <Property Name="OrganizationBPName1" Type="Edm.String" Nullable="true"/>
    <Property Name="FirstName" Type="Edm.String" Nullable="true"/>
    <Property Name="LastName" Type="Edm.String" Nullable="true"/>
    <Property Name="SearchTerm1" Type="Edm.String" Nullable="true"/>
    <Property Name="BusinessPartnerIsBlocked" Type="Edm.Boolean" Nullable="true"/>
   </EntityType>
   <EntityContainer Name="SFODataContainer" m:IsDefaultEntityContainer="true">
    <EntitySet Name="FOCostCenter" EntityType="SFOData.FOCostCenter"/>
    <EntitySet Name="PicklistV2" EntityType="SFOData.PicklistV2"/>
    <EntitySet Name="A_CostCenter" EntityType="SFOData.A_CostCenter"/>
    <EntitySet Name="A_BusinessPartner" EntityType="SFOData.A_BusinessPartner"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>
"""
