"""Command line interface for pdf2csv."""

from enum import Enum
import logging
from typing import Optional

import typer

from pdf2csv.converter import convert
from pdf2csv.errors import Pdf2CsvError

app = typer.Typer(help="Extract tables from a PDF into CSV or Excel files.")


class OutputFormat(str, Enum):
    csv = "csv"
    xlsx = "xlsx"


@app.callback()
def callback():
    """Extract tables from a PDF into CSV or Excel files."""


@app.command()
def convert_cli(
    pdf_path: str = typer.Argument(..., help="Path to the input PDF file."),
    output_dir: Optional[str] = typer.Option(
        ".", "--output-dir", "-o", help="Directory to save output files."
    ),
    rtl: bool = typer.Option(
        False,
        "--rtl/--no-rtl",
        help="Force right-to-left glyph order inside cells. "
        "Arabic and Hebrew are detected automatically either way.",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.csv,
        "--output-format",
        "-f",
        help="Format to save the output files. Options are 'csv' and 'xlsx'. Defaults to 'csv'.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose (DEBUG) logging."
    ),
):
    """Convert tables in a PDF to CSV or XLSX files in output_dir."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logging.info(
        "Starting conversion for %s, rtl=%s, output_format=%s ...",
        pdf_path,
        rtl,
        output_format.value,
    )

    try:
        frames = convert(
            pdf_path,
            output_dir=output_dir,
            rtl=rtl,
            output_format=output_format.value,
            index=False,
        )
        logging.info("Extracted %s table(s) from %s.", len(frames), pdf_path)
    except (FileNotFoundError, Pdf2CsvError) as err:
        logging.error("%s", err)
        raise typer.Exit(code=1) from err
    except Exception as exc:
        logging.error("Error during PDF conversion: %s", exc, exc_info=True)
        raise typer.Exit(code=1) from exc


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
