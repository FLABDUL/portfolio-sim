import csv
from pathlib import Path
import pytest

import ultra_min_portfolio_sim as sim


def write_csv(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


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
    tech = dict(children["TECH"])
    assert tech["AAPL"] == 150.0
    assert tech["MSFT"] == 200.0


def test_end_to_end_emits_when_complete_and_on_change_only(tmp_path: Path):
    # portfolios.csv
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
    # prices.csv (includes an AAPL update)
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "AAPL,173",
            "MSFT,425",
            "NVDA,880",
            "AAPL,174",   # update -> TECH +100; INDUSTRIALS +200
            "FORD,12",
            "TSLA,250",
            "BMW,80",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    # Header present
    assert rows[0] == ["NAME", "PRICE"]

    # Known values
    tech_173 = 100*173 + 200*425 + 300*880   # 366300
    tech_174 = 100*174 + 200*425 + 300*880   # 366400
    autos = 100*12 + 200*250 + 200*80        # 67200
    industrials_after_bmw = 2*tech_174 + 3*autos  # 2*366400 + 3*67200 = 934400

    # Check that TECH shows up after NVDA first time
    assert ["TECH", str(tech_173)] in rows

    # After AAPL update, TECH should show 366400 once (no duplicates)
    # Collect all TECH lines:
    tech_lines = [r for r in rows if r[0] == "TECH"]
    assert ["TECH", str(tech_173)] in tech_lines
    assert ["TECH", str(tech_174)] in tech_lines
    # Ensure no extra duplicates beyond these two values
    assert set(tuple(r) for r in tech_lines) == {
        ("TECH", str(tech_173)),
        ("TECH", str(tech_174)),
    }

    # After final BMW tick, AUTOS and INDUSTRIALS must be present with correct values
    assert ["AUTOS", str(autos)] in rows
    assert ["INDUSTRIALS", str(industrials_after_bmw)] in rows


def test_no_emission_until_all_leaf_prices_known(tmp_path: Path):
    # TECH needs AAPL, MSFT; we'll send only AAPL
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
            "AAPL,10",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    # Only the input line should be present; TECH should NOT appear yet
    assert rows == [
        ["NAME", "PRICE"],
        ["AAPL", "10.0"],
    ]


def test_headers_validated(tmp_path: Path):
    # Bad header in prices.csv should raise
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
        ],
    )
    write_csv(
        tmp_path / "prices.csv",
        [
            "BAD,HEADER",
            "AAPL,10",
        ],
    )
    with pytest.raises(ValueError):
        sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(tmp_path / "out.csv"))
