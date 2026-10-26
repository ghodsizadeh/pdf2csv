"""Run with the installed wheel's Python, outside the source package directory."""

from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

import pandas as pd

import pdf2csv


def main():
    root = Path(__file__).resolve().parents[1]
    expected = tomllib.loads((root / "pyproject.toml").read_text())["project"][
        "version"
    ]
    assert version("pdf2csv") == pdf2csv.__version__ == expected
    assert not Path(pdf2csv.__file__).resolve().is_relative_to(root / "pdf2csv")
    source = root / "examples/english_borderless_side_by_side.pdf"
    result = pdf2csv.extract_document(source, numeric="preserve")
    assert len(result.tables) == 2
    assert all(table.page_number == 1 for table in result.tables)
    assert result.tables[0].dataframe.values.tolist() == [
        ["Ada", "10"],
        ["Grace", "12"],
    ]
    assert result.tables[1].dataframe.values.tolist() == [
        ["Ada", "10"],
        ["Grace", "12"],
    ]
    with tempfile.TemporaryDirectory(prefix="pdf2csv-smoke-") as directory:
        work = Path(directory)
        help_result = subprocess.run(
            [sys.executable, "-m", "pdf2csv.cli", "--help"],
            cwd=work,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "convert-cli" in help_result.stdout
        for fmt in ("csv", "xlsx"):
            destination = work / fmt
            command = [
                sys.executable,
                "-m",
                "pdf2csv.cli",
                "convert",
                str(source),
                "-o",
                str(destination),
                "-f",
                fmt,
            ]
            subprocess.run(command, cwd=work, check=True)
            files = sorted(destination.glob(f"*.{fmt}"))
            assert len(files) == 2
            read = pd.read_csv if fmt == "csv" else pd.read_excel
            for number, output in enumerate(files, 1):
                expected_frame = pd.DataFrame(
                    {f"Name {number}": ["Ada", "Grace"], "Score": [10, 12]}
                )
                pd.testing.assert_frame_equal(read(output), expected_frame)
            before = [output.read_bytes() for output in files]
            collision = subprocess.run(
                command, cwd=work, capture_output=True, text=True
            )
            assert collision.returncode == 1 and "--overwrite" in collision.stderr
            assert [output.read_bytes() for output in files] == before
    print(f"Installed wheel {expected}: API, CLI, CSV/XLSX and collision checks passed")


if __name__ == "__main__":
    main()
