"""Twin v0: schema-exact offline validation of intended payloads against live $metadata.
Fidelity tier: EXACT for schema/refs. Rule semantics arrive in twin v1."""
class TwinValidationError(Exception): ...

class SchemaTwin:
    def __init__(self, metadata: dict):
        # metadata: {"EntityName": {"fields": {"name": {"type":..., "required":bool, "picklist":str|None}}}}
        self.meta = metadata

    def validate_payload(self, entity: str, payload: dict, picklists: dict[str, set] | None = None) -> list[str]:
        errs = []
        ent = self.meta.get(entity)
        if not ent:
            return [f"{entity}: entity not present in $metadata — release drift or wrong product mapping."]
        fields = ent["fields"]
        for fname, spec in fields.items():
            if spec.get("required") and payload.get(fname) in (None, ""):
                errs.append(f"{entity}.{fname}: required by $metadata, missing in intent.")
        for fname, val in payload.items():
            if fname not in fields:
                errs.append(f"{entity}.{fname}: not in $metadata — would be rejected on write.")
                continue
            pl = fields[fname].get("picklist")
            if pl and picklists is not None:
                if val not in picklists.get(pl, set()):
                    errs.append(f"{entity}.{fname}: value {val!r} not in picklist {pl} — orphan reference.")
        return errs
