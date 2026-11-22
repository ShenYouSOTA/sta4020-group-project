"""Per-field coverage and dispersion report for data/addition/descriptors.pkl.

The descriptors archive ships as a single pickle of OrderedDict[str, Series] with a
(date, asset) MultiIndex and month-end trading-day dates. This script maps those
dates to calendar months, restricts the panel to a target universe and forecast
calendar, and writes a per-field coverage table used to decide which descriptors
are safe to feed the risk and return models.

Coverage and tiers are measured on the forecast calendar.  The risk model also
needs history before the first origin, so the table adds two columns measured
outside that calendar: ``first_valid_month_full`` (first month with any value for
the universe, over the whole file) and ``presample_coverage`` (share of finite
cells from ``--history-start`` up to the month before the first origin).

Usage:
    unzip -o data/addition/descriptors.zip -d "$HOME/.cache/sta4020/"
    .venv/bin/python tools/desc_field_coverage.py \
        --descriptors "$HOME/.cache/sta4020/descriptors.pkl" \
        --universe artifacts/part1/P1_Candidate_Universe.csv \
        --calendar artifacts/part1/P1_Expected_Returns.csv \
        --history-start 2012-10 \\
        --out artifacts/addition/desc_field_coverage.csv
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptors", required=True, help="Path to descriptors.pkl")
    parser.add_argument("--universe", required=True, help="CSV with an Asset column")
    parser.add_argument("--calendar", required=True, help="CSV whose index holds forecast dates")
    parser.add_argument("--out", required=True, help="Destination CSV for the coverage table")
    parser.add_argument(
        "--history-start",
        default="2012-10",
        help="First month of the pre-sample window used for presample_coverage",
    )
    return parser.parse_args()


def to_long(series: pd.Series) -> pd.DataFrame:
    index = series.index
    frame = pd.DataFrame(
        {
            "month": pd.PeriodIndex(index.get_level_values("date"), freq="M"),
            "asset": index.get_level_values("asset"),
            "value": series.to_numpy(),
        }
    )
    return frame.drop_duplicates(["month", "asset"], keep="last")


def field_panel(series: pd.Series, index: pd.MultiIndex) -> pd.DataFrame:
    long = to_long(series).set_index(["month", "asset"])["value"]
    return long.reindex(index).unstack()


def history_stats(
    series: pd.Series, assets: list[str], start: pd.Period, end: pd.Period
) -> tuple[str, float]:
    """First month with any value for the universe, and coverage on [start, end]."""
    long = to_long(series)
    long = long[long["asset"].isin(assets) & np.isfinite(long["value"])]
    first = str(long["month"].min()) if len(long) else ""
    window = pd.period_range(start, end, freq="M")
    inside = long[long["month"].isin(window)]
    coverage = len(inside) / (len(window) * len(assets)) if len(window) else float("nan")
    return first, round(float(coverage), 6)


def tier(row: pd.Series) -> str:
    clean = row["months_zero_dispersion"] == 0 and row["n_inf"] == 0
    if clean and row["coverage"] >= 0.95:
        return "A_direct"
    if clean and row["coverage"] >= 0.90:
        return "B_impute"
    if row["coverage"] >= 0.50:
        return "C_cautious"
    return "D_drop"


def main() -> None:
    args = parse_args()
    with open(args.descriptors, "rb") as handle:
        descriptors = pickle.load(handle)

    calendar = pd.read_csv(args.calendar, index_col=0, parse_dates=True).index
    months = pd.PeriodIndex(calendar, freq="M")
    assets = pd.read_csv(args.universe)["Asset"].tolist()
    index = pd.MultiIndex.from_product([months, assets], names=["month", "asset"])
    history_start = pd.Period(args.history_start, freq="M")
    presample_end = months.min() - 1

    rows = []
    for name, series in descriptors.items():
        panel = field_panel(series, index)
        values = panel.to_numpy(dtype=float)
        observed = panel.notna().any(axis=1)
        dispersion = np.nanstd(values, axis=1, ddof=1)
        first_full, presample = history_stats(series, assets, history_start, presample_end)
        rows.append(
            {
                "field": name,
                "coverage": round(float(np.isfinite(values).mean()), 6),
                "full_months": int((panel.notna().sum(axis=1) == len(assets)).sum()),
                "first_valid_month": str(panel.index[observed][0]) if observed.any() else "",
                "n_inf": int(np.isinf(values).sum()),
                "median_cross_sd": float(np.nanmedian(dispersion))
                if np.isfinite(dispersion).any()
                else None,
                "months_zero_dispersion": int((dispersion[np.isfinite(dispersion)] <= 0).sum()),
                "first_valid_month_full": first_full,
                "presample_coverage": presample,
            }
        )

    table = pd.DataFrame(rows).sort_values("coverage", ascending=False)
    table["tier"] = table.apply(tier, axis=1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)

    counts = table["tier"].value_counts().to_dict()
    print(f"fields={len(table)} assets={len(assets)} months={len(months)}")
    print(f"presample={history_start}..{presample_end}")
    print(f"tiers={counts}")
    print(f"written={out}")


if __name__ == "__main__":
    main()
