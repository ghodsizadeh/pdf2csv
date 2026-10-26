"""Keep the benchmark's corpus and its correctness metrics executable."""

import json
from pathlib import Path
import subprocess
import sys

from benchmarks.run import score

ROOT = Path(__file__).parents[1]


def test_offline_benchmark_matches_the_labelled_corpus(tmp_path):
    output = tmp_path / "results.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "benchmarks/run.py"),
            "--engine",
            "offline",
            "--runs",
            "1",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(report["results"]) == 8
    for item in report["results"]:
        assert item["actual_tables"] == item["expected_tables"] == item["exact_tables"]
        assert item["matched_cells"] == item["total_cells"]


def test_benchmark_penalizes_extra_or_reordered_tables():
    table = {"columns": ["Name", "Score"], "rows": [["Ada", 10]]}
    extra = score([table, table], [table])
    assert extra["matched_cells"] < extra["total_cells"]
    changed = {"columns": ["Score", "Name"], "rows": [[10, "Ada"]]}
    assert score([changed], [table])["exact_tables"] == 0
