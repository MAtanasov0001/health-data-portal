from ingestion import disclosure
from ingestion.models import DisclosureSpec


def _spec() -> DisclosureSpec:
    return DisclosureSpec(
        measure_column="n", dimension_columns=["region", "group"], min_cell_size=5
    )


def _row(region: str, group: str, n: object) -> dict[str, object]:
    return {"region": region, "group": group, "n": n}


def test_primary_suppression_below_threshold():
    # Клетките са в различни региони/групи → няма група с точно едно потискане, значи няма
    # вторично потискане; проверяваме чисто първичното.
    rows = [_row("A", "x", 3), _row("B", "y", 20)]
    out, report = disclosure.apply(rows, _spec())
    assert report.primary_suppressed == 1
    assert report.secondary_suppressed == 0
    assert out[0]["n"] is None
    assert out[1]["n"] == 20


def test_marker_is_suppressed():
    rows = [_row("A", "x", "<5"), _row("B", "y", 20)]
    out, report = disclosure.apply(rows, _spec())
    assert report.primary_suppressed == 1
    assert out[0]["n"] is None


def test_secondary_suppression_protects_single_cell_via_total():
    # В регион A има точно една първично потисната клетка (x=3) сред три → пада и втора най-малка
    # (y=8), за да не се възстанови чрез сумата на региона.
    rows = [_row("A", "x", 3), _row("A", "y", 8), _row("A", "z", 20)]
    out, report = disclosure.apply(rows, _spec())
    assert report.primary_suppressed == 1
    assert report.secondary_suppressed >= 1
    by_group = {r["group"]: r["n"] for r in out}
    assert by_group["x"] is None
    assert by_group["y"] is None
    assert by_group["z"] == 20


def test_no_secondary_when_no_primary():
    rows = [_row("A", "x", 10), _row("B", "y", 8)]
    out, report = disclosure.apply(rows, _spec())
    assert report.total_suppressed == 0
    assert all(r["n"] is not None for r in out)


def test_input_not_mutated():
    rows = [_row("A", "y", 3)]
    disclosure.apply(rows, _spec())
    assert rows[0]["n"] == 3


def test_linked_measure_hidden_with_primary():
    # Свързаната мярка се скрива синхронно с потиснатата основна мярка.
    spec = DisclosureSpec(
        measure_column="n",
        dimension_columns=["region", "group"],
        min_cell_size=5,
        linked_measures=["cases"],
    )
    rows = [
        {"region": "A", "group": "x", "n": 3, "cases": 40},
        {"region": "B", "group": "y", "n": 20, "cases": 50},
    ]
    out, report = disclosure.apply(rows, spec)
    assert report.primary_suppressed == 1
    assert out[0]["n"] is None
    assert out[0]["cases"] is None  # свързаната мярка също е скрита
    assert out[1]["n"] == 20
    assert out[1]["cases"] == 50
