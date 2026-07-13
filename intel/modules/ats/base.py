"""ATS provider protocol + registry."""

from __future__ import annotations

from typing import Protocol, TypeVar

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob

T = TypeVar("T")


class ATSProvider(Protocol):
    name: AtsProvider

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        ...


_REGISTRY: dict[AtsProvider, ATSProvider] = {}


def register(cls: type[T]) -> type[T]:
    """Class decorator — stores a singleton instance."""
    instance = cls()  # type: ignore[call-arg]
    _REGISTRY[instance.name] = instance
    return cls


def get_provider(name: AtsProvider | str) -> ATSProvider | None:
    if isinstance(name, str):
        try:
            name = AtsProvider(name)
        except ValueError:
            return None
    return _REGISTRY.get(name)


def all_providers() -> dict[AtsProvider, ATSProvider]:
    return dict(_REGISTRY)
