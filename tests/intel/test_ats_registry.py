"""ATS provider registry tests."""

from intel.core.models.company import AtsProvider
from intel.modules.ats import all_providers, get_provider
import intel.modules.ats  # noqa: F401 — register all


EXPECTED = {
    AtsProvider.greenhouse,
    AtsProvider.lever,
    AtsProvider.ashby,
    AtsProvider.smartrecruiters,
    AtsProvider.workable,
    AtsProvider.teamtailor,
    AtsProvider.jobvite,
    AtsProvider.workday,
    AtsProvider.bamboohr,
    AtsProvider.rippling,
    AtsProvider.oracle,
    AtsProvider.successfactors,
    AtsProvider.icims,
}


def test_all_requested_providers_registered():
    registered = set(all_providers().keys())
    missing = EXPECTED - registered
    assert not missing, f"Missing providers: {missing}"


def test_each_provider_has_list_jobs():
    for name in EXPECTED:
        p = get_provider(name)
        assert p is not None
        assert callable(getattr(p, "list_jobs", None))
