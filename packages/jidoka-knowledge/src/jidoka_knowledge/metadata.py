"""Turn a system's own service definition into the rows the harvester forms claims from.

An OData $metadata document is DDIC by another name: entity types are tables, properties are
fields with a type and a length, keys are keys, and a property annotated with a picklist or a
value-help names its check table. Parsing it is how JIDOKA learns a product's structure without
reading a word of anyone's documentation.

Stdlib only, like the rest of this package. ElementTree over an XML string, no schema validation:
the point is to read what a real service actually publishes, and real services publish EDMX that
would fail somebody's schema.
"""
import xml.etree.ElementTree as ET

# EDMX carries its version in the namespace URI and SAP publishes both v2 and v4 in the wild, so
# matching on the local tag name is the only thing that works across both. Cheaper than a
# namespace map that has to be right for every service SAP ships.
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _walk(node, name: str):
    for child in node.iter():
        if _local(child.tag) == name:
            yield child


def _attr(el, name: str):
    """Read an attribute regardless of which namespace prefix the vendor put it in."""
    if name in el.attrib:
        return el.attrib[name]
    return next((v for k, v in el.attrib.items() if _local(k) == name), None)


def parse(edmx: str | bytes) -> dict[str, list[dict]]:
    """Split a $metadata document into the entities the harvester asks an adapter for.

    Returns rows under the STRUCTURE_SOURCES names, so `read()` below can serve them straight
    through the ordinary extract() path — the harvester never learns that this particular system
    happened to be described by EDMX rather than by DDIC.
    """
    root = ET.fromstring(edmx)
    tables, fields, domains, checks = [], [], [], []
    seen_domains: dict[str, list[str]] = {}

    for et_el in _walk(root, "EntityType"):
        table = _attr(et_el, "Name")
        if not table:
            continue
        keys = [_attr(k, "Name") for k in _walk(et_el, "PropertyRef")]
        tables.append({"table": table, "key": ", ".join(k for k in keys if k),
                       "description": "an entity published by this service"})
        for prop in _walk(et_el, "Property"):
            field = _attr(prop, "Name")
            if not field:
                continue
            row = {"table": table, "field": field,
                   "datatype": (_attr(prop, "Type") or "").replace("Edm.", "") or None,
                   "length": _attr(prop, "MaxLength"),
                   "nullable": _attr(prop, "Nullable")}
            # A picklist or value-help annotation is a check table: it says this field may only
            # hold what that list holds. Same fact DD03L.CHECKTABLE carries in ABAP DDIC.
            check = _attr(prop, "picklist") or _attr(prop, "ValueList") or _attr(prop, "ValueHelp")
            if check:
                row["check_table"] = check
                checks.append({"field": f"{table}.{field}", "check_table": check})
                seen_domains.setdefault(check, [])
            fields.append(row)

    domains = [{"domain": d, "fixed_values": v} for d, v in sorted(seen_domains.items())]
    return {"tables": tables, "fields": fields, "domains": domains, "check_tables": checks}


def read(edmx: str | bytes, picklists=None):
    """A fetcher for Adapter's `_fetch(system, entity)` slot, backed by a $metadata document.

    `picklists` optionally supplies the option rows for the value sets the document names, which
    is what turns a domain from "this field is constrained" into "these are the permitted values"
    — the fact that makes metadata a better source than a manual, since it is this tenant's
    actual configured set rather than the one SAP shipped.
    """
    parsed = parse(edmx)
    if picklists:
        by_list: dict[str, list[str]] = {}
        for row in picklists:
            name = row.get("picklistId") or row.get("id")
            option = row.get("externalCode") or row.get("optionId") or row.get("label_en_US")
            if name and option is not None:
                by_list.setdefault(str(name), []).append(str(option))
        for d in parsed["domains"]:
            d["fixed_values"] = by_list.get(d["domain"], [])

    def fetch(system, entity: str) -> list[dict]:
        rows = parsed.get(entity)
        if rows is None:
            # The harvester treats a missing entity as "this product has no such interface" and
            # moves on. Raising here would be the same outcome with a worse traceback.
            raise KeyError(entity)
        return rows
    return fetch
