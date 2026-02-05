import argparse
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup


def extract_cell_text(td) -> str:
    """
    Extract fairly clean text from a table cell.

    - Converts <br> to spaces so the CSV stays strictly one line per entry.
    - Strips and normalizes whitespace.
    """
    # Replace <br> with a single space, then collapse多余空白，避免CSV里出现物理换行
    for br in td.find_all("br"):
        br.replace_with(" ")

    text = td.get_text(separator=" ", strip=True)
    # 把各种连续空白（含原来的换行）折叠成一个空格
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_image_info(td) -> str:
    """
    Extract image information from the 'Image' column, if present.
    Returns a semicolon-separated list of src values, or the cell text if no <img>.
    """
    imgs = td.find_all("img")
    if imgs:
        srcs = [img.get("src", "") for img in imgs if img.get("src")]
        return ";".join(srcs)
    return extract_cell_text(td)


def parse_hed_html(input_html: Path):
    """
    Parse the HED HTML file exported from Excel and yield each row as a list of strings.

    The main dictionary content lives in the table inside:
        <div id="z-alf_27758"> ... </div>

    Column headers (first row of the table) are kept as-is:
        号, 部, 画, 繁, 简, GPS, 汉拼, 英译与词句, gps#, Nos., Image
    """
    html_text = input_html.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html_text, "html.parser")

    container_div = soup.find("div", id="z-alf_27758")
    if container_div is None:
        raise RuntimeError("Could not find <div id='z-alf_27758'> in the HTML file.")

    main_table = container_div.find("table")
    if main_table is None:
        raise RuntimeError("Could not find main <table> inside the HED container div.")

    rows = main_table.find_all("tr")
    if not rows:
        raise RuntimeError("No <tr> rows found in the main table.")

    # Header row
    header_cells = rows[0].find_all("td")
    header = [extract_cell_text(td) for td in header_cells]
    num_cols = len(header)
    yield header

    # Data rows
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if not tds:
            continue

        # Some rows may be malformed; skip if they don't have enough cells.
        if len(tds) < num_cols:
            continue

        row_values = []
        for idx, td in enumerate(tds[:num_cols]):
            # The last column is the "Image" column in this table
            if idx == num_cols - 1:
                value = extract_image_info(td)
            else:
                value = extract_cell_text(td)
            row_values.append(value)

        yield row_values


def hed_html_to_csv(input_html: Path, output_csv: Path) -> None:
    """
    Convert the HED dictionary HTML file to a CSV with one row per dictionary entry.
    """
    rows = list(parse_hed_html(input_html))

    # Ensure parent directory exists
    if output_csv.parent:
        output_csv.parent.mkdir(parents=True, exist_ok=True)

    # Use utf-8-sig so that Excel on Windows will properly recognize UTF-8.
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def _norm_spaces(s: str) -> str:
    # Treat NBSP and other whitespace as normal spaces, collapse runs.
    s = s.replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _resolve_input_html(p: Path) -> Path:
    """
    Resolve an input HTML path.

    If the file doesn't exist (common when the real filename contains NBSP),
    try to find a best-match *.html in the same directory / current directory.
    """
    if p.exists():
        return p

    search_dir = p.parent if str(p.parent) not in ("", ".") else Path.cwd()
    candidates = sorted(search_dir.glob("*.html"))
    if not candidates:
        raise FileNotFoundError(f"No .html files found in: {search_dir}")

    target_norm = _norm_spaces(p.name)
    for c in candidates:
        if _norm_spaces(c.name) == target_norm:
            return c

    if len(candidates) == 1:
        return candidates[0]

    options = "\n".join(f"- {c.name!r}" for c in candidates[:20])
    more = "" if len(candidates) <= 20 else f"\n... and {len(candidates) - 20} more"
    raise FileNotFoundError(
        "Input HTML not found.\n"
        f"Given: {str(p)!r}\n"
        f"Searched in: {str(search_dir)!r}\n"
        "Tip: your real filename may contain non-breaking spaces (NBSP).\n"
        "Available .html files:\n"
        f"{options}{more}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert the HED Alphabetically (A-Y) October 2024 HTML "
        "dictionary into a CSV file."
    )
    parser.add_argument(
        "input_html",
        type=Path,
        nargs="?",
        help="Path to the HED HTML file (e.g. 'HED Alphabetically (A-Y) October 2024.html').",
    )
    parser.add_argument(
        "output_csv",
        type=Path,
        nargs="?",
        help="Path to the output CSV file (default: same directory, with .csv extension).",
    )

    args = parser.parse_args()

    # Hardcoded default (matches the real filename in this repo, including NBSPs).
    default_html = Path(__file__).resolve().with_name(
        "HED\u00A0Alphabetically\u00A0(A-Y)\u00A0October\u00A02024.html"
    )

    if args.input_html is None:
        input_html = default_html
    else:
        input_html = args.input_html

    input_html = _resolve_input_html(input_html)

    if args.output_csv is not None:
        output_csv = args.output_csv
    else:
        output_csv = input_html.with_suffix(".csv")

    hed_html_to_csv(input_html, output_csv)


if __name__ == "__main__":
    main()

