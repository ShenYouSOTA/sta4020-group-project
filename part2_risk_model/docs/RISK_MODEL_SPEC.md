# Risk model implementation specification

Date: 2026-11-18. Status: implemented; synthetic verification and audit completed.

## 1. Purpose and requirements

Build one Python pipeline covering the risk-estimation methods developed in STA4020 Lectures 7 and 8. Under factor-level integration, its primary output is

```math
\hat\Sigma_{R,t+1\mid t}=\beta_t\hat\Sigma_{f,t+1\mid t}\beta_t^\top+\hat\Sigma_{u,t+1\mid t}.
```

Requirements: preserve lecture notation/formulas; support the specified estimator alternatives through shared interfaces; use only information available at the forecast origin; expose necessary intermediate estimates; develop and validate exclusively with synthetic data. Real data is not a completion gate.

| Module | Purpose | Inputs | Output |
|---|---|---|---|
| 1. Factor estimation | Normalize raw exposures and solve constrained WLS | Stock returns and one dated history of raw styles, industries and caps | Factor returns, residuals, exposure history, pure factor portfolios |
| 2. Stable risk | Estimate stable covariance and specific-risk baselines; apply shrinkage | Factor/residual or stock histories; shrinkage targets/caps when needed | Covariance estimates, specific variances and shrunk matrices |
| 3. Dynamic risk | Fit EWMA, ARCH(1) or GARCH(1,1) and forecast variance | Return histories, method and applicable parameters | Forecast variances, standardized residuals, Student-t degrees of freedom |
| 4. Integration | Construct correlations, rescale or blend estimates and compute stock covariance | Stable covariance/specific estimates, dynamic forecasts, current exposures | Stock covariance |
| 5. Diagnostics | Check pure factor portfolio construction, fitted volatility and ex ante risk | Panel/factor result, standardized residuals, covariance forecasts and subsequent returns | Algebraic errors, bias statistics and residual diagnostic figures |

`forecast_risk` calls the modules: Module 1 supplies Modules 2/3, which supply Module 4; Module 5 evaluates results. Stock-level dynamics consume stock returns directly. Direct stock methods need Module 1 only for factor-model structure. Synthetic generators belong to tests and the example notebook.

## 2. Sources and coverage

Sources: CUHK-Shenzhen STA4020, Prof. Chuan Shi, Lecture 7 (*Risk Modeling I*) and Lecture 8 (*Risk Modeling II*). Lecture materials © Prof. Chuan Shi and included with his permission: `STA4020_L7_Risk Modeling I.pdf` and `STA4020_L8_Risk Modeling II.pdf`, alongside this document. The lecture PDFs are not covered by the project's MIT license and are not needed to run the model.

References use printed slide numbers. L7 repeats slide 39 as an overlay: printed slides 40-71 are PDF pages 41-72. L8 printed numbers equal PDF pages.

| Required methods | Source |
|---|---|
| Sample covariance, Frobenius error, linear/Ledoit-Wolf shrinkage; identity, constant-correlation and factor-model targets | L7 13-25 |
| Barra exposures, constrained WLS, pure factor portfolios | L7 29-44 |
| Bias statistic, eigenfactor portfolios and Monte Carlo adjustment | L7 46-59 |
| Bayesian specific-volatility shrinkage with size-decile priors | L7 63-66 |
| EWMA, ARCH(1) and GARCH(1,1) one-step variance forecasts | L8 19-31 |
| Gaussian/standardized Student-t likelihood and residual diagnostics | L8 34-40 |
| Historical, constant, shrunk and factor-model stable correlations; PSD validity | L8 47-48 |
| Stock rescaling; factor rescaling/blending; dynamic/blended specific risk | L8 44-54 |

Higher-order ARCH models are excluded from implementation by scope. Deferred: nonlinear shrinkage and DCC, mentioned without complete algorithms. James-Stein mean shrinkage is background. Data sourcing/cleaning, economic descriptor construction, alpha models, production optimization, trading, empirical strategy backtesting and Lecture 9 VaR/ES are outside scope.

## 3. Shared data contract

| Symbol | Meaning | Shape |
|---|---|---|
| $R_t^e$, $\beta_{t-1}$ | Stock excess returns and exposures known beforehand | $N$, $N\times K$ |
| $f_t$, $e_t$ or $u_t$ | Factor and idiosyncratic returns; L7 uses $e$, L8 uses $u$ | $K$, $N$ |
| $\Sigma_f$, $\Sigma_u$ | Factor and specific covariance; store only the diagonal of $\Sigma_u$ | $K\times K$, $N$ stored entries |
| $\hat\Sigma_f^\star$, $\hat C_f^\star$ | Stable factor covariance/correlation | $K\times K$ |
| $\hat D_f^{ts}$ | Diagonal forecast factor standard deviations; store its diagonal | $K$ stored entries |

