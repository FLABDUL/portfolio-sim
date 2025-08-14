import csv
from pathlib import Path
import pandas as pd
import pytest

# Import updated module
import pandas_portfolio_sim as sim

def write_csv(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

def read_csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))

# ---------- Parsing & flattening ----------

def test_parse_and_flatten_basic(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
    portfolio_collection = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    tech = portfolio_collection["TECH"]
    assert len(tech.components) == 2
    assert any(c.name == "AAPL" and c.shares == 100.0 for c in tech.components)
    assert any(c.name == "MSFT" and c.shares == 200.0 for c in tech.components)

    flattened = sim.flatten_to_stocks(portfolio_collection)
    tech_weights = flattened["TECH"]
    assert tech_weights == {"AAPL": 100.0, "MSFT": 200.0}

    df = flattened.to_dataframe()
    assert set(df.columns) == {"portfolio", "stock", "weight"}
    assert {tuple(x) for x in df.values} == {
        ("TECH", "AAPL", 100.0),
        ("TECH", "MSFT", 200.0),
    }

def test_duplicate_constituents_are_aggregated(tmp_path: Path):
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
    portfolio_collection = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    tech = portfolio_collection["TECH"]
    as_dict = {c.name: c.shares for c in tech.components}
    assert as_dict["AAPL"] == 150.0
    assert as_dict["MSFT"] == 200.0

    flattened = sim.flatten_to_stocks(portfolio_collection)
    tech_weights = flattened["TECH"]
    assert tech_weights["AAPL"] == 150.0
    assert tech_weights["MSFT"] == 200.0

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
    portfolio_collection = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    with pytest.raises(ValueError, match="Cycle detected"):
        sim.flatten_to_stocks(portfolio_collection)

# ---------- Streaming (end-to-end) ----------

def test_streaming_end_to_end_emits_when_complete(tmp_path: Path):
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
    assert rows == [
        ["NAME", "PRICE"],
        ["AAPL", "173.0"],
        ["MSFT", "425.0"],
        ["NVDA", "880.0"],
        ["TECH", "366300"],
        ["FORD", "12.0"],
        ["TSLA", "250.0"],
        ["BMW", "80.0"],
        ["AUTOS", "67200"],
        ["INDUSTRIALS", "934200"],
    ]

def test_streaming_updates_emit_after_complete(tmp_path: Path):
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
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    assert rows[-3:] == [
        ["AAPL", "174.0"],
        ["INDUSTRIALS", "934400"],
        ["TECH", "366400"],
    ]

def test_unrelated_stock_causes_no_portfolio_emission(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
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
    (tmp_path / "prices.csv").write_text("", encoding="utf-8")
    out = tmp_path / "portfolio_prices.csv"
    with pytest.raises(pd.errors.EmptyDataError):
        sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
