"""Reading the workbooks a programme actually writes, rather than the ones a compiler wants.

`compile_xlsx` requires `object | external_code | tier` in row 1. Real design authority documents
do not look like that: they carry a title block, a rule statement, a wordmark, and then a header
row with the programme's own column names — `Picklist ID`, `External code`, `Label en_GB`. Asked to
compile the Komatsu design pack, the existing compiler read forty picklists as zero records,
because every sheet failed the convention and skipping is what it does when the convention is
absent.

There are two ways to fix that. Reshape the client's workbooks into the compiler's shape, which
asks a design authority to write for a machine and guarantees the shipped document and the
compiled one drift apart. Or declare the mapping and read what they wrote.

A `Profile` is that declaration: where the header row is, which sheets carry records, and which of
their columns mean what. It is data, so a new programme is a new profile rather than a new parser,
and the mapping is reviewable by the person who owns the workbook.

The compiler still never guesses. A column the profile names and the sheet does not have is a
refusal; a required cell left blank is a decision point, exactly as before.
"""
from dataclasses import dataclass, field

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


class ProfileError(Exception): ...


@dataclass(frozen=True)
class Profile:
    """How to read one shape of workbook."""
    name: str
    #: A column header that identifies the header row wherever it sits. Design documents put a
    #: title, a rule and a wordmark above it, and the row number moves between versions.
    header_contains: str
    #: The IR object every row on these sheets describes.
    object: str
    #: IR `external_code` comes from this column.
    code_column: str
    #: intent key -> column header. Present and blank becomes a decision point.
    intent: dict = field(default_factory=dict)
    #: Sheets to read. Empty means every sheet that has the header row.
    sheets: tuple = ()
    #: Sheets never to read, for the rules and inventory pages that head a design workbook.
    skip_sheets: tuple = ()
    #: Column whose value marks a row as a customisation rather than delivered standard, and the
    #: prefix that means "designed here". A prefix because a design authority qualifies its own
    #: answers — the Komatsu pack says "KOMATSU" and "KOMATSU (statutory codes)", and demanding one
    #: spelling would silently drop the four statutory lists from the delta pool. A contract is
    #: attached to those, which is what the pool counts (ADR-0034, ADR-0041).
    origin_column: str = ""
    designed_prefix: str = ""
    #: A value in the origin column by which the workbook disowns the row — "MDF OBJECT, not a
    #: picklist". The document is telling the compiler this is not the thing, and compiling it
    #: anyway would be the platform overruling the design authority about its own design.
    not_a_record: tuple = ()
    #: Where a contract's owner and consumers come from, when the profile carries them per row.
    owner_column: str = ""
    tier: str = "A"


def _header_row(ws, contains: str) -> tuple[int, dict] | None:
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=12, values_only=True), start=1):
        cols = {str(v).strip(): i for i, v in enumerate(row, start=1) if v is not None}
        if contains in cols:
            return r, cols
    return None


def compile_profiled(path_or_stream, profile: Profile, product: str, system_binding: str,
                     workbook: str, signed_by: str | None = None,
                     date: str | None = None) -> tuple[list[dict], list[str]]:
    """Returns (records, notes). Notes name every sheet skipped and why — a compiler that read
    three of eleven sheets and said nothing would report a third of a design as the whole of it."""
    wb = load_workbook(path_or_stream, data_only=True)
    out: list[dict] = []
    notes: list[str] = []

    for ws in wb.worksheets:
        if ws.title in profile.skip_sheets:
            notes.append(f"{ws.title}: skipped by profile")
            continue
        if profile.sheets and ws.title not in profile.sheets:
            notes.append(f"{ws.title}: not named by profile {profile.name!r}")
            continue
        found = _header_row(ws, profile.header_contains)
        if not found:
            notes.append(f"{ws.title}: no header row containing {profile.header_contains!r}")
            continue
        header_row, cols = found
        if profile.code_column not in cols:
            raise ProfileError(
                f"{ws.title}: profile {profile.name!r} names {profile.code_column!r} as the code "
                f"column and the sheet has {sorted(cols)}. A compiler that guessed which column "
                f"held the key would produce records nobody can trace to a cell.")
        first, last = min(cols.values()), max(cols.values())
        span = f"{get_column_letter(first)}{{r}}:{get_column_letter(last)}{{r}}"
        rows = 0

        for r, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True),
                                start=header_row + 1):
            def cell(name: str) -> str:
                i = cols.get(name)
                if not i or i > len(row) or row[i - 1] is None:
                    return ""
                return str(row[i - 1]).strip()

            code = cell(profile.code_column)
            if not code:
                continue                    # a spacer or a continuation row, not a record

            intent: dict = {"externalCode": code}
            for key, column in profile.intent.items():
                value = cell(column)
                intent[key] = value if value else {
                    "value": None,
                    "decision_point": f"DP-GAP-{ws.title}-{key}-{r}".upper().replace(" ", "_")}

            record = {
                "object": profile.object, "product": product, "system_binding": system_binding,
                "tier": profile.tier, "external_code": code, "intent": intent,
                "source": {"workbook": workbook, "sheet": ws.title,
                           "cell_range": f"{ws.title}!{span.format(r=r)}"},
            }
            if signed_by:
                record["source"]["signed_by"] = signed_by
            if date:
                record["source"]["date"] = date

            # A row the workbook calls designed-here is a customisation, and a customisation is a
            # contract: one writer, declared readers, and one of the delta pool.
            origin = cell(profile.origin_column) if profile.origin_column else ""
            if origin and origin in profile.not_a_record:
                notes.append(f"{ws.title} row {r}: {code} — the workbook says {origin!r}, so it is "
                             f"not compiled as a {profile.object}")
                continue
            if profile.designed_prefix and origin.startswith(profile.designed_prefix):
                owner = cell(profile.owner_column) if profile.owner_column else ""
                record["contract"] = {"owner": owner or f"{profile.object} design authority",
                                      "consumers": []}
            out.append(record)
            rows += 1
        notes.append(f"{ws.title}: {rows} record(s) from row {header_row + 1}")
    return out, notes


