# Barra-style risk model

A Python implementation of a **Barra-style equity risk model**, based on
**CUHK-Shenzhen STA4020, Lectures 7 and 8**, taught by **Prof. Chuan Shi**.
**Course lecture materials © Prof. Chuan Shi.**

The model estimates how stock returns vary together through shared country,
industry and style factors, plus stock-specific risk. Its main output is a
**one-step stock covariance forecast**, for use in portfolio risk calculations.
Expected-return prediction is outside this project's scope.

“Barra-style” describes the factor-model structure and estimation approach.
This is an educational implementation of the lecture methods, not an official
Barra product or a reproduction of a proprietary commercial model.

Implementation and numerical checks are complete for the specified scope.
**All testing uses synthetic data; real-data integration and empirical
calibration remain pending.**

## How the model works

Stock covariance combines shared factor risk and stock-specific variance:

```math
\widehat\Sigma_{R,t+1\mid t}
= \beta_t\widehat\Sigma_{f,t+1\mid t}\beta_t^\top
+ \mathrm{diag}(\widehat\sigma^2_{u,t+1\mid t}).
```

Here, $\beta_t$ contains stock exposures, $\widehat\Sigma_f$ is factor covariance,
and $\widehat\sigma_u^2$ contains stock-specific variances. Shared factors create
covariance between stocks; specific risk adds variance to each stock's diagonal.

The default `forecast_risk(panel, as_of)` pipeline:

1. Truncates all input histories at `as_of`.
2. Constructs country, industry and normalized style exposures, then estimates
   factor returns and stock residuals using constrained weighted least squares.
3. Estimates stable factor covariance with Monte Carlo eigenfactor adjustment.
4. Fits Student-t GARCH(1,1) models to factor returns and stock residuals to obtain
   next-period variances.
5. Rescales stable factor correlation using the predicted factor volatilities,
   then combines factor covariance with the latest exposures and predicted
   specific variances.

The default uses factor-level rescaling and dynamic specific variances directly.
Alternative lecture methods are available through the options below and the individual modules:

| Component | Available methods and outputs |
|---|---|
| Factor estimation | Constrained WLS; factor returns, stock residuals, exposure history and pure factor portfolio weights |
| Stable risk | Sample covariance/variance, eigenfactor adjustment, covariance shrinkage toward factor-model, scaled-identity or constant-correlation targets, Ledoit–Wolf shrinkage, and Bayesian specific-variance shrinkage |
| Dynamic risk | EWMA, ARCH(1), GARCH(1,1); Gaussian or Student-t likelihood for ARCH/GARCH |
| Integration | Factor- or stock-level rescaling, or factor/specific blending; stock covariance construction |
| Diagnostics | Pure factor portfolio algebraic errors, ordinary/eigenfactor portfolio risk bias, and standardized-residual plots |

Select alternatives through the `forecast_risk` options below, or call the
individual modules. Detailed signatures and formulas are in the
[implementation specification](docs/RISK_MODEL_SPEC.md).

## Install and run the example

Use **Python 3.10 or newer**. After obtaining the repository, run these commands
from its root in your Python environment:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m jupyterlab notebooks/synthetic_example.ipynb
```

The development installation includes pytest and notebook tools. For the model
package alone, use `python -m pip install -e .`.

Open the [synthetic example notebook](notebooks/synthetic_example.ipynb), select
the kernel for the installed environment, and run all cells. It contains its own
seeded data generator and requires no downloaded market data. Executed results
and the diagnostic figure are retained inline.

The example uses 260 observations and 20 stocks, evaluates 15 one-step covariance
forecasts, and reports:

- **Relative covariance error:** Frobenius distance from the known synthetic
  covariance, divided by its norm. Zero means exact covariance recovery.
- **Risk bias:** standardize each realized return by its corresponding predicted
  volatility, then take the sample standard deviation. Values near one indicate
  matching risk scale; above one suggests underestimated risk, below one overestimated
  risk. This is evaluated for individual stocks, an equal-weight portfolio and
  eigenfactor portfolios.
- **Construction errors:** pure factor portfolio return replication, constrained
  exposure structure and weight sums. Near-zero errors confirm algebraic
  identities, not predictive accuracy.
- **Residual diagnostics:** ACFs of standardized residuals and their squares,
  plus a distribution-matched Q-Q plot for the fitted volatility model.

The short evaluation window demonstrates the implementation; it does not
establish real-market performance.

## Inputs and API

`RiskPanel` holds aligned NumPy arrays. Let `T` be the number of observations,
`N` the number of stocks, `Q` the number of styles and `P` the number of industries.

| Field | Shape | Meaning |
|---|---|---|
| `dates` | `(T,)` | Increasing, unique observation dates |
| `asset_ids` | `(N,)` | Unique stock identifiers in column order |
| `returns` | `(T, N)` | Stock excess returns in decimal units |
| `style_values`, `style_ids` | `(T, N, Q)`, `(Q,)` | Raw style characteristics and their identifiers |
| `industry_membership`, `industry_ids` | `(T, N)`, `(P,)` | One listed industry per stock and the industry ordering |
| `market_caps` | `(T, N)` | Positive market capitalizations |

All histories share the same dates and stock order. Each row must contain only
information known on that date. The model applies the one-row lag internally:
return row `t` is fitted using exposures from row `t - 1`. The first return row is
excluded from factor estimation; the final exposure row is used for the next
period's covariance forecast. Factor order is country, industries, then styles.

Given arrays satisfying this contract:

```python
from risk_model import forecast_risk
from risk_model.factor_model import RiskPanel

