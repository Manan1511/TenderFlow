"""
views/processing_view.py

Analysis progress screen.

Displays a step-by-step pipeline status matching mock screen 1:
  1. Parsing PDF structural hierarchy
  2. Extracting tabular data matrices
  3. Running context inference via Gemma AI
  4. Generating compliance matrix

Each step can be in one of three states: pending | active | done | error.
The main app drives state transitions via update_step() and set_progress().
"""

from __future__ import annotations

import time
from typing import Callable, Literal

import customtkinter as ctk

from core.utils import (
    COLOR_ACCENT_BLUE,
    COLOR_ACTIVE_ROW,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)

StepState = Literal["pending", "active", "done", "error"]

_STEP_ICONS: dict[StepState, str] = {
    "pending": "○",
    "active":  "⟳",
    "done":    "✓",
    "error":   "✗",
}

_STEP_COLORS: dict[StepState, str] = {
    "pending": COLOR_TEXT_SECONDARY,
    "active":  COLOR_ACCENT_BLUE,
    "done":    COLOR_SUCCESS,
    "error":   COLOR_DANGER,
}

_STEPS: list[tuple[str, str]] = [
    ("parsing",    "Parsing PDF structural hierarchy..."),
    ("tables",     "Extracting tabular data matrices..."),
    ("inference",  "Running context inference via Gemma AI..."),
    ("compliance", "Generating compliance matrix..."),
]


