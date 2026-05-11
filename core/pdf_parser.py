"""
core/pdf_parser.py

Dual-library PDF extraction:
  - pdfplumber  : Detect and extract tables with bounding boxes.
  - PyMuPDF (fitz): Extract remaining text, excluding table regions.

Reading order is maintained by processing content page-by-page and
interleaving table data at the correct vertical position within each page.
"""

from __future__ import annotations

import gc

from core.utils import TABLE_PADDING_PX


def _table_to_text(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table (list of rows) to a readable string."""
    lines: list[str] = []
    for row in table:
        cleaned_cells = [str(cell).strip() if cell is not None else "" for cell in row]
        lines.append(" | ".join(cleaned_cells))
    return "\n".join(lines)


def _bbox_with_padding(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Expand a bounding box by TABLE_PADDING_PX on all sides."""
    x0, y0, x1, y1 = bbox
    pad = float(TABLE_PADDING_PX)
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def parse_pdf(pdf_path: str) -> str:
    """
    Extract and merge text and table content from a PDF file, maintaining
    the sequential reading order of the original document.

    Args:
        pdf_path: Absolute path to the PDF file.

    Returns:
        A single string containing all extracted content, ready to be sent
        to the Ollama model.

    Raises:
        FileNotFoundError: If the PDF path does not exist.
        RuntimeError:      If the PDF cannot be opened or parsed.
    """
    full_content_parts: list[str] = []

    # Lazy-load heavy C-extension libraries — only when the user starts an analysis
    import fitz  # PyMuPDF
    import pdfplumber

    with pdfplumber.open(pdf_path) as plumber_doc:
        fitz_doc = fitz.open(pdf_path)

        try:
            for page_index in range(len(plumber_doc.pages)):
                plumber_page = plumber_doc.pages[page_index]
                fitz_page = fitz_doc[page_index]

                page_parts: list[tuple[float, str]] = []  # (y_position, content)

                # ----------------------------------------------------------
                # Step 1: Extract tables via pdfplumber
                # ----------------------------------------------------------
                table_bboxes_padded: list[tuple[float, float, float, float]] = []
                tables = plumber_page.find_tables()

                for tbl in tables:
                    raw_table = tbl.extract()
                    if not raw_table:
                        continue

                    table_text = _table_to_text(raw_table)
                    bbox = tbl.bbox  # (x0, top, x1, bottom) in pdfplumber coords
                    y_mid = (bbox[1] + bbox[3]) / 2.0

                    page_parts.append((y_mid, f"\n[TABLE]\n{table_text}\n[/TABLE]\n"))
                    table_bboxes_padded.append(_bbox_with_padding(bbox))

                # ----------------------------------------------------------
                # Step 2: Extract text via PyMuPDF, clipping out table regions
                # ----------------------------------------------------------
                # pdfplumber uses (x0, top, x1, bottom) with top=0 at page top.
                # PyMuPDF uses (x0, y0, x1, y1) with y0=0 at page top.
                # The coordinate systems are compatible for our purposes.

                # Build exclusion clip rectangles
                exclude_rects = [fitz.Rect(*bbox) for bbox in table_bboxes_padded]

                # Extract words with their positions; filter out those inside
                # any excluded (table) region.
                word_list = fitz_page.get_text("words")  # [(x0,y0,x1,y1,word,blk,ln,wrd)]

                # Group words by their approximate line (quantised y0)
                line_map: dict[int, list[tuple[float, str]]] = {}
                for word_data in word_list:
                    x0_w, y0_w, x1_w, y1_w, word_str = (
                        word_data[0], word_data[1],
                        word_data[2], word_data[3],
                        word_data[4],
                    )
                    word_rect = fitz.Rect(x0_w, y0_w, x1_w, y1_w)

                    # Skip words that fall inside any table bounding box
                    if any(word_rect.intersects(excl) for excl in exclude_rects):
                        continue

                    # Quantise y to group words on the same line (±3px tolerance)
                    y_key = int(y0_w / 3) * 3
                    if y_key not in line_map:
                        line_map[y_key] = []
                    line_map[y_key].append((x0_w, word_str))

                # Reconstruct lines in top-to-bottom order
                for y_key in sorted(line_map.keys()):
                    words_on_line = sorted(line_map[y_key], key=lambda t: t[0])
                    line_text = " ".join(w for _, w in words_on_line)
                    if line_text.strip():
                        page_parts.append((float(y_key), line_text))

                # ----------------------------------------------------------
                # Step 3: Sort all parts by vertical position and combine
                # ----------------------------------------------------------
                page_parts.sort(key=lambda t: t[0])
                full_content_parts.append(
                    "\n".join(text for _, text in page_parts)
                )

                # Release page-level resources to reduce peak memory
                del word_list, line_map, page_parts
                del fitz_page, plumber_page

        finally:
            fitz_doc.close()

    # Nudge the garbage collector after releasing both document handles
    gc.collect()

    return "\n\n--- PAGE BREAK ---\n\n".join(full_content_parts)
