"""Compare extractors on a labelled regression corpus, in separate environments."""

from __future__ import annotations

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import resource
import statistics
import time
import unicodedata

ROOT = Path(__file__).parents[1]


def canonical(value):
    """Ignore numeric storage dtype and whitespace, but not text/column order."""
    if isinstance(value, str):
        value = " ".join(unicodedata.normalize("NFKC", value).split())
        translated = value.translate(
            str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩−", "01234567890123456789-")
        )
        try:
            return float(translated)
        except ValueError:
            return value
    return value


def cells(table):
    return [
        canonical(value) for row in [table["columns"], *table["rows"]] for value in row
    ]


def score(actual, expected):
    """Strict positional matching penalizes missing/extra tables, rows and cells."""
    matched, total, exact = 0, 0, 0
    for index in range(max(len(actual), len(expected))):
        left = actual[index] if index < len(actual) else {"columns": [], "rows": []}
        right = (
            expected[index] if index < len(expected) else {"columns": [], "rows": []}
        )
        left_cells, right_cells = cells(left), cells(right)
        matched += sum(a == b for a, b in zip(left_cells, right_cells))
        total += max(len(left_cells), len(right_cells))
        exact += int(
            index < len(actual)
            and index < len(expected)
            and len(left["columns"]) == len(right["columns"])
            and len(left["rows"]) == len(right["rows"])
            and left_cells == right_cells
        )
    return {"exact_tables": exact, "matched_cells": matched, "total_cells": total}


def load_engine(name):
    if name == "offline":
        from pdf2csv import convert

        return convert, {
            "pdf2csv": version("pdf2csv"),
            "pdfplumber": version("pdfplumber"),
        }

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Compare born-digital extraction without OCR in both engines. Docling
    # model downloads are intentionally part of the first conversion time.
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(do_ocr=False)
            )
        }
    )

    def extract(path, *, rtl=False):
        import pandas as pd

        result = converter.convert(str(path))
        frames = [table.export_to_dataframe() for table in result.document.tables]
        # Reproduce main's numeric cleanup and explicit --rtl string reversal,
        # rather than penalizing Docling just for returning visual RTL text.
        for frame in frames:
            for column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="ignore")
            if rtl:
                for column in frame.select_dtypes(include=["object"]).columns:
                    frame[column] = frame[column].map(
                        lambda value: value[::-1] if isinstance(value, str) else value
                    )
                frame.columns = frame.columns.str[::-1]
        return frames

    return extract, {
        name: version(name)
        for name in [
            "docling",
            "docling-core",
            "docling-ibm-models",
            "torch",
            "scipy",
            "pandas",
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["offline", "docling"], required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    corpus = json.loads((ROOT / "benchmarks/corpus.json").read_text(encoding="utf-8"))
    report = {
        "engine": args.engine,
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "runs": args.runs,
        "ocr": False,
        "results": [],
    }
    started = time.perf_counter()
    try:
        extract, report["versions"] = load_engine(args.engine)
    except Exception as exc:
        report["setup_error"] = f"{type(exc).__name__}: {exc}"
        extract = None
    report["initialization_seconds"] = time.perf_counter() - started
    if extract is not None:
        for item in corpus:
            result = {
                "pdf": item["pdf"],
                "expected_tables": len(item["tables"]),
                "seconds": [],
            }
            for _ in range(args.runs):
                started = time.perf_counter()
                try:
                    frames = extract(ROOT / item["pdf"], rtl=item.get("rtl", False))
                    actual = [
                        {"columns": list(frame.columns), "rows": frame.values.tolist()}
                        for frame in frames
                    ]
                    result["actual_tables"] = len(actual)
                    result.update(score(actual, item["tables"]))
                except Exception as exc:
                    result["error"] = f"{type(exc).__name__}: {exc}"
                    result.update(
                        actual_tables=0,
                        exact_tables=0,
                        matched_cells=0,
                        total_cells=sum(len(cells(table)) for table in item["tables"]),
                    )
                result["seconds"].append(time.perf_counter() - started)
                if "error" in result:
                    break
            result["median_seconds"] = statistics.median(result["seconds"])
            report["results"].append(result)
            print(
                f'{item["pdf"]}: {result.get("exact_tables", 0)}/{result["expected_tables"]} exact tables'
            )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["peak_rss_bytes"] = peak if platform.system() == "Darwin" else peak * 1024
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return int(
        "setup_error" in report
        or any("error" in result for result in report["results"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
