"""Adapter contract: every SAP product implements exactly this surface.
The tier_map is the honest declaration of what the product's interfaces permit."""
from abc import ABC, abstractmethod


class AdapterError(Exception):
    """An adapter refusing to act, as distinct from an adapter breaking.

    Raised when the IR asks for something the product's interfaces cannot honestly deliver — a
    tier-A object with no declared entity set, a payload the substrate would reject. Every product's
    error type inherits this so the API can map refusals to 422 once, rather than growing an
    `except` clause per adapter and returning a 500 the first time somebody adds a new one.
    """


class Adapter(ABC):
    product: str = "?"
    @abstractmethod
    def tier_map(self) -> dict: ...
    @abstractmethod
    def extract(self, system, entity: str) -> list[dict]: ...
    @abstractmethod
    def build_apply(self, ir_record) -> dict:
        """Tier A -> API payload; Tier B -> file artefact; Tier C -> human instruction sheet."""
    @abstractmethod
    def verify(self, ir_record, live_state: list[dict]) -> dict: ...
