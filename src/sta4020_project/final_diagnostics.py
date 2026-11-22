"""Matched forecast, calibration and attribution tables for the final runs."""

import numpy as np
import pandas as pd
from scipy.stats import chi2

from .cli import BENCHMARK, monthly_risk_free
from .contracts import read_covariance_panel, read_wide, target_dates
from .stats import circular_block_bootstrap_mean, hac_regression, newey_west_tstat
from .styles import STYLES
from .tradability import DELISTED_ASSET, DELISTED_FROM, load_eligibility

MVO = "Mean-Variance Optimization"
BL = "Black-Litterman"


def table(report, name):
    return pd.read_csv(report / "tables" / f"{name}.csv", index_col=0)


def prediction_comparison(expected_dir, actual, data, origins, output):
    raw = pd.read_csv(expected_dir / "descriptor_coverage.csv", index_col="Formation")
    coverage = raw.drop(columns=["DescriptorMonth", "Eligible"]).mean(axis=1)
    coverage.index = pd.PeriodIndex(coverage.index, freq="M")
    eligibility = load_eligibility(data, origins, actual.columns)
    fresh = read_wide(expected_dir / "signal_eligibility.csv").astype(bool)
    matched = eligibility & fresh
    mapping = target_dates(origins, actual.index)
    outcomes = actual.loc[mapping].set_axis(origins).where(matched)
    ic = pd.DataFrame({
        name: read_wide(expected_dir / f"{name}.csv").where(matched)
        .corrwith(outcomes, axis=1, method="spearman")
        for name in ("historical", "fm", "extended")
    })
    if ic.isna().any().any():
        raise ValueError("Rank IC is undefined on the common monthly cross-section")
    ic["n_assets"] = matched.sum(axis=1)
    ic["descriptor_coverage"] = coverage.loc[origins.to_period("M")].to_numpy()
    high = ic["descriptor_coverage"] >= ic["descriptor_coverage"].median()
    summary = pd.DataFrame({
        "mean_rank_ic": ic[["historical", "fm", "extended"]].mean(),
        "icir": ic[["historical", "fm", "extended"]].mean() / ic[["historical", "fm", "extended"]].std(),
        "high_coverage_rank_ic": ic.loc[high, ["historical", "fm", "extended"]].mean(),
    })
    gain = ic["extended"] - ic["fm"]
    interval = circular_block_bootstrap_mean(gain)["mean_ci"]
    selection = {
        "ic_gain": float(gain.mean()), "ic_gain_ci95": interval,
        "high_coverage_ic_gain": float(gain[high].mean()),
        "high_coverage_months": int(high.sum()),
        "coverage_threshold": float(ic["descriptor_coverage"].median()),
        "minimum_matched_assets": int(ic["n_assets"].min()),
    }
    summary.to_csv(output / "return_forecasts.csv")
    ic.to_csv(output / "monthly_ic.csv")
    return selection


def executed(report, model, origins, assets):
    weights = read_wide(report / "tables" / f"executed_{model.replace('/', '_')}.csv")
    if not weights.index.equals(origins) or set(weights.columns) != set(assets):
        raise ValueError(f"{model}: executed weights do not match the common calendar and assets")
    values = weights[assets].to_numpy()
    if (values < -1e-10).any() or not np.allclose(values.sum(axis=1), 1.0, rtol=0, atol=1e-10):
        raise ValueError(f"{model}: executed weights violate full investment or long-only constraints")
    return values


def calibration(variance, realised, rf):
    squared = (realised - rf) ** 2
    normalized_error = squared / variance - 1
    fit, _, covariance = hac_regression(np.column_stack([np.ones(len(variance)), variance]), squared)
    difference = fit - [0, 1]
    wald = difference @ np.linalg.solve(covariance, difference)
    bias = newey_west_tstat(normalized_error)
    centered = normalized_error - normalized_error.mean()
    autocorrelations = np.array([centered[lag:] @ centered[:-lag] / (centered @ centered)
                                for lag in range(1, 7)])
    n = len(variance)
    ljung_box = n * (n + 2) * np.sum(autocorrelations ** 2 / (n - np.arange(1, 7)))
    return {
        "predicted_vol": np.sqrt(12 * variance.mean()),
        "realized_gross_vol": np.std(realised, ddof=1) * np.sqrt(12),
        "mean_variance_ratio": squared.mean() / variance.mean(),
        "qlike": np.mean(np.log(variance) + squared / variance),
        "mz_intercept": fit[0], "mz_slope": fit[1], "mz_joint_p": chi2.sf(wald, 2),
        "normalized_error": bias["mean"], "bias_Q": bias["t_statistic"] ** 2,
        "bias_p": bias["p_value"], "ljung_box_Q6": ljung_box, "ljung_box_p": chi2.sf(ljung_box, 6),
    }


