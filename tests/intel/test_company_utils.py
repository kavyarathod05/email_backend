from intel.modules.companies.utils import name_key, slugify


def test_slugify_basic():
    assert slugify("Google") == "google"
    assert slugify("Scale AI") == "scale-ai"
    assert slugify("  JPMorganChase ") == "jpmorganchase"


def test_name_key_dedupes_spacing():
    assert name_key("Scale AI") == name_key("ScaleAI")
    assert name_key("Google") == name_key("google")
    assert name_key("Meta") != name_key("Microsoft")
