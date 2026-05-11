"""
core/utils.py

Shared constants, JSON cleanup helpers, and formatting utilities.
"""

from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Named constants — UI
# ---------------------------------------------------------------------------
APP_TITLE = "Tender Analyzer — Precision Engine"
APP_GEOMETRY = "1280x820"
APP_MIN_WIDTH = 1050
APP_MIN_HEIGHT = 720
SIDEBAR_WIDTH = 240

# ---------------------------------------------------------------------------
# Named constants — Processing
# ---------------------------------------------------------------------------
TABLE_PADDING_PX = 5          # Extra padding around pdfplumber table bboxes

# Required keys in the Ollama JSON response
REQUIRED_JSON_KEYS: tuple[str, ...] = (
    "emd_fee",
    "processing_fee",
    "manufacturer_documents",
    "bidder_documents",
    "product_supply_requirements",
    "email_draft",
)

# ---------------------------------------------------------------------------
# Colours (referenced by views for custom drawing)
# ---------------------------------------------------------------------------
COLOR_ACCENT_BLUE = "#1f6feb"
COLOR_ACCENT_BLUE_HOVER = "#388bfd"
COLOR_SIDEBAR_BG = "#161b22"
COLOR_CARD_BG = "#0d1117"
COLOR_CARD_BORDER = "#30363d"
COLOR_TEXT_PRIMARY = "#e6edf3"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_SUCCESS = "#3fb950"
COLOR_WARNING = "#d29922"
COLOR_DANGER = "#f85149"
COLOR_ACTIVE_ROW = "#1c2d4a"

# ---------------------------------------------------------------------------
# JSON cleanup helpers
# ---------------------------------------------------------------------------

def clean_json_response(raw: str) -> str:
    """
    Aggressively strip markdown formatting and conversational text from an
    Ollama response so that only a bare JSON object remains.

    Strategy:
      1. Remove fenced code blocks (```json ... ``` or ``` ... ```)
      2. Slice from the first '{' to the last '}'
      3. Strip surrounding whitespace
    """
    # Remove fenced code blocks
    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned)

    # Find the outermost JSON object boundaries
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "No valid JSON object boundaries found in the model response."
        )

    return cleaned[start : end + 1].strip()


def parse_strict_json(raw_response: str) -> dict[str, Any]:
    """
    Clean the raw Ollama response, parse it as JSON, and validate that all
    required keys are present.

    Raises:
        ValueError: If JSON is malformed or required keys are missing.
    """
    cleaned = clean_json_response(raw_response)
    data: dict[str, Any] = json.loads(cleaned)

    missing = [k for k in REQUIRED_JSON_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"Ollama response is missing required keys: {missing}"
        )

    return data


# ---------------------------------------------------------------------------
# PDF export helper
# ---------------------------------------------------------------------------

def export_results_to_pdf(data: dict[str, Any], output_path: str) -> None:
    """
    Export tender analysis results to a formatted PDF file using reportlab.

    Args:
        data:        Parsed analysis dict (output of parse_strict_json).
        output_path: Absolute path where the PDF should be saved.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()

    # --- Custom paragraph styles ---
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#1f6feb"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0d1117"),
        spaceBefore=14,
        spaceAfter=4,
    )
    subheading_style = ParagraphStyle(
        "SubheadingStyle",
        parent=styles["Heading3"],
        fontSize=10,
        textColor=colors.HexColor("#8b949e"),
        spaceBefore=10,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=16,
    )
    fee_style = ParagraphStyle(
        "FeeStyle",
        parent=styles["BodyText"],
        fontSize=18,
        textColor=colors.HexColor("#1f6feb"),
        fontName="Helvetica-Bold",
    )

    story = []

    # Title
    story.append(Paragraph("Tender Analysis Report", title_style))
    story.append(Paragraph("Generated by Precision Engine", body_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#30363d")))
    story.append(Spacer(1, 0.3 * cm))

    # --- Financial Requirements ---
    story.append(Paragraph("Financial Requirements", heading_style))

    fee_data = [
        ["Earnest Money Deposit (EMD)", data.get("emd_fee", "N/A")],
        ["Tender Processing Fee", data.get("processing_fee", "N/A")],
    ]
    fee_table = Table(fee_data, colWidths=[9 * cm, 8 * cm])
    fee_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f6f8fa")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0d1117")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#30363d")),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ])
    )
    story.append(fee_table)
    story.append(Spacer(1, 0.4 * cm))

    # --- Manufacturer Documents ---
    story.append(Paragraph("Compliance Checklist", heading_style))
    story.append(Paragraph("MANUFACTURER DOCUMENTS", subheading_style))
    man_docs: list[str] = data.get("manufacturer_documents", [])
    for idx, doc in enumerate(man_docs, start=1):
        story.append(Paragraph(f"{idx}. {doc}", body_style))
    if not man_docs:
        story.append(Paragraph("None specified.", body_style))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("BIDDER DOCUMENTS", subheading_style))
    bid_docs: list[str] = data.get("bidder_documents", [])
    for idx, doc in enumerate(bid_docs, start=1):
        story.append(Paragraph(f"{idx}. {doc}", body_style))
    if not bid_docs:
        story.append(Paragraph("None specified.", body_style))

    # --- Product Supply Requirements ---
    story.append(Paragraph("Product Supply Requirements", heading_style))
    supply_reqs: list[str] = data.get("product_supply_requirements", [])
    for idx, req in enumerate(supply_reqs, start=1):
        story.append(Paragraph(f"{idx}. {req}", body_style))
    if not supply_reqs:
        story.append(Paragraph("None specified.", body_style))

    # --- Email Draft ---
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#30363d")))
    story.append(Paragraph("Email Outreach Draft", heading_style))
    email_text: str = data.get("email_draft", "No email draft generated.")
    # Escape HTML special chars for Paragraph
    email_text_escaped = (
        email_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    story.append(Paragraph(email_text_escaped, body_style))

    doc.build(story)
