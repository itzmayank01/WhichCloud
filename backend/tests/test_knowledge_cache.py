"""The knowledge base is parsed once per directory, not once per call.

load_techniques() re-globbed and re-parsed every YAML file on every call.
The hot callers are engine.recommend() and the /techniques route -- and
that route asked for it TWICE in one response, once to count it and once
to serialise it. Measured locally the route went from 97.9ms to 3.6ms;
on the 0.1-CPU plan /techniques was ~4.7s of mostly reparse.

Memoising a function that returns a mutable list is the trap here, so the
mutation test below is the one that matters, not the speed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from whichcloud.knowledge import (
    KnowledgeBaseError,
    _parse_techniques,
    load_techniques,
)


def _doc(tid: str) -> dict:
    return {
        "id": tid,
        "name": "X",
        "category": "compute",
        "summary": "s",
        "savings": {},
        "providers": ["aws"],
    }


def test_the_yaml_is_parsed_once_across_repeated_calls(tmp_path: Path):
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(_doc("one")))
    _parse_techniques.cache_clear()

    first = load_techniques(tmp_path)
    info_after_first = _parse_techniques.cache_info()
    for _ in range(5):
        load_techniques(tmp_path)
    info = _parse_techniques.cache_info()

    assert info_after_first.misses == 1
    assert info.misses == 1, "the knowledge base was re-parsed"
    assert info.hits == 5
    assert [t.id for t in first] == ["one"]


def test_a_caller_that_mutates_what_it_gets_cannot_corrupt_the_cache(tmp_path: Path):
    """The public function hands back a copy. Without that, one caller
    doing `.pop()` would silently shorten the catalog for every later
    caller in the process -- including the engine."""
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(_doc("one")))
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(_doc("two")))
    _parse_techniques.cache_clear()

    got = load_techniques(tmp_path)
    assert len(got) == 2
    got.pop()
    got.append("not a technique")  # type: ignore[arg-type]

    again = load_techniques(tmp_path)
    assert [t.id for t in again] == ["one", "two"]


def test_two_directories_do_not_share_an_entry(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.yaml").write_text(yaml.safe_dump(_doc("from-a")))
    (b / "y.yaml").write_text(yaml.safe_dump(_doc("from-b")))
    _parse_techniques.cache_clear()

    assert [t.id for t in load_techniques(a)] == ["from-a"]
    assert [t.id for t in load_techniques(b)] == ["from-b"]


def test_the_same_directory_spelled_two_ways_shares_an_entry(tmp_path: Path):
    """The key is the resolved path, so `kb` and `kb/../kb` are one entry
    rather than two parses of the same files."""
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "x.yaml").write_text(yaml.safe_dump(_doc("one")))
    _parse_techniques.cache_clear()

    load_techniques(kb)
    load_techniques(tmp_path / "kb" / ".." / "kb")
    info = _parse_techniques.cache_info()
    assert info.misses == 1 and info.hits == 1


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("bad.yaml", "id: [unclosed"),
        ("notamap.yaml", "- just\n- a\n- list\n"),
    ],
)
def test_a_malformed_file_still_raises_on_every_call(
    tmp_path: Path, filename: str, content: str
):
    """lru_cache does not store exceptions. If it did, the first failure
    would be remembered and later callers would get a cached raise -- or
    worse, a half-built catalog."""
    (tmp_path / filename).write_text(content)
    _parse_techniques.cache_clear()

    for _ in range(3):
        with pytest.raises(KnowledgeBaseError):
            load_techniques(tmp_path)


def test_an_empty_directory_still_raises_on_every_call(tmp_path: Path):
    _parse_techniques.cache_clear()
    for _ in range(3):
        with pytest.raises(KnowledgeBaseError, match="no technique files"):
            load_techniques(tmp_path)


def test_a_missing_directory_still_raises_on_every_call(tmp_path: Path):
    _parse_techniques.cache_clear()
    for _ in range(3):
        with pytest.raises(KnowledgeBaseError, match="not found"):
            load_techniques(tmp_path / "nope")


def test_the_real_knowledge_base_still_loads():
    _parse_techniques.cache_clear()
    catalog = load_techniques()
    assert len(catalog) > 10
    assert len({t.id for t in catalog}) == len(catalog), "duplicate technique ids"