class ProcessingView(ctk.CTkFrame):
    """
    Step-by-step analysis progress screen.

    Public interface:
        update_step(key, state, elapsed_ms)  — Drive step state transitions
        set_progress(value)                  — Set progress bar 0.0–1.0
        start_spinner()                      — Start indeterminate animation
        stop_spinner()                       — Stop indeterminate animation
        reset()                              — Reset all steps to pending
    """

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkFrame,
        on_cancel: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_cancel = on_cancel
        self._step_icon_labels: dict[str, ctk.CTkLabel] = {}
        self._step_text_labels: dict[str, ctk.CTkLabel] = {}
        self._step_time_labels: dict[str, ctk.CTkLabel] = {}
        self._step_rows: dict[str, ctk.CTkFrame] = {}
        self._progress_bar: ctk.CTkProgressBar
        self._progress_label: ctk.CTkLabel

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Centre the card vertically and horizontally
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.grid(row=0, column=0)

        card = ctk.CTkFrame(
            outer,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            corner_radius=16,
            width=660,
        )
        card.pack(padx=40, pady=40)
        card.grid_columnconfigure(0, weight=1)

        # Icon
        ctk.CTkLabel(
            card,
            text="📋",
            font=ctk.CTkFont(size=48),
        ).grid(row=0, column=0, pady=(36, 8))

        # Title
        ctk.CTkLabel(
            card,
            text="Analyzing Document...",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=1, column=0)

        ctk.CTkLabel(
            card,
            text="Extracting requirements using Gemma AI",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=2, column=0, pady=(4, 20))

        # Progress bar row
        prog_row = ctk.CTkFrame(card, fg_color="transparent")
        prog_row.grid(row=3, column=0, sticky="ew", padx=36, pady=(0, 8))
        prog_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            prog_row,
            text="Overall Progress",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w")

        self._progress_label = ctk.CTkLabel(
            prog_row,
            text="0%",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_ACCENT_BLUE,
        )
        self._progress_label.grid(row=0, column=1, sticky="e")

        self._progress_bar = ctk.CTkProgressBar(
            card,
            mode="indeterminate",
            height=8,
            corner_radius=4,
            progress_color=COLOR_ACCENT_BLUE,
            fg_color="#1c2d4a",
        )
        self._progress_bar.grid(row=4, column=0, sticky="ew", padx=36, pady=(0, 20))

        # Step list frame
        steps_frame = ctk.CTkFrame(
            card,
            fg_color="#0a0f15",
            corner_radius=10,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
        )
        steps_frame.grid(row=5, column=0, sticky="ew", padx=36, pady=(0, 24))
        steps_frame.grid_columnconfigure(1, weight=1)

        for row_idx, (key, label) in enumerate(_STEPS):
            row_frame = ctk.CTkFrame(steps_frame, fg_color="transparent", corner_radius=6)
            row_frame.grid(row=row_idx, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)
            self._step_rows[key] = row_frame

            icon_lbl = ctk.CTkLabel(
                row_frame,
                text=_STEP_ICONS["pending"],
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=_STEP_COLORS["pending"],
                width=24,
            )
            icon_lbl.grid(row=0, column=0, padx=(12, 6), pady=10)
            self._step_icon_labels[key] = icon_lbl

            text_lbl = ctk.CTkLabel(
                row_frame,
                text=label,
                font=ctk.CTkFont(size=11, family="Courier New"),
                text_color=_STEP_COLORS["pending"],
                anchor="w",
            )
            text_lbl.grid(row=0, column=1, sticky="w", pady=10)
            self._step_text_labels[key] = text_lbl

            time_lbl = ctk.CTkLabel(
                row_frame,
                text="Pending",
                font=ctk.CTkFont(size=10),
                text_color=COLOR_TEXT_SECONDARY,
                width=70,
            )
            time_lbl.grid(row=0, column=2, padx=(6, 12), pady=10)
            self._step_time_labels[key] = time_lbl

        # Cancel button
        ctk.CTkButton(
            card,
            text="Cancel Analysis",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            hover_color="#2d1c1c",
            text_color=COLOR_TEXT_SECONDARY,
            corner_radius=8,
            height=38,
            width=180,
            command=self._on_cancel,
        ).grid(row=6, column=0, pady=(0, 32))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_step(
        self,
        key: str,
        state: StepState,
        elapsed_ms: int | None = None,
    ) -> None:
        """Update the icon, colour, and timing label for a pipeline step."""
        icon_lbl = self._step_icon_labels.get(key)
        text_lbl = self._step_text_labels.get(key)
        time_lbl = self._step_time_labels.get(key)
        row_frame = self._step_rows.get(key)

        if not (icon_lbl and text_lbl and time_lbl and row_frame):
            return

        color = _STEP_COLORS[state]
        icon_lbl.configure(text=_STEP_ICONS[state], text_color=color)
        text_lbl.configure(text_color=color)

        if state == "active":
            row_frame.configure(fg_color=COLOR_ACTIVE_ROW)
            time_lbl.configure(text="Active", text_color=COLOR_ACCENT_BLUE)
        elif state == "done" and elapsed_ms is not None:
            row_frame.configure(fg_color="transparent")
            time_lbl.configure(text=f"{elapsed_ms}ms", text_color=COLOR_SUCCESS)
        elif state == "error":
            row_frame.configure(fg_color="#2d1c1c")
            time_lbl.configure(text="Error", text_color=COLOR_DANGER)
        else:
            row_frame.configure(fg_color="transparent")
            time_lbl.configure(text="Pending", text_color=COLOR_TEXT_SECONDARY)

    def set_progress(self, value: float, label_text: str | None = None) -> None:
        """Set the progress bar to a determinate value (0.0–1.0)."""
        self._progress_bar.configure(mode="determinate")
        self._progress_bar.set(value)
        display = label_text if label_text else f"{int(value * 100)}%"
        self._progress_label.configure(text=display)

    def start_spinner(self) -> None:
        """Switch to indeterminate mode and start the animation."""
        self._progress_bar.configure(mode="indeterminate")
        self._progress_bar.start()
        self._progress_label.configure(text="Processing...")

    def stop_spinner(self) -> None:
        """Stop the indeterminate animation."""
        self._progress_bar.stop()

    def reset(self) -> None:
        """Reset all steps to pending state."""
        for key in self._step_icon_labels:
            self.update_step(key, "pending")
        self._progress_bar.configure(mode="determinate")
        self._progress_bar.set(0)
        self._progress_label.configure(text="0%")
