"""Adapter registry: product name -> adapter class.

The IR record's `product` is what binds intent to a substrate, so this map is the single place
the platform decides which code may touch which system. Adding a product means adding a line here
and nothing else — but it also means the product is now executable, so an honest tier_map is the
price of entry.
"""
from .base import Adapter

# ponytail: a dict, not entry-point discovery. Adapters ship in this package; when they ship
# separately, swap this for importlib.metadata entry points.
ADAPTERS: dict[str, type[Adapter]] = {}


def _register():
    from .s4hana import S4Adapter
    from .successfactors import SFAdapter

    for cls in (S4Adapter, SFAdapter):
        ADAPTERS[cls.product] = cls


_register()

__all__ = ["Adapter", "ADAPTERS"]
