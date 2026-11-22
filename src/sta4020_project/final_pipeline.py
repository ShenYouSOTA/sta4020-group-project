"""Compatibility entrypoint for `python -m sta4020_project.final_pipeline`."""

from .pipeline.final import descriptor_path, fingerprint, main, run_final

__all__ = ["descriptor_path", "fingerprint", "main", "run_final"]

if __name__ == "__main__":
    raise SystemExit(main())