@dataclass(frozen=True)
class DecisionProfile:
    """Where a design workbook records the decisions it is waiting on.

    Compiling the Komatsu pack and reading zero open decision points was the worst result of the
    whole exercise: the workbook lists nine, with owners and dates, and the platform reported a
    design with nothing blocking it. A false clean is the one failure mode this platform exists to
    prevent, and it was produced by a compiler that simply did not look at the sheet.
    """
    name: str
    header_contains: str
    id_column: str
    question_column: str
    owner_column: str
    sheets: tuple = ()
    due_column: str = ""
    recommendation_column: str = ""
    #: The workbook states no DP type, and this does not invent one. Everything registers as
    #: DESIGN and every one is reported as unclassified — because a STATUTORY decision needs an
    #: evidence reference to resolve (invariant 5) and one registered as DESIGN does not. Guessing
    #: from the wording would be the platform deciding which of a client's decisions are statutory.
    default_type: str = "DESIGN"


def compile_decisions(path_or_stream, profile: DecisionProfile) -> tuple[list[dict], list[str]]:
    """Returns (decision points, notes). Notes name every one whose type the workbook did not
    state, because that is the difference between a decision that needs evidence and one that
    does not."""
    wb = load_workbook(path_or_stream, data_only=True)
    out, notes = [], []
    for ws in wb.worksheets:
        if profile.sheets and ws.title not in profile.sheets:
            continue
        found = _header_row(ws, profile.header_contains)
        if not found:
            continue
        header_row, cols = found
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            def cell(name: str) -> str:
                i = cols.get(name)
                if not i or i > len(row) or row[i - 1] is None:
                    return ""
                return str(row[i - 1]).strip()

            dp_id = cell(profile.id_column)
            if not dp_id or dp_id == profile.id_column:
                continue
            out.append({"dp_id": dp_id, "dp_type": profile.default_type,
                        "question": cell(profile.question_column),
                        "owner": cell(profile.owner_column),
                        "options": [cell(profile.recommendation_column)]
                                   if profile.recommendation_column and
                                   cell(profile.recommendation_column) else [],
                        "required_by": cell(profile.due_column) if profile.due_column else ""})
    if out:
        notes.append(
            f"{len(out)} decision point(s) registered as {profile.default_type}: the workbook "
            f"states no type. A STATUTORY decision requires a signed evidence reference to resolve "
            f"and one registered as DESIGN does not, so any of these whose answer is a statutory "
            f"value has to be re-typed by a person before it is answered — "
            f"{', '.join(d['dp_id'] for d in out)}.")
    return out, notes


#: The Komatsu SuccessFactors design pack, v1.0. The option-set sheets share one shape; the rules,
#: inventory, impact, crosswalk and decision-point pages are not records and are named as skipped
#: rather than silently ignored.
KOMATSU_PICKLISTS = Profile(
    name="komatsu/picklist-design-v1",
    header_contains="Picklist ID",
    object="PicklistOption",
    code_column="External code",
    intent={"picklist": "Picklist ID", "label_en_GB": "Label en_GB", "country": "Country",
            "status": "Status"},
    skip_sheets=("Design Rules", "Inventory", "Integration Impact", "Crosswalk",
                 "Decision Points"),
)

#: The same pack's inventory page, which is where origin and the approving owner live. Read as its
#: own profile because it describes picklists rather than their values.
KOMATSU_INVENTORY = Profile(
    name="komatsu/picklist-inventory-v1",
    header_contains="Ref",
    object="Picklist",
    code_column="Ref",
    intent={"concept": "Business concept", "scope_item": "Module / scope item",
            "picklist_id": "Picklist ID", "country": "Country scope",
            "cascading": "Cascading"},
    sheets=("Inventory",),
    origin_column="Origin",
    designed_prefix="KOMATSU",
    not_a_record=("MDF OBJECT, not a picklist",),
    owner_column="Owner (approves values)",
)

#: The same pack's own record of what it is waiting on. Nine decisions, with owners and dates.
KOMATSU_DECISIONS = DecisionProfile(
    name="komatsu/picklist-decisions-v1",
    header_contains="DP",
    id_column="DP",
    question_column="Decision required",
    owner_column="Owner",
    due_column="Required by",
    recommendation_column="GONXT recommended position",
    sheets=("Decision Points",),
)
