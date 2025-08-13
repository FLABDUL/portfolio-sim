import csv
from pathlib import Path
import pytest

import simple_portfolio_sim as sim


def write_csv(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


# ---------- Parsing & flattening ----------

def test_parse_aggregates_duplicates(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "AAPL,50",
            "MSFT,200",
        ],
    )
    children = sim.read_portfolios_csv(str(tmp_path / "portfolios.csv"))
    # children["TECH"] is a list of (name, qty) — make it a dict for easy asserts
    as_dict = dict(children["TECH"])
    assert as_dict["AAPL"] == 150.0
    assert as_dict["MSFT"] == 200.0

    flat = sim.expand_flattened(children)
    assert flat["TECH"] == {"AAPL": 150.0, "MSFT": 200.0}


def test_cycle_detection(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "A,",
            "B,1",
            "B,",
            "A,1",
        ],
    )
    children = sim.read_portfolios_csv(str(tmp_path / "portfolios.csv"))
    with pytest.raises(ValueError, match="cycle|resolve"):
        sim.expand_flattened(children)


# ---------- End-to-end streaming ----------

def test_stream_emits_when_complete(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
            "NVDA,300",
            "AUTOS,",
            "FORD,100",
            "TSLA,200",
            "BMW,200",
            "INDUSTRIALS,",
            "TECH,2",
            "AUTOS,3",
        ],
    )
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "AAPL,173",
            "MSFT,425",
            "NVDA,880",
            "FORD,12",
            "TSLA,250",
            "BMW,80",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    children = sim.read_portfolios_csv(str(tmp_path / "portfolios.csv"))
    flat = sim.expand_flattened(children)
    sim.stream_and_write(flat, str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    # Exact values (order of portfolio lines per tick is allowed to vary — we check sets)
    assert rows[:4] == [
        ["NAME", "PRICE"],
        ["AAPL", "173.0"],
        ["MSFT", "425.0"],
        ["NVDA", "880.0"],
    ]
    # After NVDA, TECH must appear (value exact)
    assert ["TECH", "366300"] in rows

    # Final tick was BMW; AUTOS and INDUSTRIALS must be present with correct values
    # AUTOS = 100*12 + 200*250 + 200*80 = 67200
    # INDUSTRIALS = 2*366300 + 3*67200 = 934200
    assert ["AUTOS", "67200"] in rows
    assert ["INDUSTRIALS", "934200"] in rows


def test_stream_updates_are_emitted(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
            "NVDA,300",
            "AUTOS,",
            "FORD,100",
            "TSLA,200",
            "BMW,200",
            "INDUSTRIALS,",
            "TECH,2",
            "AUTOS,3",
        ],
    )
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "AAPL,173",
            "MSFT,425",
            "NVDA,880",
            "FORD,12",
            "TSLA,250",
            "BMW,80",
            "AAPL,174",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    children = sim.read_portfolios_csv(str(tmp_path / "portfolios.csv"))
    flat = sim.expand_flattened(children)
    sim.stream_and_write(flat, str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    # After the last tick (AAPL to 174), TECH should be 366400 and INDUSTRIALS 934400
    assert ["AAPL", "174.0"] in rows
    assert ["TECH", "366400"] in rows
    assert ["INDUSTRIALS", "934400"] in rows