Use floating-point arrays, time on axis 0, decimal returns and squared-return covariance units; no implicit annualization. Store specific risk as a variance vector. Follow lecture notation: $F$ is a shrinkage target, $X$ is demeaned returns, and $e$ (L7) and $u$ (L8) are idiosyncratic returns. Use $d$ for the number of series. Within each calculation, $T$ counts its observations. Every forecast at origin $t$ is for the next observation $t+1$. Omit forecast subscripts only when the origin is unambiguous.

| `RiskPanel` field | Shape / meaning |
|---|---|
| `dates`, `asset_ids` | Increasing unique return dates $(T,)$ and stock ordering $(N,)$ |
| `returns` | Stock excess returns $(T,N)$ |
| `style_values`, `style_ids` | Raw styles $(T,N,Q)$ on `dates`, and style ordering $(Q,)$ |
| `industry_membership`, `industry_ids` | One industry per stock $(T,N)$ on the same dates; fixed industry ordering $(P,)$ |
| `market_caps` | Positive caps $(T,N)$ on the same dates |

After truncation at the forecast origin, all panel histories share the same $T$ dates. Data in each row must be known on its date. Apply the lecture lag internally: regress `returns[1:]` on exposures constructed from styles/industries/caps in rows `[:-1]`. The first return has no preceding exposure row in the panel and is excluded from factor estimation, giving $T-1$ fitted observations; require at least two input dates. The final input row constructs forecast-origin exposures and supplies latest caps.

Module 1 reads `RiskPanel`; individual risk estimators receive numerical arrays. Use stock returns directly for stock-level methods. Zero style factors are allowed. In API names, asset refers to a stock in this universe.

**Validation:** require the stated shapes, matching ordering and finite numerical inputs. Panel dates/IDs must be unique, industries represented and caps positive. Covariance inputs/outputs must be symmetric positive semidefinite; singular matrices are allowed where the calculation is defined. Reject invalid parameters, undefined calculations and failed fits. Method-specific conditions appear below.

Callers select history windows before calling individual estimators; every window ends at the forecast origin. Preserve input arrays and ordering. Synthetic panels are balanced; data cleaning and imputation are outside scope.

## 4. Module 1: Barra factor estimation

**Purpose:** construct the lecture exposure history, estimate factor returns by constrained WLS, and return residuals and pure factor portfolio weights.

| Public function | Inputs | Output |
|---|---|---|
| `fit_factor_model(panel)` | `RiskPanel` from Section 3, with raw styles, industries, caps and stock returns | `FactorResult` with the four fields below |

**Output:** `FactorResult` with four fields:

| Field | Shape | Meaning |
|---|---|---|
| `factor_returns` | $(T-1,K)$ | Rows are $\hat f_t^\top$, aligned with `dates[1:]` |
| `residuals` | $(T-1,N)$ | Rows are $\hat e_t^\top$, aligned with `dates[1:]` |
| `exposures` | $(T,N,K)$ | Exposure history: `exposures[j]` is constructed from input row `j`, aligned with `dates` |
| `pure_factor_portfolios` | $(T-1,K,N)$ | Stock holdings that reproduce each fitted factor-return vector |

For `j=1,...,T-1`, `factor_returns[j-1]`, `residuals[j-1]` and `pure_factor_portfolios[j-1]` use `exposures[j-1]` and `returns[j]`. Factor order is country, input industries, input styles.

### 4.1 Exposure construction

**Calculation:** set $K=1+P+Q$. Country exposure is one; industry dummies are exclusive/exhaustive. For each raw style characteristic, subtract its capitalization-weighted cross-sectional mean, then divide by its unweighted cross-sectional sample standard deviation. Compute that standard deviation around the unweighted arithmetic mean with denominator $N-1$.

The result satisfies $\sum_i s_i\beta_{i,t-1}^{S_q}=0$. Country and industry columns are not standardized.

**Validation:** style dispersion must be positive.

### 4.2 Constrained WLS

**Calculation:** use lagged exposures/caps for each return:

```math
R_t^e=\beta_{t-1}f_t+e_t,\quad W_{ii}=\frac{\sqrt{s_i}}{\sum_j\sqrt{s_j}},\quad s_{I_p}=\frac{\sum_{i\in I_p}s_i}{\sum_{i=1}^N s_i},\quad \sum_p s_{I_p}f_{I_p,t}=0.
```

Construct the slide's $C\in\mathbb R^{K\times(K-1)}$ to map the free factor returns into the full vector $f$. Country/styles pass through; always eliminate the last industry in input ordering:

```math
f_{I_P}=-\sum_{p=1}^{P-1}\frac{s_{I_p}}{s_{I_P}}f_{I_p}.
```

Free coordinates are country, the first $P-1$ industries and all styles. Each industry needs positive total caps. With $\beta=\beta_{t-1}$:

```math
\Omega_{t-1}=C(C^\top\beta^\top W\beta C)^{-1}C^\top\beta^\top W,\quad \hat f_t=\Omega_{t-1}R_t^e,\quad \hat e_t=R_t^e-\beta_{t-1}\hat f_t.
```

Solve the least-squares problem with design $W^{1/2}\beta C$ and response $W^{1/2}R_t^e$ using QR/SVD and a rank check; never explicitly invert or silently accept deficient rank. Row multipliers are $\sqrt{W_{ii}}$, not $W_{ii}$.

