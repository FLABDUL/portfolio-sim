# tests/test_pandas_portfolio_sim.py

import csv
from pathlib import Path
import pandas as pd
import pytest

# Import functions/classes under test
import pandas_portfolio_sim as sim


def write_csv(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


# ---------- Parsing & flattening ----------

def test_parse_and_flatten_basic(tmp_path: Path):
    # TECH -> 100 AAPL, 200 MSFT
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
    children = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    assert children == {"TECH": [("AAPL", 100.0), ("MSFT", 200.0)]}

    flattened = sim.flatten_to_stocks(children)
    assert flattened == {"TECH": {"AAPL": 100.0, "MSFT": 200.0}}

    df = sim.flattened_to_df(flattened)
    # Ensure DataFrame has expected content
    assert set(df.columns) == {"portfolio", "stock", "weight"}
    assert {tuple(x) for x in df.values} == {
        ("TECH", "AAPL", 100.0),
        ("TECH", "MSFT", 200.0),
    }


def test_duplicate_constituents_are_aggregated(tmp_path: Path):
    # AAPL appears twice; should sum to 150
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
    children = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    # Order of items not guaranteed; convert to dict for assertion
    as_dict = dict(children["TECH"])
    assert as_dict["AAPL"] == 150.0
    assert as_dict["MSFT"] == 200.0

    flattened = sim.flatten_to_stocks(children)
    assert flattened["TECH"]["AAPL"] == 150.0
    assert flattened["TECH"]["MSFT"] == 200.0


def test_cycle_detection(tmp_path: Path):
    # A contains B, B contains A -> cycle
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
    children = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    with pytest.raises(ValueError, match="Cycle detected"):
        sim.flatten_to_stocks(children)


# ---------- Streaming (end-to-end) ----------

def test_streaming_end_to_end_emits_when_complete(tmp_path: Path):
    # Portfolios: TECH and AUTOS, INDUSTRIALS = 2*TECH + 3*AUTOS
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
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    # Header
    assert rows[0] == ["NAME", "PRICE"]

    # After NVDA, TECH should appear (needs AAPL, MSFT, NVDA)
    # After BMW, AUTOS and INDUSTRIALS should appear
    assert rows == [
        ["NAME", "PRICE"],
        ["AAPL", "173.0"],
        ["MSFT", "425.0"],
        ["NVDA", "880.0"],
        ["TECH", "366300"],          # 100*173 + 200*425 + 300*880
        ["FORD", "12.0"],
        ["TSLA", "250.0"],
        ["BMW", "80.0"],
        ["AUTOS", "67200"],          # 100*12 + 200*250 + 200*80
        ["INDUSTRIALS", "934200"],  # 2*366300 + 3*88600
    ]


def test_streaming_updates_emit_after_complete(tmp_path: Path):
    # Same portfolios as above
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
    # Prices: complete both portfolios, then update AAPL
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
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    # Last three lines should reflect the update:
    # delta = +1 on AAPL -> TECH += 100*1 = +100; INDUSTRIALS += 2*100 = +200
    assert rows[-3:] == [
        ["AAPL", "174.0"],
        ["INDUSTRIALS", "934400"],
        ["TECH", "366400"],
    ]


def test_unrelated_stock_causes_no_portfolio_emission(tmp_path: Path):
    # TECH requires AAPL, MSFT
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
    # Price for a stock that no portfolio references
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "XYZ,10",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    # Only the input tick should be present (no TECH emission yet)
    assert rows == [
        ["NAME", "PRICE"],
        ["XYZ", "10.0"],
    ]


def test_prices_must_have_header_and_data(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
        ],
    )
    # Empty prices file should cause pandas to raise EmptyDataError
    (tmp_path / "prices.csv").write_text("", encoding="utf-8")

    out = tmp_path / "portfolio_prices.csv"
    with pytest.raises(pd.errors.EmptyDataError):
        sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
