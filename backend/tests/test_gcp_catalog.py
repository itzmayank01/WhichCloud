"""Catalog API parsing and SKU selection.

These cover the mechanism, not the choices. Whether `select_skus` picks the
*right* SKU for object storage can only be settled against live data; what is
settled here is that the price arithmetic is correct and that the filters
exclude what they claim to exclude.
"""

from decimal import Decimal

from whichcloud.pricing.gcp import select_skus, sku_price, sku_unit


def sku(*, desc="thing", price=None, region="asia-south1", family="", group="",
        usage="OnDemand", unit="h"):
    """A SKU in the shape the Catalog API returns."""
    units, nanos = price if price else ("0", 31611000)
    return {
        "skuId": "AAAA-BBBB-CCCC",
        "description": desc,
        "serviceRegions": [region],
        "category": {"resourceFamily": family, "resourceGroup": group, "usageType": usage},
        "pricingInfo": [{"pricingExpression": {
            "usageUnit": unit,
            "tieredRates": [{"startUsageAmount": 0,
                             "unitPrice": {"currencyCode": "USD", "units": units, "nanos": nanos}}],
        }}],
    }


class TestPriceArithmetic:
    def test_nanos_are_part_of_the_price(self):
        # 0.031611 USD arrives as units=0, nanos=31611000. Reading only units
        # would price this at zero.
        assert sku_price(sku(price=("0", 31611000))) == Decimal("0.031611")

    def test_whole_units_and_nanos_combine(self):
        assert sku_price(sku(price=("2", 500000000))) == Decimal("2.5")

    def test_whole_units_alone(self):
        assert sku_price(sku(price=("3", 0))) == Decimal("3")

    def test_a_zero_priced_sku_yields_nothing(self):
        # Free tiers exist in the catalog; they are not a price.
        assert sku_price(sku(price=("0", 0))) is None

    def test_missing_pricing_info_yields_nothing(self):
        assert sku_price({"description": "x"}) is None

    def test_unit_is_read_back(self):
        assert sku_unit(sku(unit="GiBy.mo")) == "GiBy.mo"


class TestSelection:
    def test_region_must_match(self):
        skus = [sku(region="us-east1")]
        assert select_skus(skus, "asia-south1") == []

    def test_global_skus_are_accepted_anywhere(self):
        skus = [sku(region="global")]
        assert len(select_skus(skus, "asia-south1")) == 1

    def test_usage_type_excludes_commitments_and_preemptible(self):
        skus = [sku(usage="Commit1Yr"), sku(usage="Preemptible"), sku(usage="OnDemand")]
        assert len(select_skus(skus, "asia-south1")) == 1

    def test_must_contain_is_required(self):
        skus = [sku(desc="Nearline Storage Mumbai")]
        assert select_skus(skus, "asia-south1", must_contain=("standard storage",)) == []

    def test_must_not_contain_excludes_archive_tiers(self):
        # The S3 mistake in GCP form: archive tiers are cheaper per GB and
        # completely wrong as a default.
        skus = [
            sku(desc="Archive Storage Mumbai"),
            sku(desc="Standard Storage Mumbai"),
        ]
        kept = select_skus(
            skus, "asia-south1",
            must_contain=("standard storage",),
            must_not_contain=("archive", "nearline", "coldline"),
        )
        assert len(kept) == 1
        assert "standard" in kept[0]["description"].lower()

    def test_zero_priced_skus_never_survive_selection(self):
        assert select_skus([sku(price=("0", 0))], "asia-south1") == []

    def test_resource_family_and_group_narrow_further(self):
        skus = [sku(family="Storage", group="RegionalStorage"),
                sku(family="Compute", group="N2Standard")]
        kept = select_skus(skus, "asia-south1", resource_family="Storage")
        assert len(kept) == 1
