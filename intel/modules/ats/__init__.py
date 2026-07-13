"""Load all ATS providers into registry."""

from intel.modules.ats.base import all_providers, get_provider, register
from intel.modules.ats.providers import (  # noqa: F401
    ashby,
    bamboohr,
    greenhouse,
    icims,
    jobvite,
    lever,
    oracle,
    rippling,
    smartrecruiters,
    successfactors,
    teamtailor,
    workday,
    workable,
)

__all__ = ["all_providers", "get_provider", "register"]
