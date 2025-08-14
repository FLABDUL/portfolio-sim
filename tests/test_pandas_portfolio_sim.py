import csv
from pathlib import Path

import pytest

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
            f"{sim.COL_NAME},{sim.COL_SHARES}",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )
    portfolios = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    flattened = sim.flatten_to_stocks(portfolios)

    assert flattened["TECH"]["AAPL"] == 100.0
    assert flattened["TECH"]["MSFT"] == 200.0

    df = flattened.to_dataframe()
    assert set(df.columns) == {sim.COL_PORTFOLIO, sim.COL_STOCK, sim.COL_WEIGHT}
    assert {tuple(x) for x in df.values} == {
        ("TECH", "AAPL", 100.0),
        ("TECH", "MSFT", 200.0),
    }


def test_cycle_detection(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            f"{sim.COL_NAME},{sim.COL_SHARES}",
            "A,",
            "B,1",
            "B,",
            "A,1",
        ],
    )
    portfolios = sim.read_portfolios_csv(tmp_path / "portfolios.csv")
    with pytest.raises(sim.CycleDetectedError, match="Cycle detected"):
        sim.flatten_to_stocks(portfolios)


# ---------- Streaming (end-to-end) ----------

def test_streaming_end_to_end_emits_when_complete(tmp_path: Path):
    write_csv(
        tmp_path / "portfolios.csv",
        [
            f"{sim.COL_NAME},{sim.COL_SHARES}",
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
            f"{sim.COL_NAME},{sim.COL_PRICE}",
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
        sim.CSV_HEADER_OUTPUT,
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
    write_csv(
        tmp_path / "portfolios.csv",
        [
            f"{sim.COL_NAME},{sim.COL_SHARES}",
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
            f"{sim.COL_NAME},{sim.COL_PRICE}",
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
            f"{sim.COL_NAME},{sim.COL_SHARES}",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )

    write_csv(
        tmp_path / "prices.csv",
        [
            f"{sim.COL_NAME},{sim.COL_PRICE}",
            "XYZ,10",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    assert rows == [
        sim.CSV_HEADER_OUTPUT,
        ["XYZ", "10.0"],
    ]