**Validation:** the constrained design must have full column rank. Verify reconstruction and the industry constraint in the factor-construction checks of Section 10.

### 4.3 Pure factor portfolio identities

```math
\Omega\beta =
\begin{bmatrix}
D_{(1+P)\times(1+P)} & 0_{(1+P)\times Q}
\\ 0_{Q\times(1+P)} & I_{Q\times Q}
\end{bmatrix},
\qquad \Omega R^e=\hat f.
```

The block $D$ describes country/industry exposures. Style portfolios have unit own-style and zero other exposure. Industry $p$ has own-industry exposure $1-s_{I_p}$, other-industry exposure $-s_{I_q}$ and zero country/style exposure. The country portfolio has country exposure one, industry exposures $s_{I_p}$ and style exposures zero. Industry/style weights sum to zero; country weights sum to one. The country/industry block is not identity; country holdings need not equal cap weights or all be nonnegative.

## 5. Module 2: stable risk

**Purpose:** estimate stable factor covariance and specific variances, and apply covariance or Bayesian specific-variance shrinkage.

| Public function | Inputs | Output |
|---|---|---|
| `estimate_factor_covariance(factor_returns, *, eigenfactor_adjustment=True, simulations=1000, a=1.0)` | Factor returns $(T,K)$; optional eigenfactor adjustment parameters | Factor covariance $(K,K)$; sample covariance when adjustment is disabled |
| `estimate_specific_variance(residuals)` | Module 1 residual returns $(T,N)$ | Sample specific variances $(N,)$ |
| `shrink_covariance(sample_covariance, method="factor_model", *, w=0.5, target_covariance=None, returns=None)` | Matrix $(d,d)$; target or return history required by the selected method below | Shrunk matrix $(d,d)$ |
| `shrink_specific_variance(specific_variance, market_caps, q=1.0)` | Sample specific variances $(N,)$ and forecast-origin caps $(N,)$ | Bayesian-shrunk specific variances $(N,)$ |

Module 1 supplies factor returns and residuals. Stock covariance uses stock returns. L7 covariance shrinkage is stable asset-level blending of sample and target matrices, both $(N,N)$; it is separate from L8 dynamic blending. Only `estimate_factor_covariance` performs eigenfactor adjustment.

### 5.1 Sample covariance and covariance shrinkage

**Calculation:** for demeaned returns $X$ with $T$ rows, the sample covariance and its shrunk estimate are

```math
S=(T-1)^{-1}X^\top X,\qquad\hat\Sigma=wF+(1-w)S,\quad0\leq w\leq1.
```

| `method` | Target and required arguments |
|---|---|
| `factor_model` | Require `target_covariance`: stock covariance $F$ from `compute_asset_covariance`, using stable factor/specific estimates and forecast-origin exposures. Use `w`. |
| `scaled_identity` | Construct $F=s_0I$, where $s_0$ is the mean diagonal of $S$. Use `w`. |
| `constant_correlation` | Set $F_{ii}=S_{ii}$ and $F_{ij}=\rho\sqrt{S_{ii}S_{jj}}$, where $\rho$ is the mean off-diagonal sample correlation. Use `w`. |
| `ledoit_wolf` | Construct the scaled-identity target and estimate intensity from `returns` $(T,d)$ from the same sample. Reconcile the $T-1$ normalization; `w` is unused. |

Ordinary covariance shrinkage applies to stock matrices, with $d=N$. Module 4 also reuses `scaled_identity` on stock or factor correlation matrices; their unit diagonals give target $I$. This reuse does not add shrinkage to factor covariance estimation.

**Validation:** sample estimation needs $T\geq2$; targets must match the input matrix's shape. Constant-correlation construction requires positive sample variances; with one series, its target is $S$.

### 5.2 Eigenfactor adjustment

**Calculation:** start from sample factor covariance. When adjustment is enabled, use $M=$ `simulations` and a local seed of zero in the procedure below; otherwise return the sample covariance.

1. Decompose sample $\hat\Sigma_f=UDU^\top$ with ascending eigenvalues.
2. For each $m$, generate $T$ independent Gaussian observations for each eigenfactor, with variance $D_{kk}$, and form $\tilde f_m=Ub_m$.
3. Compute simulated sample covariance $\tilde\Sigma_{f,m}=\tilde U_m\tilde D_m\tilde U_m^\top$ with the same ordering, and $D_m=\tilde U_m^\top\hat\Sigma_f\tilde U_m$.
4. Correct and reconstruct:

```math
\nu_k=M^{-1}\sum_m\sqrt{(D_m)_{kk}/(\tilde D_m)_{kk}},\quad \nu_k^s=a(\nu_k-1)+1,\quad (D_0)_{kk}=(\nu_k^s)^2D_{kk},\quad \hat\Sigma_{f,0}=UD_0U^\top.
```

**Output:** the adjusted covariance $\hat\Sigma_{f,0}$, denoted $\hat\Sigma_f^\star$ in L8.

