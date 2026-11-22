"""AST-based architecture guard: enforce star dependency graph and clean runtime checks."""

from __future__ import annotations

import ast
from pathlib import Path

from sta4020_project.shared.contracts import project_root

ROOT = project_root()
PKG_ROOT = ROOT / "src" / "sta4020_project"
PART3_SCRIPT = ROOT / "part3_portfolio" / "Part3.py"

FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "shared": {"part1", "part2", "part3_portfolio", "part4", "pipeline"},
    "part1": {"part2", "part3_portfolio", "part4", "pipeline"},
    "part2": {"part1", "part3_portfolio", "part4", "pipeline"},
    "part3": {"part1", "part2", "part4", "pipeline"},
    "part4": {"part1", "part2", "part3_portfolio", "pipeline"},
}


def _imported_domains(path: Path, current_domain: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "sta4020_project" and len(parts) > 1:
                    found.add(parts[1])
                elif parts[0] == "part3_portfolio":
                    found.add("part3_portfolio")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                parts = module.split(".")
                if parts[0] == "sta4020_project" and len(parts) > 1:
                    found.add(parts[1])
                elif parts[0] == "part3_portfolio":
                    found.add("part3_portfolio")
            elif node.level >= 2:
                # Relative import climbing out of current subpackage: e.g. `from ..shared import ...`
                top = module.split(".")[0] if module else ""
                if top:
                    found.add(top)
                else:
                    for alias in node.names:
                        found.add(alias.name)
    found.discard(current_domain)
    return found


def test_no_lateral_or_reverse_imports_across_domains():
    violations: list[str] = []
    for domain in ("shared", "part1", "part2", "part4"):
        for pyfile in sorted((PKG_ROOT / domain).rglob("*.py")):
            bad = _imported_domains(pyfile, domain) & FORBIDDEN_IMPORTS[domain]
            if bad:
                violations.append(f"{pyfile.relative_to(ROOT)} illegally imports {sorted(bad)}")
    bad_part3 = _imported_domains(PART3_SCRIPT, "part3") & FORBIDDEN_IMPORTS["part3"]
    if bad_part3:
        violations.append(f"part3_portfolio/Part3.py illegally imports {sorted(bad_part3)}")
    assert not violations, "\n".join(violations)


def test_no_bare_assert_or_numpy_testing_in_production_code():
    violations: list[str] = []
    files = list(PKG_ROOT.rglob("*.py")) + [PART3_SCRIPT]
    for pyfile in sorted(files):
        tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                violations.append(f"{pyfile.relative_to(ROOT)}:{node.lineno} uses bare assert")
            elif isinstance(node, ast.Attribute) and node.attr == "testing":
                if isinstance(node.value, ast.Name) and node.value.id in {"np", "numpy"}:
                    violations.append(f"{pyfile.relative_to(ROOT)}:{node.lineno} uses numpy.testing")
    assert not violations, "\n".join(violations)
