

def test_object_storage_requests_are_stored_per_request():
    """REGRESSION-GUARD: Azure publishes blob operations per 10,000, AWS
    publishes them per request, and the estimator multiplies whatever it
    finds by a raw request count.

    Storing the meter rate unchanged billed $12,000 a month of blob writes
    on a workload whose real figure is $1.20 -- four orders of magnitude,
    large enough to make Azure look like the most expensive cloud on earth
    and small enough in the code to miss.
    """
    from decimal import Decimal

    from whichcloud.pricing import azure

    points = {p.sku: p for p in azure.fetch_blob_request_prices("us-east")}
    assert points, "no blob request prices returned"

    for point in points.values():
        assert point.unit == "request"
        # A per-10K rate left unconverted lands near 0.05; a per-request
        # rate is a millionth of a dollar.
        assert point.price_usd < Decimal("0.001")

    # Both providers publish $5 per million writes. If they disagree, one
    # of the two units is wrong.
    put = points["blob:put-requests"].price_usd * Decimal("1000000")
    assert Decimal("4") < put < Decimal("6"), f"${put}/million is not a request rate"