**Validation:** require positive integer `simulations` and positive `a` when adjustment is enabled. For singular covariance, adjust only the positive eigenspace and preserve zero eigenvalues; undefined corrections raise an error.

### 5.3 Specific variance and Bayesian shrinkage

**Calculation:** `estimate_specific_variance` returns sample variances with denominator $T-1$. `shrink_specific_variance` takes their square roots and applies the L7 Bayesian adjustment. Sort caps, break ties by input order and form ten nearly equal-count size groups. Within each group, use the cap-weighted mean volatility as the prior and unweighted dispersion around that prior:

```math
\begin{gathered}
\bar\sigma(S_i)=\sum_{j\in S_i}w_j\hat\sigma_j,
\\ \nu_i=\frac{q|\hat\sigma_i-\bar\sigma(S_i)|}{\sqrt{\frac1{N(S_i)}\sum_{j\in S_i}(\hat\sigma_j-\bar\sigma(S_i))^2}+q|\hat\sigma_i-\bar\sigma(S_i)|},
\\ \sigma_i^{SH}=\nu_i\bar\sigma(S_i)+(1-\nu_i)\hat\sigma_i,\qquad \hat\Sigma_u^\star=\mathrm{diag}((\sigma_1^{SH})^2,\ldots,(\sigma_N^{SH})^2).
\end{gathered}
```

A zero denominator retains the original volatility.

**Output:** the variance vector $((\sigma_1^{SH})^2,\ldots,(\sigma_N^{SH})^2)$.

**Validation:** sample variance needs $T\geq2$. Bayesian shrinkage needs at least ten stocks, nonnegative input variances and $q\geq0$.

## 6. Module 3: dynamic risk

**Purpose:** estimate univariate conditional variance models and forecast variance for the next observation. Use the same function for factor, residual and stock returns; it estimates no correlation.

| Public function | Inputs | Output |
|---|---|---|
| `estimate_dynamic_variance(returns, method="garch", *, lambda_=0.94, distribution="student_t")` | Return history $(T,d)$ and the method-specific arguments below | Three result fields below |

| Argument | Shape / type | Meaning |
|---|---|---|
| `returns` | $(T,d)$ | Factor returns ($d=K$), specific residuals or stock returns ($d=N$) |
| `method` | String | `"garch"` for GARCH(1,1), `"arch"` for ARCH(1), or `"ewma"` |
| `lambda_` | Scalar | EWMA decay, with $0<\lambda<1$ |
| `distribution` | String | ARCH/GARCH likelihood: standardized `"student_t"` or `"gaussian"` |

| Field | Shape | Meaning |
|---|---|---|
| `forecast_variance` | $(d,)$ | One-step $\hat\sigma_{t+1\mid t}^2$; Module 4 input |
| `standardized_residuals` | $(T,d)$ | Fitted $\hat z_t$ for all training observations; Module 5 input |
| `degrees_of_freedom` | $(d,)$ or `None` | Fitted $\nu$ for Student-t ARCH/GARCH; `None` for Gaussian fits or EWMA; Module 5 input |

Return only these fields; fitted means, coefficients and variance paths remain internal. Each call uses one specification, fitted independently to each series. `lambda_` is used only by EWMA; `distribution` only by ARCH/GARCH.

### 6.1 Models and fitting

Use $R_t=\mu_{t\mid t-1}+\varepsilon_t$, $\varepsilon_t=\sigma_tz_t$, $\sigma_t^2\equiv\sigma_{t\mid t-1}^2$.

```math
\text{EWMA: }\sigma_t^2=\lambda\sigma_{t-1}^2+(1-\lambda)\varepsilon_{t-1}^2,\qquad 0<\lambda<1.
```

```math
\text{ARCH}(1):\sigma_t^2=\alpha_0+\alpha_1\varepsilon_{t-1}^2,\qquad \alpha_0>0,\ 0\leq\alpha_1<1.
```

```math
\text{GARCH}(1,1):\sigma_t^2=\alpha_0+\alpha_1\varepsilon_{t-1}^2+\beta_1\sigma_{t-1}^2,\qquad \alpha_0>0,\ \alpha_1,\beta_1\geq0.
```

**Calculation:** EWMA uses the supplied decay; ARCH/GARCH parameters maximize the selected likelihood. Enforce $\alpha_1<1$ for ARCH and $\alpha_1+\beta_1<1$ for GARCH, in addition to the positivity constraints above.

Use a constant mean: estimate $\mu$ jointly with ARCH/GARCH parameters; for EWMA, use the training sample mean. The GARCH mean specification follows L8 36-37. Compute innovations as $\hat\varepsilon_t=R_t-\hat\mu$.

The Gaussian likelihood is

```math
\ell(\theta)=-\frac12\sum_t[\log(2\pi)+\log\sigma_t^2(\theta)+(R_t-\mu)^2/\sigma_t^2(\theta)].
```

Student-t uses $`z_t=\sqrt{(\nu-2)/\nu}\,u_t`$, $u_t\sim t_\nu$, $\nu>2$, and

