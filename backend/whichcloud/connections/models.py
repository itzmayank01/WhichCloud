"""What a connected account yields, once the provider differences are gone.

Every adapter returns these. The normalisation happens in the adapter,
not the reader, so `billing_line_items` means one thing regardless of
which cloud filled it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

#: What a line was bought under. The gap between unblended and amortized
#: is entirely explained by these, so a report that cannot name them
#: cannot explain the gap either.
PURCHASE_TYPES = ("on_demand", "reserved", "savings_plan", "spot")


@dataclass
class BillingFact:
    """One day, one service, one region, one purchase type.

    Three cost figures rather than one, because a bill is not one number:

      unblended  what the line actually cost that day
      amortized  a commitment's up-front cost spread across its term
      blended    AWS's cross-account average rate

    A reserved instance paid for in January makes January look like a
    disaster and February look free under `unblended`, and looks like
    nothing happened under `amortized`. Both are true answers to
    different questions, so both are kept and the reader chooses.

    Credits and tax are separate from cost rather than folded in: a
    report that can exclude tax has to be able to find it, and folding it
    in at write time makes that impossible afterwards.
    """

    usage_date: date
    service: str
    unblended_usd: Decimal = Decimal(0)
    amortized_usd: Decimal = Decimal(0)
    blended_usd: Decimal = Decimal(0)
    credit_usd: Decimal = Decimal(0)
    tax_usd: Decimal = Decimal(0)
    usage_amount: Decimal = Decimal(0)
    usage_unit: str = ""
    region: str = ""
    resource_type: str = ""
    account_id: str = ""
    purchase_type: str = "on_demand"

    def __post_init__(self) -> None:
        if self.purchase_type not in PURCHASE_TYPES:
            raise ValueError(
                f"{self.purchase_type!r} is not a purchase type "
                f"({', '.join(PURCHASE_TYPES)})"
            )
        # An adapter that reports only unblended is the common case, and
        # leaving amortized at zero would make "amortised" read as a 100%
        # discount rather than as a figure the provider did not supply.
        if self.amortized_usd == 0 and self.unblended_usd != 0:
            self.amortized_usd = self.unblended_usd
        if self.blended_usd == 0 and self.unblended_usd != 0:
            self.blended_usd = self.unblended_usd


@dataclass
class VerifyResult:
    """Whether we can actually read this account, and what we learned."""

    ok: bool
    #: The provider's own id for what we reached. Stored, so a later sync
    #: that reaches a DIFFERENT account is visible rather than silently
    #: blending two accounts' costs into one report.
    account_id: str = ""
    message: str = ""


@dataclass
class SetupStep:
    """One instruction, and the exact text to paste where it goes.

    Connecting a cloud account is the step where most people give up, and
    they give up because the instructions describe a policy instead of
    handing them one. Every step that needs a value carries it.
    """

    title: str
    body: str
    #: A policy document, CLI command or URL, ready to copy. Rendered as
    #: a code block rather than prose.
    snippet: str = ""
    language: str = "text"


@dataclass
class Setup:
    steps: list[SetupStep] = field(default_factory=list)
    #: Said plainly where it is true: this connection means we hold a
    #: credential of theirs. Only Azure sets it.
    stores_secret: bool = False
    #: What the connection can do, in the user's words rather than the
    #: provider's. Shown before they start, not after.
    grants: str = ""
