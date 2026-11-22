"""Per-part configuration dataclasses composed into the final experiment config."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Part1Config:
    train_months: int = 72
    risk_months: int = 36
    min_factor_pairs: int = 100
    min_ic_months: int = 48
    ridge_penalty: float = 0.10
    fdr_q: float = 0.10
    block_months: int = 6
    bootstraps: int = 1999
    seed: int = 4020


@dataclass(frozen=True)
class Part2Config:
    history_start: str = "2013-01"
    broad_start: str = "2005-01"
    broad_max_names: int = 800
    methods: tuple[str, ...] = ("broad-factor", "factor", "sample", "ledoit-wolf")


@dataclass(frozen=True)
class Part3Config:
    risk_aversion: float = 5.0
    max_weight: float = 0.10
    sensitivity_aversions: tuple[int, ...] = (2, 5, 10)
    sensitivity_priors: tuple[str, ...] = ("Uniform", "Market cap")
    bl_tau: float = 0.05


@dataclass(frozen=True)
class Part4Config:
    cost_bps: float = 10.0
    cost_sweep: tuple[float, ...] = (0.0, 10.0, 30.0, 50.0)


@dataclass(frozen=True)
class FinalExperimentConfig:
    part1: Part1Config = field(default_factory=Part1Config)
    part2: Part2Config = field(default_factory=Part2Config)
    part3: Part3Config = field(default_factory=Part3Config)
    part4: Part4Config = field(default_factory=Part4Config)

    def to_dict(self) -> dict:
        return asdict(self)
