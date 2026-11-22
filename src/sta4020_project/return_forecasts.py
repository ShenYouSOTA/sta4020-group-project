"""Compatibility entrypoint for `python -m sta4020_project.return_forecasts`."""

from .part1.forecasts import build_forecasts, main

__all__ = ["build_forecasts", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
