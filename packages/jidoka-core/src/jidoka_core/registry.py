"""System Registry: every source/target system is a first-class object.
SOURCE systems are write-locked at the credential layer — structurally, not by policy text."""
from dataclasses import dataclass, field

ROLES = ("SOURCE_LEGACY", "TARGET", "DEV", "TEST", "PROD", "TWIN", "SANDBOX")
WRITE_FORBIDDEN_ROLES = ("SOURCE_LEGACY", "TWIN")

class RegistryError(Exception): ...
class WriteLockViolation(Exception): ...

@dataclass
class SystemRecord:
    system_id: str
    product: str
    role: str
    environment: str
    connectivity: dict = field(default_factory=dict)
    extraction_profile: dict = field(default_factory=dict)
    owner: str = ""
    change_substrate: str = ""

class SystemRegistry:
    def __init__(self):
        self._systems: dict[str, SystemRecord] = {}
        self._promotion_paths: list[tuple[str, str]] = []

    def register(self, rec: SystemRecord) -> SystemRecord:
        if rec.role not in ROLES:
            raise RegistryError(f"Unknown role {rec.role}")
        if rec.role in WRITE_FORBIDDEN_ROLES and rec.connectivity.get("write_credentials"):
            raise WriteLockViolation(
                f"{rec.system_id}: role {rec.role} may not hold write credentials. "
                f"Register a separate TARGET system if writes are intended.")
        self._systems[rec.system_id] = rec
        return rec

    def get(self, system_id: str) -> SystemRecord:
        if system_id not in self._systems:
            raise RegistryError(f"System {system_id} not registered — bind IR to registered systems only.")
        return self._systems[system_id]

    def assert_writable(self, system_id: str):
        rec = self.get(system_id)
        if rec.role in WRITE_FORBIDDEN_ROLES:
            raise WriteLockViolation(f"Write attempted against {rec.role} system {system_id} — refused.")
        if not rec.connectivity.get("write_credentials"):
            raise WriteLockViolation(f"{system_id} has no write credentials vaulted — Tier-A apply impossible.")

    def add_promotion_path(self, from_id: str, to_id: str):
        self.get(from_id); self.get(to_id)
        self._promotion_paths.append((from_id, to_id))

    def landscape(self) -> dict:
        return {"systems": [vars(s) for s in self._systems.values()],
                "promotion_paths": self._promotion_paths}
