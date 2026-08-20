"""Module 4. Recovery objectives and regulation, both by lookup.

Neither of these may be free-written. An RTO invented to sound reassuring
is a promise nobody checked, and a regulation invented to sound thorough
is worse -- it is checkable, and citing HIPAA at an Indian hospital is the
kind of error that destroys trust in everything else on the page.
"""

from __future__ import annotations

#: Keyed on what the architecture actually contains, most protective first.
#: Each entry is (predicate over the component set, rto, rpo).
def objectives(
    *,
    multi_instance: bool,
    multi_az_database: bool,
    cross_region_copy: bool,
    warm_standby: bool = False,
) -> dict[str, str]:
    """RTO and RPO derived from components, never asserted."""
    if warm_standby:
        local = {"rto": "1-2 min", "rpo": "~5 min"}
        region = {"region_rto": "<15 min", "region_rpo": "~5 min"}
    elif multi_instance and multi_az_database:
        local = {"rto": "1-2 min", "rpo": "~5 min"}
        region = (
            {"region_rto": "2-6 h", "region_rpo": "= copy interval"}
            if cross_region_copy
            else {"region_rto": "not survivable", "region_rpo": "total"}
        )
    else:
        local = {"rto": "30-120 min", "rpo": "= backup interval"}
        region = (
            {"region_rto": "2-6 h", "region_rpo": "= copy interval"}
            if cross_region_copy
            else {"region_rto": "not survivable", "region_rpo": "total"}
        )
    return {**local, **region}


#: (country, sector) -> obligations. Table lookup only. A pair absent from
#: this table yields no regulation names, which is the correct output when
#: nothing is known -- not an invitation to guess one.
RULES: dict[tuple[str, str], tuple[dict[str, str], ...]] = {
    ("IN", "healthcare"): (
        {
            "regulation": "Digital Personal Data Protection Act 2023",
            "obligation": "Health data is sensitive personal data: it must be "
                          "protected against unauthorised access and its "
                          "processing must be auditable.",
            "control": "Encryption at rest (KMS), TLS 1.2+ in transit (ACM), "
                       "access and API audit retention (CloudTrail, flow logs).",
        },
        {
            "regulation": "IT Act s43A / SPDI Rules 2011",
            "obligation": "Reasonable security practices for sensitive "
                          "personal data, demonstrable on request.",
            "control": "Documented encryption, least-privilege access, and "
                       "retained audit records.",
        },
        {
            "regulation": "ABDM Health Data Management Policy",
            "obligation": "Health records are held with consent and an "
                          "auditable trail of who accessed what.",
            "control": "Immutable audit storage (S3 Object Lock) and "
                       "per-access logging.",
        },
        {
            "regulation": "EHR Standards 2016",
            "obligation": "Electronic health records are retained and remain "
                          "retrievable for their statutory life.",
            "control": "Lifecycle-tiered retention with a cross-region copy "
                       "held inside India.",
        },
    ),
    ("IN", "fintech"): (
        {
            "regulation": "RBI Storage of Payment System Data directive",
            "obligation": "Payment system data must be stored only in India.",
            "control": "Region pinning enforced by a service control policy "
                       "denying every region outside India.",
        },
        {
            "regulation": "Digital Personal Data Protection Act 2023",
            "obligation": "Personal data is protected and its processing "
                          "auditable.",
            "control": "Encryption at rest (KMS) and retained audit records.",
        },
    ),
    ("US", "healthcare"): (
        {
            "regulation": "HIPAA Security Rule",
            "obligation": "Technical safeguards for electronic protected "
                          "health information.",
            "control": "Encryption at rest and in transit, audit controls, "
                       "and access records retained.",
        },
    ),
}

#: Applies to any sector in these countries.
_ANY_SECTOR: dict[str, tuple[dict[str, str], ...]] = {
    "DE": (
        {
            "regulation": "GDPR",
            "obligation": "Personal data is processed lawfully, kept inside "
                          "the EEA unless adequacy applies, and breaches are "
                          "reportable within 72 hours.",
            "control": "Region pinning, encryption at rest, and audit "
                       "retention sufficient to evidence a breach.",
        },
    ),
}
for _eu in ("FR", "IE", "NL", "ES", "IT"):
    _ANY_SECTOR[_eu] = _ANY_SECTOR["DE"]


def compliance_notes(country: str, sector: str) -> list[dict[str, str]]:
    """Obligations for this pair, or an empty list. Never a guess."""
    notes = list(RULES.get((country, sector), ()))
    notes.extend(_ANY_SECTOR.get(country, ()))
    return notes
