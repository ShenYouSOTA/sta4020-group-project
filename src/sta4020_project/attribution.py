"""Where the gap against 1/N comes from.

For one month with target weights w, equal weights e = 1/N, realised returns r
and the Part 1 forecast mu:

    r_p - r_ew = sum_i (w_i - e_i) * r_i

Because both weight vectors sum to one, the cross-sectional mean of r drops
out and the gap splits exactly into

    signal = sum_i (w_i - e_i) * (mu_i - mean(mu))      forecast capture
    timing = sum_i (w_i - e_i) * ((r_i - mean(r)) - (mu_i - mean(mu)))

Signal is the forecast return associated with the tilts. Timing is the residual
from realised returns differing from the forecast. Both are measured
in the same units as the portfolio return, so they add up to the gap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .contracts import DATE


def decompose(weights: pd.DataFrame, expected: pd.DataFrame, realised: pd.DataFrame,
              mapping: pd.Series, *, benchmark_weights: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-month gap decomposition for one model."""
    assets = list(realised.columns)
    rows = []
    for origin, target in mapping.items():
        if origin not in weights.index or target not in realised.index:
            continue
        w = weights.loc[origin].reindex(assets).to_numpy(dtype=float)
        mu = expected.loc[origin].reindex(assets).to_numpy(dtype=float)
        r = realised.loc[target].reindex(assets).to_numpy(dtype=float)
        equal = np.full(len(assets), 1.0 / len(assets))
        if benchmark_weights is not None:
            equal = benchmark_weights.loc[origin, assets].to_numpy(dtype=float)
        eligible = equal > 0
        tilt = w - equal
        mu_centred = mu - mu[eligible].mean()
        r_centred = r - r[eligible].mean()
        rows.append({
            "origin": origin,
            "realised_date": target,
            "portfolio": float(w @ r),
            "benchmark": float(equal @ r),
            "gap": float(tilt @ r_centred),
            "signal": float(tilt @ mu_centred),
            "timing": float(tilt @ (r_centred - mu_centred)),
            "forecast_dispersion": float(mu[eligible].std(ddof=1)),
            "realised_dispersion": float(r[eligible].std(ddof=1)),
        })
    frame = pd.DataFrame(rows).set_index("realised_date").sort_index()
    if not np.allclose(frame["gap"], frame["signal"] + frame["timing"], atol=1e-12):
        raise AssertionError("gap decomposition does not add up")
    return frame


def summarise(decomposition: pd.DataFrame, periods_per_year: int = 12) -> dict:
    """Average monthly contributions, annualised, and their share of the gap."""
    gap = decomposition["gap"].mean() * periods_per_year
    signal = decomposition["signal"].mean() * periods_per_year
    timing = decomposition["timing"].mean() * periods_per_year
    total = abs(signal) + abs(timing)
    return {
        "gap_annualized": gap,
        "signal_annualized": signal,
        "timing_annualized": timing,
        "signal_share": abs(signal) / total if total else float("nan"),
        "gap_hit_rate": float((decomposition["gap"] > 0).mean()),
        "signal_t_stat": _tstat(decomposition["signal"]),
        "timing_t_stat": _tstat(decomposition["timing"]),
        "mean_forecast_dispersion": float(decomposition["forecast_dispersion"].mean()),
        "mean_realised_dispersion": float(decomposition["realised_dispersion"].mean()),
    }


def _tstat(series: pd.Series) -> float:
    deviation = series.std(ddof=1)
    return float(series.mean() / (deviation / np.sqrt(len(series)))) if deviation > 0 else float("nan")


def weight_diagnostics(weights: pd.DataFrame, expected: pd.DataFrame,
                       mapping: pd.Series | None = None) -> pd.DataFrame:
    """Concentration, turnover and forecast alignment of one weight path."""
    assets = [column for column in weights.columns if column in expected.columns]
    rows = []
    previous = None
    for origin in weights.index:
        w = weights.loc[origin].reindex(assets).to_numpy(dtype=float)
        share = w / w.sum()
        hhi = float((share ** 2).sum())
        record = {
            "origin": origin,
            "hhi": hhi,
            "effective_n": 1.0 / hhi,
            "max_weight": float(share.max()),
            "non_zero": int((share > 1e-9).sum()),
            "turnover": float(0.5 * np.abs(share - previous).sum()) if previous is not None else float("nan"),
        }
        if origin in expected.index:
            mu = expected.loc[origin].reindex(assets).to_numpy(dtype=float)
            if mu.std(ddof=1) > 0 and share.std(ddof=1) > 0:
                record["corr_weight_forecast"] = float(np.corrcoef(share, mu)[0, 1])
            else:
                record["corr_weight_forecast"] = float("nan")
        rows.append(record)
        previous = share
    frame = pd.DataFrame(rows).set_index("origin")
    frame.index.name = DATE
    return frame
