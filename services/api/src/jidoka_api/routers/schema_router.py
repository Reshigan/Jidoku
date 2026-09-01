from fastapi import APIRouter
from jidoka_core.schema import IR_SCHEMA, IR_SCHEMA_VERSION

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("/ir")
def ir_schema():
    """The published IR schema. Versioned so a workbook can declare which contract it compiled against."""
    return {"version": IR_SCHEMA_VERSION, "schema": IR_SCHEMA}
