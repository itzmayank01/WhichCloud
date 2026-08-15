"""Sizing for Azure Managed Redis is read out of the SKU name.

That only works because the Balanced tier is named after its memory. The
classic C-series is not, so the parser must refuse it rather than return a
plausible-looking wrong number.
"""

from whichcloud.pricing.azure import _redis_memory_gb


def test_balanced_skus_carry_their_size_in_the_name():
    assert _redis_memory_gb("B1") == 1.0
    assert _redis_memory_gb("B3") == 3.0
    assert _redis_memory_gb("B250") == 250.0


def test_b0_is_the_half_gigabyte_special_case():
    assert _redis_memory_gb("B0") == 0.5


def test_c_series_is_refused_rather_than_misread():
    # C3 is 6 GB, not 3 GB. Reading the digit would understate it by half and
    # make Azure look cheaper than it is.
    for sku in ("C0", "C1", "C3", "C6"):
        assert _redis_memory_gb(sku) is None


def test_other_families_are_refused():
    for sku in ("A1000", "M2000", "X700", "P3", "", "B", "Bx"):
        assert _redis_memory_gb(sku) is None
