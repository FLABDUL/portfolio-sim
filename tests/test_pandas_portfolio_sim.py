import csv
from pathlib import Path
import pandas as pd
import pytest

from pandas_portfolio_sim import (
    read_portfolios_csv,
    flatten_to_stocks,
    FlattenedPortfolioCollection,
    PortfolioRuntime,
    COL_NAME, COL_SHARES, COL_PRICE, CSV_HEADER_OUTPUT
)

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
            f"{COL_NAME},{COL_SHARES}",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
    portfolios = read_portfolios_csv(tmp_path / "portfolios.csv")
    flattened = flatten_to_stocks(portfolios)

    assert flattened["TECH"]["AAPL"] == 100.0
    assert flattened["TECH"]["MSFT"] == 200.0

    df = flattened.to_dataframe()
    assert set(df.columns) == {"portfolio", "stock", "weight"}
    assert {tuple(x) for x in df.values} == {
        ("TECH", "AAPL", 100.0),
        ("TECH", "MSFT", 200.0),
    }

def test_cycle_detection(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            f"{COL_NAME},{COL_SHARES}",
            "A,",
            "B,1",
            "B,",
            "A,1",
        ],
    )
    portfolios = read_portfolios_csv(tmp_path / "portfolios.csv")
    with pytest.raises(ValueError, match="Cycle detected"):
        flatten_to_stocks(portfolios)

# ---------- Streaming (end-to-end) ----------

def test_streaming_emits_values(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            f"{COL_NAME},{COL_SHARES}",
            "TECH,",
            "AAPL,10",
            "MSFT,5",
        ]
    )
    write_csv(
        tmp_path / "prices.csv",
        [
            f"{COL_NAME},{COL_PRICE}",
            "AAPL,100",
            "MSFT,50",
        ]
    )
    out = tmp_path / "out.csv"

    from pandas_portfolio_sim import main
    main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    assert rows[0] == CSV_HEADER_OUTPUT
    assert rows[-1][0] == "TECH"
    assert float(rows[-1][1]) == 10*100 + 5*50
