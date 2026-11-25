import pytest

from sta4020_project.part4 import cli, report
from sta4020_project.pipeline import sample
from sta4020_project.shared.contracts import Paths


@pytest.fixture
def completed_report(tmp_path):
    out_dir = tmp_path / "part4_evaluation" / "reports" / "final"
    files = {
        "manifest.json": '{"tag": "final"}\n',
        "REPORT.md": "# Completed report\n",
        "tables/performance_summary.csv": "model,return\noriginal,0.1\n",
    }
    for name, content in files.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    yield out_dir

    existing = {
        path.relative_to(out_dir).as_posix() for path in out_dir.rglob("*") if path.is_file()
    }
    assert existing == files.keys()
    for name, content in files.items():
        assert (out_dir / name).read_text(encoding="utf-8") == content


def test_evaluate_cli_rejects_completed_report(completed_report):
    with pytest.raises(FileExistsError, match="contains a completed final run"):
        cli.main(["--out", str(completed_report)])


def test_sample_cli_rejects_completed_report(completed_report, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(sample.contracts, "Paths", lambda: paths)
    monkeypatch.setattr(sample, "run_part3", lambda *_: tmp_path / "Portfolio_Weights.csv")

    with pytest.raises(FileExistsError, match="contains a completed final run"):
        sample.main(["--tag", "final"])


def test_report_writer_rejects_completed_report(completed_report):
    with pytest.raises(FileExistsError, match="contains a completed final run"):
        report.write_report({}, cli.BENCHMARK, completed_report)
