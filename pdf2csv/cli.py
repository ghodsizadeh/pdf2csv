import logging
import typer
from typing import Optional, Literal  # Add Literal

from pdf2csv.converter import convert

app = typer.Typer(help="CLI tool for converting PDF tables to CSV using Docling.")


@app.command()
def convert_cli(
    pdf_path: str = typer.Argument(..., help="Path to the input PDF file."),
    output_dir: Optional[str] = typer.Option(
        ".", "--output-dir", "-o", help="Directory to save output files."
    ),
    rtl: bool = typer.Option(
        False,
        "--rtl/--no-rtl",
        help="Whether to reverse text for right-to-left format (default=False). "
        "Use '--rtl' to reverse the text.",
    ),
    output_format: Literal[
        "csv", "xlsx"
    ] = typer.Option(  # Update output_format parameter
        "csv",
        "--output-format",
        "-f",
        help="Format to save the output files. Options are 'csv' and 'xlsx'. Defaults to 'csv'.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose (DEBUG) logging."
    ),
):
    """
    Convert a PDF file to CSV(s) or XLSX(s) and optionally store them in output_dir.
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logging.info(
        f"Starting conversion for {pdf_path}, rtl={rtl}, output_format={output_format} ..."
    )

    try:
        dfs = convert(
            pdf_path,
            output_dir=output_dir,
            rtl=rtl,
            output_format=output_format,
            index=False,
        )
        logging.info(f"Extracted {len(dfs)} table(s) from {pdf_path}.")
    except FileNotFoundError as fnf_err:
        logging.error(str(fnf_err))
    except Exception as exc:
        logging.error(f"Error during PDF conversion: {exc}", exc_info=True)


def main():
    """
    Entry point for the CLI.
    """
    app()


if __name__ == "__main__":
    main()
