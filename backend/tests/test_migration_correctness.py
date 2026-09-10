"""A lift-and-shift must not be recommended hardware it cannot run on.

The defect these lock down was the only one in the coverage map where
acting on the output risked infrastructure that would not start, rather
than infrastructure that cost the wrong amount:

    "We run 40 virtual machines ... a mix of Windows and Linux ...
     move them to the cloud as-is"

  * "40" had no field to land in, so the one figure that should have
    sized the entire plan was discarded on the way in -- not
    underestimated, discarded.
  * `_X86_REQUIRED` needed the literal phrase "windows server". Bare
    "Windows" did not match, so `requires_x86` stayed False and the
    engine recommended Graviton -- for legacy Windows images that do not
    run on ARM at all.

Both are checked here against the CONSTRAINTS layer, with no model call:
these are rules about what the engine does with a reading, and mixing a
live extraction into them would make the test measure the model instead.
"""

from __future__ import annotations

import pytest

from whichcloud.constraints import Constraints
from whichcloud.llm_extract import _force_x86_where_required


# ── the forcing rule ─────────────────────────────────────────────────


@pytest.mark.parametrize("os_value", ["windows", "mixed"])
def test_windows_anywhere_in_the_estate_forces_x86(os_value):
    """"A mix of Windows and Linux" is still Windows. The mixed case is
    the one that actually bit: it reads as partly fine, and a plan that
    moves the Linux half to ARM has silently dropped the other half."""
    c = Constraints(source_os=os_value, cpu_architecture="arm_ok")
    _force_x86_where_required(c)
    assert c.cpu_architecture == "x86_required"
    assert c.requires_x86()
    # The constraint has to be arguable, not merely obeyed.
    assert c.forced_x86_reason


def test_the_model_cannot_talk_the_engine_out_of_x86():
    """The model is asked for cpu_architecture but is not trusted to hold
    the line -- it returned arm_ok for Windows estates. The OS decides."""
    c = Constraints(source_os="windows", cpu_architecture="arm_ok")
    _force_x86_where_required(c)
    assert c.cpu_architecture == "x86_required"


def test_linux_is_left_alone_rather_than_forced_either_way():
    """The rule may only ever TIGHTEN. A Linux estate that nobody said
    anything about stays `unknown` -- which is not permission to use ARM,
    and is also not a bar. Inventing `arm_ok` here would be the same
    silent default in the opposite direction."""
    c = Constraints(source_os="linux", cpu_architecture="unknown")
    _force_x86_where_required(c)
    assert c.cpu_architecture == "unknown"
    assert not c.requires_x86()


def test_unknown_os_is_never_promoted_to_arm_ok():
    c = Constraints(source_os="unknown", cpu_architecture="unknown")
    _force_x86_where_required(c)
    assert c.cpu_architecture == "unknown"
    assert not c.requires_x86()


# ── INV-15, at the invariant level ───────────────────────────────────


def test_inv15_catches_an_arm_family_under_x86_required():
    """The invariant reads the SKUs the estimate actually selected, not
    the spec flag the planner intended -- only the first reaches a user."""
    from tests.run_harness import _ARM_FAMILY

    for arm in ("t4g.medium", "m7g.large", "c7gn.xlarge", "x2gd.large",
                "im4gn.large", "db.t4g.micro", "g5g.xlarge"):
        assert _ARM_FAMILY.match(arm), f"{arm} should read as ARM"

    for x86 in ("t3a.medium", "m5.large", "c6i.xlarge", "db.m5.large",
                "r5b.large", "g5.xlarge", "m6a.large"):
        assert not _ARM_FAMILY.match(x86), f"{x86} should NOT read as ARM"


def test_graviton_naming_rule_distinguishes_amd_from_arm():
    """t3a is AMD and t4g is Graviton, and the only difference is one
    letter after the generation digit. Getting this backwards would
    recommend ARM to every x86-only workload while looking correct."""
    from tests.run_harness import _ARM_FAMILY

    assert _ARM_FAMILY.match("t4g.small")
    assert not _ARM_FAMILY.match("t3a.small")