```math
\ell(\theta)=\sum_t\left[\log\Gamma((\nu+1)/2)-\log\Gamma(\nu/2)-\tfrac12\log(\pi(\nu-2)\sigma_t^2)-\tfrac{\nu+1}{2}\log(1+\varepsilon_t^2/((\nu-2)\sigma_t^2))\right].
```

Here $\Gamma$ is the gamma function. Estimate $\nu$ with the other parameters. Use the same unit-variance scaling for simulation and Q-Q diagnostics; the density agrees with the [official arch reference](https://arch.readthedocs.io/en/stable/univariate/generated/generated/arch.univariate.StudentsT.loglikelihood.html). `distribution` selects the ARCH/GARCH likelihood; EWMA uses its variance recursion.

### 6.2 Initialization and one-step forecasting

**Initialization:** use the training sample variance (denominator $T-1$) as the first conditional variance and hold it fixed during optimization. Start recursion at the second observation. Include all $T$ observations in the likelihood and standardized residual output, including the first with its initialized variance.

Fitted standardized residuals are in-sample diagnostics. Their fitted variance path is not a history of ex ante forecasts. Numerical solver details remain internal; return results in the original input units.

**Forecast calculation:** after filtering observations through $t$, calculate the next variance using the latest innovation $\hat\varepsilon_t$ and fitted variance $\hat\sigma_t^2$:

```math
\text{EWMA: }\hat\sigma_{t+1\mid t}^2=\lambda\hat\sigma_t^2+(1-\lambda)\hat\varepsilon_t^2.
```

```math
\text{ARCH}(1):\hat\sigma_{t+1\mid t}^2=\hat\alpha_0+\hat\alpha_1\hat\varepsilon_t^2.
```

```math
\text{GARCH}(1,1):\hat\sigma_{t+1\mid t}^2=\hat\alpha_0+\hat\alpha_1\hat\varepsilon_t^2+\hat\beta_1\hat\sigma_t^2.
```

**Validation:** require positive initial and conditional variances, at least two observations, and more observations than fitted parameters for ARCH/GARCH. Failed optimization raises an error; do not substitute another estimator.

## 7. Module 4: dynamic covariance integration

**Purpose:** combine a stable risk estimate from Module 2 with one-step variance forecasts from Module 3. L8 45, 50 and 52-54 present rescaling and blending as alternative final integration methods. Stable shrinkage is an earlier estimation step, not a third dynamic integration method.

All inputs refer to the same forecast origin. Module 1 supplies `exposures = factor_result.exposures[-1]`, shape $(N,K)$. Stock and factor covariance matrices have different dimensions; do not substitute one for the other.

| Public function | Inputs | Output |
|---|---|---|
| `rescale_covariance(covariance, forecast_volatility, method="factor_model", *, w=0.5)` | Stable covariance $(d,d)$, forecast standard deviations $(d,)$, correlation construction | Next-period covariance $(d,d)$; $d=K$ for factors or $d=N$ for stocks |
| `blend_risk(stable_estimate, dynamic_estimate, stable_weight=0.5)` | Matching covariance matrices or variance vectors; stable weight | Weighted-average covariance or variances; the lecture pipeline uses $(K,K)$ and $(N,)$ respectively |
| `compute_asset_covariance(exposures, factor_covariance, specific_variance)` | Exposures $(N,K)$, factor covariance $(K,K)$, specific variances $(N,)$ | Stock covariance $(N,N)$ |

### 7.1 Rescale covariance

**Inputs:** supply a stable covariance and forecast standard deviations for the same series. Without stock covariance shrinkage, `factor_model` uses the stable factor covariance at factor level or assembled stock covariance $F$ at stock level; the other methods start from sample covariance. If Module 2 stock covariance shrinkage is enabled, its $(N,N)$ result supplies the stock-level input before the chosen correlation construction. Both stable covariance shrinkage and a correlation adjustment may therefore be used; neither changes the matrix level.

**Calculation:** normalize the supplied covariance to correlation, then construct the correlation for rescaling:

```math
\hat C_{ij}=\frac{\text{covariance}_{ij}}{\sqrt{\text{covariance}_{ii}\text{covariance}_{jj}}}.
```

| `method` | Calculation of $\hat C^\star$ |
|---|---|
| `"factor_model"`, `"historical_average"` | Preserve the supplied stable correlation: $\hat C^\star=\hat C$. Their unshrunk input sources differ as described above. |
| `"constant_correlation"` | Set $\rho$ to the mean off-diagonal entry of $\hat C$; set $\hat C^\star_{ii}=1$ and $\hat C^\star_{ij}=\rho$ for $i\ne j$. |
| `"shrinkage"` | Set $\hat C^\star=wI+(1-w)\hat C$ using Module 2's `shrink_covariance` with `method="scaled_identity"`. This shrinks correlation, distinct from ordinary stock covariance shrinkage. |

Apply the forecast standard deviations:

```math
\hat\Sigma_{t+1\mid t}=\hat D^{ts}_{t+1\mid t}\hat C^\star\hat D^{ts}_{t+1\mid t},\qquad \hat D^{ts}_{t+1\mid t}=\mathrm{diag}(\text{forecast\_volatility}).
```

**Output:** covariance with diagonal `forecast_volatility ** 2`.

**Validation:** require a positive stable covariance diagonal and matching nonnegative forecast standard deviations. For correlation shrinkage, require $0\leq w\leq1$. For one series, correlation is $[1]$.

### 7.2 Blend stable and dynamic risk (L8)

**Inputs:** stable factor covariance $(K,K)$ and historical or Bayesian-shrunk specific variances $(N,)$ come from Module 2. Module 3 supplies factor and residual variance forecasts. Following L8 52's fixed-correlation construction, form the dynamic factor covariance using stable factor correlation:

```math
\hat\Sigma^{ts}_{f,t+1\mid t}=\hat D^{ts}_{f,t+1\mid t}\hat C_f^\star\hat D^{ts}_{f,t+1\mid t}.
```

This construction may reuse `rescale_covariance` internally. It prepares the dynamic input to blending; the final estimator is the weighted average below, rather than the standalone rescaling estimator. No DCC or additional correlation setting is introduced for blending.

**Calculation:** blend the two estimates at each component:

```math
\hat\Sigma_{f,t+1\mid t}=\eta_f\hat\Sigma_f^\star+(1-\eta_f)\hat\Sigma_{f,t+1\mid t}^{ts},
```

```math
\hat\sigma_{u,i,t+1\mid t}^2=\eta_{u,i}\hat\sigma_{u,i}^{2,EB}+(1-\eta_{u,i})\hat\sigma_{u,i,t+1\mid t}^{2,ts}.
```

Historical specific variances replace the Bayesian baseline when specific shrinkage is disabled. `factor_blending` and `specific_blending` supply the weights; both default to 0.5 when blending is selected.

**Output:** blended factor covariance and specific variances, subsequently assembled into stock covariance. Weight one selects the stable component; zero selects the dynamic component.

**Validation:** estimates must have matching shapes and weights in $[0,1]$. Factor covariance uses a scalar weight; specific variances also permit a stock-aligned $(N,)$ weight vector.

### 7.3 Compute stock covariance from factor and specific risk

**Inputs:** forecast-origin exposures $(N,K)$, factor covariance $(K,K)$ and specific variances $(N,)$, in matching stock/factor order.

**Calculation:**

```math
\hat\Sigma_R=\beta_t\hat\Sigma_f\beta_t^\top+\mathrm{diag}(\hat\sigma_{u,1}^2,\ldots,\hat\sigma_{u,N}^2).
```

**Output:** stable stock covariance $F$ when inputs are stable, or a stock covariance forecast when inputs are forecasts. Specific variance contributes only to the diagonal.

**Validation:** require matching dimensions and nonnegative specific variances.

### 7.4 Integration choices and matrix levels

- **Factor rescaling (default):** stable factor covariance $(K,K)$ or factor sample covariance supplies correlation; dynamic factor variances $(K,)$ supply its scale. Assemble the result with exposures $(N,K)$ and dynamic specific variances $(N,)$. No stable/dynamic blending is performed.
- **Stock rescaling:** a stable stock covariance $(N,N)$ supplies correlation; dynamic stock variances $(N,)$ supply its scale. The stock covariance may come from the factor model, sample returns or Module 2 stock covariance shrinkage. It is not assembled again.
- **Dynamic blending (L8):** use stable and dynamic factor covariance $(K,K)$ plus stable and dynamic specific variances $(N,)$, as in Section 7.2. Assemble the two blended components into $(N,N)$ stock covariance. `rescaling_level` and rescaling-specific options do not apply to this recipe.

Stable estimation settings are not enabled or prohibited by an integration method. They affect only estimates the selected calculation consumes: stock covariance shrinkage produces $(N,N)$, so factor rescaling and L8 factor blending do not consume it. This does not restrict L7 blending to factor matrices. Bayesian specific shrinkage is consumed by a stock factor-model baseline or specific blending; it never modifies a dynamic variance forecast. No stock-to-factor covariance conversion is implied.

## 8. Module 5: risk diagnostics

**Purpose:** check pure factor portfolio construction, measure forecast risk bias (L7), and plot standardized residual diagnostics for fitted volatility models (L8).

| Public function | Inputs | Output |
|---|---|---|
| `diagnose_pure_factor_portfolios(panel, factor_result)` | The `RiskPanel` used for fitting and its Module 1 `FactorResult`; fields read are listed in Section 8.1 | Three scalar maximum absolute errors: return replication, exposure structure and neutrality |
| `compute_bias_statistic(returns, covariance, *, eigenfactor=False)` | One series: returns and forecast variances, both $(T,)$. Multiple series: returns $(T,d)$ and forecast covariances $(T,d,d)$ | Scalar for one-dimensional inputs; otherwise one bias statistic per series or positive-eigenvalue portfolio |
| `diagnose_standardized_residuals(standardized_residuals, degrees_of_freedom)` | Module 3's `standardized_residuals` $(T,d)$ and fitted Student-t degrees of freedom $(d,)$ or `None` | One diagnostic figure per series, returned in input-column order |

### 8.1 Diagnose pure factor portfolios

**Purpose:** check whether Module 1 constructed the pure factor portfolios correctly, using the identities in Section 4.3. This checks algebraic properties, not risk forecasts.

**Inputs:** from `panel`, read only `returns`, `market_caps`, `industry_membership` and `industry_ids`; from `factor_result`, read only `pure_factor_portfolios`, `exposures` and `factor_returns`. Use the same panel that produced the result. Shapes follow Sections 3-4; $T$ counts panel rows and there are $T-1$ fitted observations.

**Calculation:** for each panel row $j=1,\ldots,T-1$, let $\Omega$ be `factor_result.pure_factor_portfolios[j-1]`. Apply the three checks:

- **Return error:** $\Omega R_j^e-\hat f_j$, using `panel.returns[j]` and `factor_result.factor_returns[j-1]`.
- **Exposure error:** $\Omega\beta_{j-1}$ minus the block matrix in Section 4.3, using `factor_result.exposures[j-1]`. Construct the expected country/industry block independently: `panel.industry_ids` defines its column order; `panel.industry_membership[j-1]` selects each industry's stocks; `panel.market_caps[j-1]` gives $s_{I_p}=\sum_{i\in I_p}s_i/\sum_i s_i$. The style block is identity and the cross blocks are zero.
- **Neutrality error:** use only $\Omega$; subtract one from the country row's weight sum and zero from every industry/style row's weight sum.

**Output:** return the maximum absolute entry of each error over all observations as three scalars, in the order above. All three should be zero within the shared numerical tolerance. Do not return intermediate matrices or calculate bias statistics.

**Validation:** require a matching panel/result pair satisfying Sections 3-4, with at least one fitted observation. Report algebraic discrepancies through the three errors; malformed inputs raise an exception.

### 8.2 Compute bias statistics

**Purpose:** compare realized return variability with forecast risk. Ordinary portfolios, individual stocks and factors use the default calculation. Set `eigenfactor=True` to evaluate portfolios constructed from covariance eigenvectors.

**Inputs:** `returns[t]` is the realized return; `covariance[t]` is its previously forecast variance or covariance. Ordinary portfolio returns and variances arrive already computed as $(T,)$ arrays; no weights or reshaping are needed. Multiple series use returns $(T,d)$ and covariance $(T,d,d)$.

**Calculation:**

1. With `eigenfactor=False`, use the supplied returns. Their forecast variances are `covariance` itself for one-dimensional inputs, or its matrix diagonals for multiple series.
2. With `eigenfactor=True`, require matrix covariance histories. At each observation, decompose the forecast as $UDU^\top$, sort eigenvalues in ascending order, and use $U^\top R_t^e$ as portfolio returns and the diagonal of $D$ as forecast variances. Evaluate positive-eigenvalue portfolios, matching them by eigenvalue rank across observations. Each eigenvector has unit Euclidean length; the first minimizes variance under that constraint.

For either calculation, divide the selected return by its forecast standard deviation and compute the sample standard deviation over time:

```math
b_{i,t}=R_{i,t}^e/\sigma_{i,t},\qquad B_i=\sqrt{\frac1{T-1}\sum_{t=1}^T(b_{i,t}-\bar b_i)^2}.
```

**Output:** return only $B_i$: near one means calibrated risk, above one means underestimated risk, and below one means overestimated risk. The lecture's approximate reference band is $[1-\sqrt{2/T},1+\sqrt{2/T}]$; dependence or heavy tails can invalidate this approximation.

**Validation:** require $T\geq2$ and positive scored variances. Eigenfactor mode needs matrix histories with constant positive rank; omit zero-eigenvalue directions. Use only forecasts available before each scored return.

### 8.3 Diagnose standardized residuals

**Purpose:** check whether the fitted mean model leaves linear dependence, the fitted variance model leaves volatility dependence, or the fitted distribution fails to describe the tails. These are the separate L8 37-40 checks of fitted-model adequacy, not proof of future forecast accuracy.

**Inputs:** pass Module 3's `standardized_residuals` and `degrees_of_freedom` directly. Each column contains $\hat z_t=\hat\varepsilon_t/\hat\sigma_t$ for one fitted series. `degrees_of_freedom` contains its fitted Student-t parameter, or is `None` for Gaussian fits and EWMA. This function does not fit or standardize returns again.

**Calculation:** compute each series' sample mean and variance and the following three plots:

- **ACF of standardized residuals:** shows linear dependence left unexplained by the mean model.
- **ACF of squared standardized residuals:** shows volatility dependence left unexplained by the variance model.
- **Q-Q plot:** compares standardized residuals with the fitted unit-variance Student-t distribution, or the standard normal when degrees of freedom are `None`. Systematic departures indicate distributional or tail mismatch. For EWMA, normal quantiles are only a reference.

**Output:** a list of $d$ figures in input-column order, each with the three panels and mean/variance annotations (reference values zero and one). Intermediate arrays remain internal. Inspect ACFs for systematic patterns; an isolated spike does not establish model failure.

**Validation:** require $T\geq2$ and, when supplied, one fitted degree of freedom greater than two per series.

## 9. Package API

**Purpose:** connect stable estimation, dynamic estimation and the selected integration method. Helpers stay in `risk_model.py`; calculations remain in the owning numerical modules.

| Public function | Inputs | Output |
|---|---|---|
| `forecast_risk(panel, as_of, *, factor_covariance=None, covariance_shrinkage=None, specific_shrinkage=None, dynamic_variance=None, integration_method="rescale", rescaling_level="factor", rescaling=None, factor_blending=None, specific_blending=None)` | `RiskPanel`, forecast-origin date and the options below | One-step stock covariance $(N,N)$ |

**Inputs:** dictionaries forward parameters directly. Omitted parameters retain module defaults. Shrinkage is off with `None` and on with a dictionary, including `{}`. Blending is selected only by `integration_method="blend"`; its weight dictionaries use module defaults when `None` or `{}`. Inactive settings are ignored.

| Option (module order) | Meaning / receiving function |
|---|---|
| `factor_covariance` | `estimate_factor_covariance`: `eigenfactor_adjustment`, `simulations`, `a` |
| `covariance_shrinkage` | `shrink_covariance`: `method`, `w`; creates a stable stock covariance, never a factor covariance |
| `specific_shrinkage` | `shrink_specific_variance`: `q`; stabilizes specific variance |
| `dynamic_variance` | `estimate_dynamic_variance`: `method`, `lambda_`, `distribution` |
| `integration_method` | `"rescale"` (default) or `"blend"`: choose the L8 dynamic integration method |
| `rescaling_level` | `"factor"` (default) or `"stock"`; applies only to rescaling |
| `rescaling` | `rescale_covariance`: correlation `method`, `w`; applies only to rescaling |
| `factor_blending`, `specific_blending` | `blend_risk`: `stable_weight`; apply only to blending |

**Calculation:** truncate every panel history at `as_of`, estimate the required stable components and dynamic variances, then follow exactly one recipe in Section 7.4. Stock covariance shrinkage precedes stock correlation construction, so it may combine with any rescaling correlation method. Blending uses fixed stable factor correlation to construct its dynamic input, and defaults to equal stable/dynamic weights for both components. Defaults preserve the original factor-rescaling forecast.

**Validation:** reject unknown integration methods and, when rescaling is selected, unknown rescaling levels. Ignore stable estimates and method-specific settings that the selected recipe does not use. Numerical functions validate their active inputs; no additional cross-stage prohibition is imposed. Call modules directly for separate history windows or intermediate estimates.

**Package:** `src/risk_model/` contains `factor_model.py`, `stable_risk.py`, `dynamic_risk.py`, `integration.py`, `diagnostics.py`, the top-level `risk_model.py` and private validation. Import `forecast_risk` from `risk_model`; import other functions from their owning package modules. Tests live in `tests/`; the self-contained synthetic example is `notebooks/synthetic_example.ipynb`. Dependencies are declared in `pyproject.toml`. Follow PEP 8/YAGNI.

## 10. Minimal verification and completion

Use synthetic data only. Retain the input validation specified in each module; use numerical tolerances for floating-point comparisons.

- **Factor construction:** on a small panel with unequal caps and multiple industries, verify return reconstruction and the industry constraint. The pure factor portfolio diagnostic must report near-zero errors for correct results and detect deliberately incorrect portfolios.
- **Risk calculations:** give each lecture method one small independent numerical reference case. Cover covariance/shrinkage formulas, eigenfactor adjustment, variance recursions and likelihoods, rescaling, blending and stock covariance assembly. Check alternative integration methods and stable-shrinkage/correlation composition at matching dimensions. Check the relevant matrix properties and preserve valid singular covariance.
- **Diagnostics:** compare ordinary and eigenfactor bias statistics with a direct calculation. Inspect one residual diagnostic figure for the two ACF panels, the correct Q-Q reference and mean/variance annotations.
- **Timing:** verify the one-row exposure lag. Changing observations after the forecast origin must not change that origin's forecast.
- **End-to-end:** run the default pipeline on one seeded synthetic panel with known conditional covariance. Check finite, symmetric positive-semidefinite forecasts; compare them with the known covariance using Frobenius error and evaluate bias against subsequent returns. The example also displays the Module 5 diagnostics. Keep synthetic latent quantities outside estimator inputs.

**Completion:** all Section 2 lecture methods are implemented, the checks above pass, and the synthetic example runs successfully. Real-data calibration and downstream investment work remain pending.

**Run:** from the repository root, install with `python -m pip install -e ".[dev]"`, run `python -m pytest -q`, then open `notebooks/synthetic_example.ipynb` with `python -m jupyterlab notebooks/synthetic_example.ipynb`. Run all cells using the installed environment; results and the diagnostic figure are retained inline. `risk_model.py` stays within 100 lines; other Python files and the notebook's combined code stay below 200 lines.