def risk_comparison(risk_runs, final_report, expected, actual, data, output):
    origins, assets = expected.index, expected.columns.tolist()
    mapping = target_dates(origins, actual.index)
    outcomes = actual.loc[mapping, assets].to_numpy()
    rf = monthly_risk_free(data / "risk_free.csv", mapping).to_numpy()
    reference = executed(final_report, BENCHMARK, origins, assets)
    rows, diagnostics = [], []
    for method, (path, report) in risk_runs.items():
        matrices = read_covariance_panel(path, assets)
        covariance = np.stack([matrices[origin] for origin in origins])
        eig = np.linalg.eigvalsh(covariance)
        trace_share = eig[:, -5:].sum(axis=1) / eig.sum(axis=1)
        diagonal = np.diagonal(covariance, axis1=1, axis2=2).copy()
        observations = outcomes.copy()
        if DELISTED_ASSET in assets:
            invalid = np.asarray(mapping >= DELISTED_FROM)
            diagonal[invalid, assets.index(DELISTED_ASSET)] = np.nan
            observations[invalid, assets.index(DELISTED_ASSET)] = np.nan
        diagnostics.append({
            "method": method, "months_positive_definite": int((eig[:, 0] > 1e-12).sum()),
            "min_eigenvalue": eig[:, 0].min(), "max_top5_trace_share": trace_share.max(),
            "mean_predicted_stock_vol": np.sqrt(12 * np.nanmean(diagonal, axis=0)).mean(),
            "realized_stock_vol": np.nanstd(observations, axis=0, ddof=1).mean() * np.sqrt(12),
        })
        for model in table(report, "performance_summary").index:
            weights = executed(report, model, origins, assets)
            if model == BENCHMARK:
                np.testing.assert_allclose(weights, reference, atol=1e-12)
            variance = np.einsum("ti,tij,tj->t", weights, covariance, weights)
            realised = (weights * outcomes).sum(axis=1)
            rows.append({"method": method, "model": model, **calibration(variance, realised, rf)})
    pd.DataFrame(rows).to_csv(output / "risk_calibration.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(output / "covariance_diagnostics.csv", index=False)


def final_attribution(path, report, expected, actual, output):
    origins, assets = expected.index, expected.columns.tolist()
    mapping = target_dates(origins, actual.index)
    outcomes = actual.loc[mapping, assets].to_numpy()
    with np.load(path.with_suffix(".components.npz")) as bundle:
        positions = pd.Index(bundle["assets"]).get_indexer(assets)
        if (positions < 0).any() or not np.array_equal(bundle["origins"], origins.to_numpy()):
            raise ValueError("broad-risk components do not match the final forecast")
        exposures = bundle["exposures"][:, positions]
        factor_covariances = bundle["factor_covariances"]
        specific = bundle["specific_variances"][:, positions]
    factors = pd.read_csv(path.with_suffix(".factors.csv"), index_col=0, parse_dates=True).loc[mapping]
    factors = factors[["market", *STYLES]]
    factor_matrix = factors.to_numpy()
    design = np.column_stack([np.ones(len(factors)), factor_matrix])
    benchmark = (executed(report, BENCHMARK, origins, assets) * outcomes).sum(axis=1)
    net = table(report, "oos_returns")
    summary, monthly, style, gaps = [], [], [], []
    for model in net:
        weights = executed(report, model, origins, assets)
        portfolio_exposures = np.einsum("ti,tik->tk", weights, exposures)
        common = np.einsum("ti,tij,tj->t", portfolio_exposures, factor_covariances, portfolio_exposures)
        unique = np.einsum("ti,ti->t", weights ** 2, specific)
        summary.append({
            "model": model, "factor_vol": np.sqrt(12 * common.mean()),
            "specific_vol": np.sqrt(12 * unique.mean()),
            "combined_vol": np.sqrt(12 * (common + unique).mean()),
            "factor_variance_share": common.mean() / (common + unique).mean(),
        })
        monthly.append(pd.DataFrame({"origin": origins, "model": model,
                                     "factor_variance": common, "specific_variance": unique}))
        if model == BENCHMARK:
            continue
        gross = (weights * outcomes).sum(axis=1)
        active = gross - benchmark
        fit, _, covariance = hac_regression(design, active)
        contributions = 12 * fit * np.r_[1, factor_matrix.mean(axis=0)]
        np.testing.assert_allclose(contributions.sum(), 12 * active.mean(), atol=1e-12)
        for name, coefficient, contribution, se in zip(
            ["intercept", *factors.columns], fit, contributions, np.sqrt(np.diag(covariance)), strict=True,
        ):
            style.append({"model": model, "factor": name, "loading": coefficient,
                          "hac_t": coefficient / se, "annual_contribution": contribution})
        active_net = net[model] - net[BENCHMARK]
        interval = circular_block_bootstrap_mean(active_net)["mean_ci"]
        gaps.append({"model": model, "gross_gap": 12 * active.mean(), "net_gap": 12 * active_net.mean(),
                     "incremental_cost_drag": 12 * (active.mean() - active_net.mean()),
                     "annual_net_gap_ci_low": 12 * interval[0], "annual_net_gap_ci_high": 12 * interval[1],
                     **table(report, f"attribution/{model}").iloc[0].to_dict()})
    pd.DataFrame(summary).to_csv(output / "risk_decomposition.csv", index=False)
    pd.concat(monthly).to_csv(output / "monthly_risk_decomposition.csv", index=False)
    pd.DataFrame(style).to_csv(output / "style_attribution.csv", index=False)
    pd.DataFrame(gaps).to_csv(output / "return_attribution.csv", index=False)

    paired, vif = [], []
    for origin, matrix in zip(origins, exposures[:, :, 2:], strict=True):
        if origin >= DELISTED_FROM and DELISTED_ASSET in assets:
            matrix = np.delete(matrix, assets.index(DELISTED_ASSET), axis=0)
        correlation = np.corrcoef(matrix, rowvar=False)
        paired.append(np.abs(correlation))
        vif.append(np.diag(np.linalg.inv(correlation)))
    pd.DataFrame(np.median(paired, axis=0), index=STYLES, columns=STYLES).to_csv(output / "style_correlations.csv")
    pd.DataFrame(vif, index=origins, columns=STYLES).to_csv(output / "style_vif.csv")
