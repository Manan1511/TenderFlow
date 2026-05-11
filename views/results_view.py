"""
views/results_view.py

Results screen — Analysis tab and Outreach (email) tab.

Combines:
  - Financial Requirements (EMD + processing fee)
  - Compliance Checklist (manufacturer + bidder docs)
  - Product Supply Requirements
  - Email Outreach Draft with Copy button and PDF export
"""

from __future__ import annotations

import os
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk

from core.utils import (
    COLOR_ACCENT_BLUE,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    export_results_to_pdf,
    get_font,
)


class ResultsView(ctk.CTkFrame):
    """
    Displays the extracted tender analysis data across two tabs:
      Tab 1 — Analysis (fees, compliance checklist, supply requirements)
      Tab 2 — Outreach (email draft)

    Public API:
        populate(data: dict)  — Fills all widgets from a parsed JSON dict.
        clear()               — Clears the view back to an empty state.
    """

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkFrame,
        on_new_analysis: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_new_analysis = on_new_analysis
        self._data: dict[str, Any] = {}

        # Refs to dynamically populated widgets
        self._emd_label: ctk.CTkLabel
        self._proc_fee_label: ctk.CTkLabel
        self._man_docs_frame: ctk.CTkScrollableFrame
        self._bid_docs_frame: ctk.CTkScrollableFrame
        self._supply_frame: ctk.CTkScrollableFrame
        self._email_box: ctk.CTkTextbox
        self._toast_label: ctk.CTkLabel | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # --- Top bar ---
        self._build_top_bar()

        # --- Tab view — styled for prominence ---
        tab_view = ctk.CTkTabview(
            self,
            fg_color=COLOR_CARD_BG,
            # Active tab: vivid blue pill
            segmented_button_selected_color=COLOR_ACCENT_BLUE,
            segmented_button_selected_hover_color="#388bfd",
            # Inactive tab: slightly lighter than card bg so it reads as a button
            segmented_button_unselected_color="#1a2030",
            segmented_button_unselected_hover_color="#1c2d4a",
            # Outer card border
            border_color=COLOR_ACCENT_BLUE,
            border_width=2,
            corner_radius=12,
        )
        tab_view.grid(row=1, column=0, sticky="nsew", padx=36, pady=(0, 28))

        # Enlarge the segmented button bar for better visibility
        tab_view._segmented_button.configure(
            font=get_font(size=13, weight="bold"),
            height=40,
            corner_radius=8,
            border_width=2,
        )

        tab_analysis = tab_view.add("  Analysis  ")
        tab_outreach = tab_view.add("  Outreach  ")

        tab_analysis.grid_columnconfigure(0, weight=1)
        tab_analysis.grid_rowconfigure(1, weight=1)
        tab_outreach.grid_columnconfigure(0, weight=1)
        tab_outreach.grid_rowconfigure(0, weight=1)

        self._build_analysis_tab(tab_analysis)
        self._build_outreach_tab(tab_outreach)

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=36, pady=(28, 12))
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            left,
            text="ACTIVE ANALYSIS",
            font=get_font(size=9, weight="bold"),
            text_color=COLOR_ACCENT_BLUE,
            fg_color="#1c2d4a",
            corner_radius=4,
            padx=8,
            pady=3,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            left,
            text="Tender Analysis Results",
            font=get_font(size=22, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", rowspan=2)

        ctk.CTkButton(
            right,
            text="Export Report (PDF)",
            font=get_font(size=11),
            fg_color="transparent",
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            hover_color="#1c2d4a",
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=8,
            height=36,
            command=self._handle_export,
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            right,
            text="New Analysis",
            font=get_font(size=11, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            height=36,
            command=self._on_new_analysis,
        ).grid(row=0, column=1)

    def _build_analysis_tab(self, parent: ctk.CTkFrame) -> None:
        """Financial + Compliance + Supply requirements in a two-column layout."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Row 0 — Financial requirements (full width)
        self._build_financial_row(parent)

        # Row 1 — Compliance checklist (left) + Supply requirements (right)
        self._build_compliance_card(parent)
        self._build_supply_card(parent)

    def _build_financial_row(self, parent: ctk.CTkFrame) -> None:
        fin_frame = ctk.CTkFrame(
            parent,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        fin_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        fin_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            fin_frame,
            text="⬡  Financial Requirements",
            font=get_font(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 6))

        ctk.CTkFrame(fin_frame, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0).grid(
            row=1, column=0, columnspan=3, sticky="ew",
        )

        # EMD
        emd_col = ctk.CTkFrame(fin_frame, fg_color="transparent")
        emd_col.grid(row=2, column=0, sticky="nsew", padx=16, pady=14)

        ctk.CTkLabel(
            emd_col,
            text="EARNEST MONEY DEPOSIT (EMD)",
            font=get_font(size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w")

        self._emd_label = ctk.CTkLabel(
            emd_col,
            text="—",
            font=get_font(size=28, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        self._emd_label.grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(
            emd_col,
            text="Refundable post-award",
            font=get_font(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=2, column=0, sticky="w")

        # Divider
        ctk.CTkFrame(fin_frame, fg_color=COLOR_CARD_BORDER, width=1, corner_radius=0).grid(
            row=2, column=1, sticky="ns", pady=10,
        )

        # Processing fee
        proc_col = ctk.CTkFrame(fin_frame, fg_color="transparent")
        proc_col.grid(row=2, column=2, sticky="nsew", padx=16, pady=14)

        ctk.CTkLabel(
            proc_col,
            text="TENDER PROCESSING FEE",
            font=get_font(size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w")

        self._proc_fee_label = ctk.CTkLabel(
            proc_col,
            text="—",
            font=get_font(size=28, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        self._proc_fee_label.grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(
            proc_col,
            text="Non-refundable",
            font=get_font(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=2, column=0, sticky="w")

    def _build_compliance_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        card.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        # Row 2 is the unified scrollable frame — it takes all remaining height
        card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            card,
            text="☑  Compliance Checklist",
            font=get_font(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        ctk.CTkFrame(card, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0).grid(
            row=1, column=0, sticky="ew",
        )

        # Single scrollable frame for BOTH sections — no fixed height, fills card
        self._compliance_scroll = ctk.CTkScrollableFrame(
            card, fg_color="transparent"
        )
        self._compliance_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self._compliance_scroll.grid_columnconfigure(0, weight=1)

        # Create placeholder sub-frame references (populated in populate())
        # _man_docs_frame and _bid_docs_frame now point inside _compliance_scroll
        self._man_docs_frame = self._compliance_scroll
        self._bid_docs_frame = self._compliance_scroll

    def _build_supply_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        card.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            card,
            text="≡  Extracted Supply Requirements",
            font=get_font(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        ctk.CTkFrame(card, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0).grid(
            row=1, column=0, sticky="ew",
        )

        self._supply_frame = ctk.CTkScrollableFrame(
            card, fg_color="transparent"
        )
        self._supply_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        self._supply_frame.grid_columnconfigure(0, weight=1)

    def _build_outreach_tab(self, parent: ctk.CTkFrame) -> None:
        """Email outreach draft tab."""
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # Left — email draft
        left_card = ctk.CTkFrame(
            parent,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        left_card.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left_card.grid_columnconfigure(0, weight=1)
        left_card.grid_rowconfigure(2, weight=1)

        # Header
        header_row = ctk.CTkFrame(left_card, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        header_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_row,
            text="Email Outreach Draft",
            font=get_font(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header_row,
            text="● Draft Generated",
            font=get_font(size=10),
            text_color=COLOR_SUCCESS,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            left_card,
            text="Review the generated documentation request before dispatching to the manufacturer.",
            font=get_font(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        # Email textbox
        self._email_box = ctk.CTkTextbox(
            left_card,
            font=get_font(size=11, family="Courier New"),
            fg_color="#060a0f",
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            corner_radius=8,
            wrap="word",
            state="disabled",
        )
        self._email_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))

        # Action buttons
        btn_row = ctk.CTkFrame(left_card, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="📋  Copy Email",
            font=get_font(size=12, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            height=38,
            command=self._handle_copy_email,
        ).grid(row=0, column=0, padx=(0, 10))

        # Right — requested documents sidebar
        right_card = ctk.CTkFrame(
            parent,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right_card.grid_columnconfigure(0, weight=1)
        right_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_card,
            text="Requested Documents",
            font=get_font(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        self._req_docs_frame = ctk.CTkScrollableFrame(
            right_card, fg_color="transparent"
        )
        self._req_docs_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self._req_docs_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(self, data: dict[str, Any]) -> None:
        """Fill all UI elements from a validated analysis dict."""
        self._data = data

        # Financial
        self._emd_label.configure(text=data.get("emd_fee") or "Not specified")
        self._proc_fee_label.configure(text=data.get("processing_fee") or "Not specified")

        # Compliance checklist — both sections in one unified scrollable frame
        self._clear_frame(self._compliance_scroll)
        man_docs: list[str] = data.get("manufacturer_documents", [])
        bid_docs: list[str] = data.get("bidder_documents", [])
        self._populate_compliance_unified(
            self._compliance_scroll, man_docs, bid_docs
        )

        # Supply requirements
        self._clear_frame(self._supply_frame)
        supply_reqs: list[str] = data.get("product_supply_requirements", [])
        self._populate_supply_list(self._supply_frame, supply_reqs)

        # Email draft
        email_text: str = data.get("email_draft", "No email draft generated.")
        self._email_box.configure(state="normal")
        self._email_box.delete("0.0", "end")
        self._email_box.insert("0.0", email_text)
        self._email_box.configure(state="disabled")

        # Requested docs sidebar (same as manufacturer docs)
        self._clear_frame(self._req_docs_frame)
        self._populate_doc_sidebar(self._req_docs_frame, man_docs)

    def clear(self) -> None:
        """Reset all dynamic content."""
        self._data = {}
        self._emd_label.configure(text="—")
        self._proc_fee_label.configure(text="—")
        for frame in (
            self._compliance_scroll,
            self._supply_frame,
            self._req_docs_frame,
        ):
            self._clear_frame(frame)
        self._email_box.configure(state="normal")
        self._email_box.delete("0.0", "end")
        self._email_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_frame(frame: ctk.CTkScrollableFrame | ctk.CTkFrame) -> None:
        for widget in frame.winfo_children():
            widget.destroy()

    def _populate_compliance_unified(
        self,
        scroll: ctk.CTkScrollableFrame,
        man_docs: list[str],
        bid_docs: list[str],
    ) -> None:
        """
        Render manufacturer and bidder documents inside a single shared
        scrollable frame, separated by a section header each.
        """
        row_cursor = 0

        # --- Manufacturer section header ---
        ctk.CTkLabel(
            scroll,
            text="MANUFACTURER DOCUMENTS",
            font=get_font(size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=row_cursor, column=0, sticky="w", padx=6, pady=(8, 2))
        row_cursor += 1

        if man_docs:
            for item in man_docs:
                self._checklist_row(scroll, item, row_cursor)
                row_cursor += 1
        else:
            ctk.CTkLabel(
                scroll,
                text="None specified.",
                font=get_font(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).grid(row=row_cursor, column=0, sticky="w", padx=10, pady=2)
            row_cursor += 1

        # Spacer between sections
        ctk.CTkFrame(
            scroll, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0
        ).grid(row=row_cursor, column=0, sticky="ew", padx=4, pady=(8, 0))
        row_cursor += 1

        # --- Bidder section header ---
        ctk.CTkLabel(
            scroll,
            text="BIDDER DOCUMENTS",
            font=get_font(size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=row_cursor, column=0, sticky="w", padx=6, pady=(8, 2))
        row_cursor += 1

        if bid_docs:
            for item in bid_docs:
                self._checklist_row(scroll, item, row_cursor)
                row_cursor += 1
        else:
            ctk.CTkLabel(
                scroll,
                text="None specified.",
                font=get_font(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).grid(row=row_cursor, column=0, sticky="w", padx=10, pady=2)

    def _checklist_row(
        self,
        parent: ctk.CTkScrollableFrame,
        text: str,
        grid_row: int,
    ) -> None:
        """Render one checkbox-style card row at *grid_row*."""
        row = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD_BG,
            corner_radius=6,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        row.grid(row=grid_row, column=0, sticky="ew", pady=3, padx=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row,
            text="○",
            font=get_font(size=14),
            text_color=COLOR_TEXT_SECONDARY,
            width=24,
        ).grid(row=0, column=0, padx=(10, 6), pady=8)

        ctk.CTkLabel(
            row,
            text=text,
            font=get_font(size=11),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
            wraplength=300,
            justify="left",
        ).grid(row=0, column=1, sticky="w", pady=8, padx=(0, 10))

    def _populate_supply_list(
        self, frame: ctk.CTkScrollableFrame, items: list[str]
    ) -> None:
        """Render supply requirements as numbered rows."""
        if not items:
            ctk.CTkLabel(
                frame,
                text="None specified.",
                font=get_font(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
            return

        for idx, item in enumerate(items):
            row = ctk.CTkFrame(
                frame,
                fg_color=COLOR_CARD_BG if idx % 2 == 0 else "#0f1520",
                corner_radius=6,
            )
            row.grid(row=idx, column=0, sticky="ew", pady=2, padx=2)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=f"{idx + 1:02d}",
                font=get_font(size=10, weight="bold"),
                text_color=COLOR_ACCENT_BLUE,
                width=28,
            ).grid(row=0, column=0, padx=(10, 6), pady=8)

            ctk.CTkLabel(
                row,
                text=item,
                font=get_font(size=11),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w",
                wraplength=280,
                justify="left",
            ).grid(row=0, column=1, sticky="w", pady=8, padx=(0, 10))

    def _populate_doc_sidebar(
        self, frame: ctk.CTkScrollableFrame, items: list[str]
    ) -> None:
        """Render sidebar document cards."""
        if not items:
            ctk.CTkLabel(
                frame,
                text="No documents listed.",
                font=get_font(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
            return

        for idx, item in enumerate(items):
            card = ctk.CTkFrame(
                frame,
                fg_color=COLOR_CARD_BG,
                corner_radius=8,
                border_color=COLOR_CARD_BORDER,
                border_width=1,
            )
            card.grid(row=idx, column=0, sticky="ew", pady=4, padx=2)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                card,
                text="📄",
                font=get_font(size=16),
                width=30,
            ).grid(row=0, column=0, padx=(10, 6), pady=10)

            ctk.CTkLabel(
                card,
                text=item,
                font=get_font(size=10, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w",
                wraplength=180,
                justify="left",
            ).grid(row=0, column=1, sticky="w", pady=10, padx=(0, 10))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_copy_email(self) -> None:
        email_text = self._email_box.get("0.0", "end").strip()
        if not email_text:
            return
        self.clipboard_clear()
        self.clipboard_append(email_text)
        self._show_toast("✓  Draft copied to clipboard successfully.")

    def _handle_export(self) -> None:
        if not self._data:
            self._show_toast("⚠  No analysis data to export. Run an analysis first.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Export Analysis Report",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile="tender_analysis_report.pdf",
        )
        if not output_path:
            return

        try:
            export_results_to_pdf(self._data, output_path)
            self._show_toast(f"✓  Report exported to {os.path.basename(output_path)}")
        except Exception as exc:  # noqa: BLE001
            self._show_toast(f"✗  Export failed: {exc}")

    def _show_toast(self, message: str) -> None:
        """Display a transient toast notification at the bottom of the view."""
        if self._toast_label and self._toast_label.winfo_exists():
            self._toast_label.destroy()

        toast = ctk.CTkLabel(
            self,
            text=message,
            font=get_font(size=11, weight="bold"),
            text_color="#ffffff",
            fg_color="#1c2d4a",
            corner_radius=8,
            padx=16,
            pady=10,
        )
        toast.place(relx=0.5, rely=0.95, anchor="s")
        self._toast_label = toast
        # Auto-dismiss after 3 seconds
        self.after(3000, lambda: toast.destroy() if toast.winfo_exists() else None)
