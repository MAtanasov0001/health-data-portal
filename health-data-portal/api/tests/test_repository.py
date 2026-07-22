from pathlib import Path

from api.repository import Repository


def test_identifiers_sorted(snapshots_root: Path):
    repo = Repository(snapshots_root)
    assert repo.identifiers() == ["alpha", "beta"]


def test_latest_picks_highest_semver(snapshots_root: Path):
    repo = Repository(snapshots_root)
    latest = repo.latest("alpha")
    assert latest is not None
    assert latest.version == "1.1.0"


def test_get_specific_version(snapshots_root: Path):
    repo = Repository(snapshots_root)
    dv = repo.get("alpha", "1.0.0")
    assert dv is not None and dv.version == "1.0.0"


def test_get_missing_returns_none(snapshots_root: Path):
    repo = Repository(snapshots_root)
    assert repo.get("alpha", "9.9.9") is None
    assert repo.latest("nope") is None


def test_list_latest_one_per_dataset(snapshots_root: Path):
    repo = Repository(snapshots_root)
    items = repo.list_latest()
    assert [i.identifier for i in items] == ["alpha", "beta"]
    assert {i.version for i in items} == {"1.1.0", "1.0.0"}
