"""
views/upload_view.py

Dashboard / Upload screen.

Layout:
  Left card  — Document upload zone with Browse button + selected file name
  Right card — Ollama engine status indicator
"""

from __future__ import annotations

import os
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from core.utils import (
    COLOR_ACCENT_BLUE,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    get_font,
)


class UploadView(ctk.CTkFrame):
    """
    The main landing / dashboard screen.

    Callbacks:
        on_analyze(pdf_path: str) — Called when the user clicks Analyze Tender
                                     with a valid PDF path selected.
    """

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkFrame,
        on_analyze: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_analyze = on_analyze
        self._selected_pdf: str = ""
        self._engine_status_label: ctk.CTkLabel
        self._engine_dot: ctk.CTkLabel
        self._file_icon_label: ctk.CTkLabel
        self._file_name_label: ctk.CTkLabel
        self._analyze_btn: ctk.CTkButton

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # ---- Header ----
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=36, pady=(28, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="TenderFlow Pro",
            font=get_font(size=22, weight="bold"),
            text_color=COLOR_ACCENT_BLUE,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header_frame,
            text="Data Ingestion",
            font=get_font(size=22, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        ctk.CTkLabel(
            header_frame,
            text="Upload new tender specifications or RFPs for automated parsing and compliance check.",
            font=get_font(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        # ---- Two-column cards row ----
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="nsew", padx=36, pady=24)
        cards_frame.grid_columnconfigure(0, weight=3)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)

        self._build_upload_card(cards_frame)
        self._build_status_card(cards_frame)

    def _build_upload_card(self, parent: ctk.CTkFrame) -> None:
        """Left card: upload drop-zone and browse button."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Document Upload",
            font=get_font(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 0))

        # Dashed-border drop zone (simulated with a styled inner frame)
        drop_zone = ctk.CTkFrame(
            card,
            fg_color="#0f1923",
            border_color="#2d4a6a",
            border_width=2,
            corner_radius=10,
        )
        drop_zone.grid(row=1, column=0, sticky="nsew", padx=20, pady=12)
        drop_zone.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        # File icon (Unicode approximation)
        ctk.CTkLabel(
            drop_zone,
            text="📄",
            font=get_font(size=40),
        ).grid(row=0, column=0, pady=(36, 6))

        ctk.CTkLabel(
            drop_zone,
            text="Select a PDF Tender File",
            font=get_font(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=1, column=0)

        ctk.CTkLabel(
            drop_zone,
            text="Maximum file size: 50 MB. Supported format: PDF.",
            font=get_font(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=2, column=0, pady=(2, 16))

        ctk.CTkButton(
            drop_zone,
            text="Browse Files",
            font=get_font(size=12, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            width=160,
            height=38,
            command=self._handle_browse,
        ).grid(row=3, column=0, pady=(0, 36))

        # --- Selected file badge ---
        badge = ctk.CTkFrame(
            card,
            fg_color="#0f1923",
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            corner_radius=20,
        )
        badge.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        badge.grid_columnconfigure(1, weight=1)

        self._file_icon_label = ctk.CTkLabel(
            badge,
            text="○",
            font=get_font(size=14),
            text_color=COLOR_TEXT_SECONDARY,
            width=20,
        )
        self._file_icon_label.grid(row=0, column=0, padx=(14, 6), pady=10)

        self._file_name_label = ctk.CTkLabel(
            badge,
            text="No file selected",
            font=get_font(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=360,
            justify="left",
        )
        self._file_name_label.grid(row=0, column=1, sticky="w", padx=(0, 14), pady=10)

        # Analyze Tender button
        self._analyze_btn = ctk.CTkButton(
            card,
            text="Analyze Tender  →",
            font=get_font(size=13, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            height=42,
            state="disabled",
            command=self._handle_analyze,
        )
        self._analyze_btn.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 20))

    def _build_status_card(self, parent: ctk.CTkFrame) -> None:
        """Right card: engine status indicator."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Engine Status",
            font=get_font(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6))

        # Divider
        ctk.CTkFrame(card, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0).grid(
            row=1, column=0, sticky="ew", padx=0,
        )

        # Status row
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.grid(row=2, column=0, sticky="ew", padx=20, pady=14)

        self._engine_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=get_font(size=14),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._engine_dot.grid(row=0, column=0, padx=(0, 6))

        self._engine_status_label = ctk.CTkLabel(
            status_row,
            text="Checking...",
            font=get_font(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._engine_status_label.grid(row=0, column=1, sticky="w")

        # Stats
        ctk.CTkFrame(card, fg_color=COLOR_CARD_BORDER, height=1, corner_radius=0).grid(
            row=3, column=0, sticky="ew", padx=0,
        )

        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=14)
        stats_frame.grid_columnconfigure((0, 1), weight=1)

        for col, (label, value) in enumerate([("Queue Load", "Minimal"), ("Avg Parse Time", "—")]):
            ctk.CTkLabel(
                stats_frame,
                text=label,
                font=get_font(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).grid(row=0, column=col, sticky="w")
            ctk.CTkLabel(
                stats_frame,
                text=value,
                font=get_font(size=15, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
            ).grid(row=1, column=col, sticky="w")

        # Model info
        ctk.CTkLabel(
            card,
            text="Model: gemma4:e4b\nEndpoint: localhost:11434",
            font=get_font(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left",
        ).grid(row=5, column=0, sticky="w", padx=20, pady=(0, 20))


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_engine_status(self, is_online: bool) -> None:
        """Update the engine status indicator (called from the main thread)."""
        if is_online:
            self._engine_dot.configure(text_color=COLOR_SUCCESS)
            self._engine_status_label.configure(
                text="System Online & Ready", text_color=COLOR_SUCCESS
            )
        else:
            self._engine_dot.configure(text_color=COLOR_DANGER)
            self._engine_status_label.configure(
                text="System Offline — Start Ollama", text_color=COLOR_DANGER
            )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF Tender File",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if path:
            self._selected_pdf = path
            file_name = os.path.basename(path)
            # Update badge to "selected" state
            self._file_icon_label.configure(text="●", text_color=COLOR_SUCCESS)
            self._file_name_label.configure(
                text=file_name,
                text_color=COLOR_TEXT_PRIMARY,
            )
            self._analyze_btn.configure(state="normal")

    def _handle_analyze(self) -> None:
        if self._selected_pdf:
            self._on_analyze(self._selected_pdf)
