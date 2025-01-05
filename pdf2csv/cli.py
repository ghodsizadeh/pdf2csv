import logging
import typer
from typing import Optional

from pdf2csv.converter import convert

app = typer.Typer(help="CLI tool for converting PDF tables to CSV using Docling.")


@app.command()
def convert_cli(
    pdf_path: str = typer.Argument(..., help="Path to the input PDF file."),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Directory to save CSV files."
    ),
    ltr: bool = typer.Option(
        True, 
        "--ltr/--no-ltr",
        help="Whether to keep text in left-to-right format (default=True). "
             "Use '--no-ltr' to reverse the text."
    ),
    verbose: bool = typer.Option(
        False, 
        "--verbose", 
        "-v", 
        help="Enable verbose (DEBUG) logging."
    ),
):
    """
    Convert a PDF file to CSV(s) and optionally store them in output_dir.
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logging.info(f"Starting conversion for {pdf_path}, ltr={ltr} ...")

    try:
        dfs = convert(pdf_path, output_dir=output_dir, ltr=ltr, index=False)
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