panel = RiskPanel(
    dates=dates,
    asset_ids=asset_ids,
    returns=returns,
    style_values=style_values,
    style_ids=style_ids,
    industry_membership=industry_membership,
    industry_ids=industry_ids,
    market_caps=market_caps,
)
stock_covariance = forecast_risk(panel, as_of=panel.dates[-1])
```

The returned array has shape `(N, N)` in `asset_ids` order. Its diagonal contains
stock variances and its off-diagonal entries contain covariances, in squared
decimal-return units. It covers the **next observation interval**, with no implicit
annualization. For stock weights `w`, portfolio variance is
`w @ stock_covariance @ w`.

Inputs must be finite and correctly aligned; industries must be represented and
raw styles must have positive cross-sectional dispersion. Invalid inputs and
failed volatility fits raise errors. Data sourcing, cleaning, missing-value
imputation, and economic style-descriptor construction are not included.

### Customize risk estimation

Stable estimation includes **L7 asset-level blending (covariance shrinkage)**.
`integration_method` then chooses **L8 dynamic rescaling or blending**, with
rescaling the default. Dictionaries override selected parameters;
unspecified parameters retain defaults. Shrinkage is off with `None`, on with
`{}`. In blending mode, weight dictionaries use 50/50 defaults with `None` or `{}`.
Settings for estimates or methods the selected calculation does not use are ignored.

Options follow the SPEC order: stable risk → dynamic risk → integration.
The dictionary column shows defaults **when that calculation is used**.

| Option | Default value / dictionary | Purpose |
|---|---|---|
| `factor_covariance` | `{"eigenfactor_adjustment": True}` | Stable factor covariance; `False` selects sample covariance. |
| `covariance_shrinkage` | `{"method": "factor_model", "w": 0.5}` | L7: blend sample stock covariance with a target; `w` is target weight. |
| `specific_shrinkage` | `{"q": 1.0}` | Bayesian shrinkage of the stable specific-variance baseline. |
| `dynamic_variance` | `{"method": "garch", "distribution": "student_t"}` | Forecast factor/residual or stock variances. |
| `integration_method` | `"rescale"` | Choose L8 dynamic `"rescale"` or `"blend"`. |
| `rescaling_level` | `"factor"` | For rescaling: factor covariance `(K,K)` or `"stock"` covariance `(N,N)`. |
| `rescaling` | `{"method": "factor_model"}` | For rescaling: choose correlation and apply matching forecast volatilities. |
| `factor_blending` | `{"stable_weight": 0.5}` | For L8 blending: combine stable/dynamic factor covariance, weight on stable. |
| `specific_blending` | `{"stable_weight": 0.5}` | For L8 blending: combine stable/dynamic specific variances, weight on stable. |

For example, choose L8 dynamic blending with EWMA dynamics and a Bayesian specific baseline:

```python
stock_covariance = forecast_risk(
    panel, as_of=panel.dates[-1],
    specific_shrinkage={},
    dynamic_variance={"method": "ewma", "lambda_": 0.97},
    integration_method="blend",
    factor_blending={"stable_weight": 0.3},
    specific_blending={},
)
```

- **L7 stable blending:** combines `(N,N)` sample and target stock covariance. Its result can precede any stock rescaling correlation method; factor-level integration does not consume it.
- **Rescaling output:** stock rescaling already produces complete `(N,N)` stock covariance, so it is returned directly. Factor rescaling produces `(K,K)` factor covariance, which still needs exposures and specific variances to assemble stock covariance.
- **L8 blending input:** forecast factor volatilities and fixed stable factor correlation first produce `dynamic_factor_cov`, a `(K,K)` matrix. This reuses the rescaling calculation to prepare an input. The final estimator blends that input with stable factor covariance, blends specific variances separately, then assembles stock covariance.

Every call returns `(N,N)` stock covariance. The [notebook's customization examples](notebooks/synthetic_example.ipynb)
list alternative methods and additional parameters beside each example. To migrate
an earlier blending call, explicitly add `integration_method="blend"`.

## Verification and project layout

The focused synthetic test suite checks factor reconstruction and constraints,
pure portfolio identities, numerical reference calculations, variance recursions
and likelihoods, covariance integration, diagnostics, and isolation from future
observations. The notebook compares covariance forecasts with a known synthetic
data-generating process. Neither requires exact recovery of noisy latent factors.

- `src/risk_model/`: model modules, the top-level `risk_model.py`, and private
  numerical validation.
- `notebooks/`: the self-contained, executed synthetic demonstration.
- `tests/`: numerical tests and synthetic fixtures.
- `docs/RISK_MODEL_SPEC.md`: implementation contract, formulas and lecture references.
- `docs/STA4020_L7_Risk Modeling I.pdf` and `docs/STA4020_L8_Risk Modeling II.pdf`:
  lecture slides included with Prof. Chuan Shi's permission.
- `pyproject.toml`: package metadata and dependencies.

Return/alpha models, portfolio optimization, trading and strategy backtesting
are outside this implementation.

## License and course attribution

The implementation and accompanying project documentation are released under
the [MIT License](LICENSE).

The methods are based on Prof. Chuan Shi's CUHK-Shenzhen STA4020 lectures:
Lecture 7, *Risk Modeling I*, and Lecture 8, *Risk Modeling II*. The lecture
materials are © Prof. Chuan Shi and are included with his permission. They are
not covered by this project's MIT license.

The slides are available in `docs/`: [Lecture 7 — Risk Modeling I](docs/STA4020_L7_Risk%20Modeling%20I.pdf)
and [Lecture 8 — Risk Modeling II](docs/STA4020_L8_Risk%20Modeling%20II.pdf).
Neither installation nor the synthetic tests and notebook require the PDFs.
