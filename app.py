"""
app.py — Tender Analyzer: Precision Engine

Entry point and main application orchestrator.

Architecture:
  - CustomTkinter dark-mode UI with a fixed sidebar + swappable content area
  - Background thread handles PDF parsing + Ollama inference
  - All UI updates from the background thread are routed through root.after()
"""

from __future__ import annotations

import threading
import time
from typing import Any

import customtkinter as ctk

from core.ollama_client import check_ollama_connection, generate_analysis
from core.pdf_parser import parse_pdf
from core.utils import (
    APP_GEOMETRY,
    APP_MIN_HEIGHT,
    APP_MIN_WIDTH,
    APP_TITLE,
    COLOR_ACCENT_BLUE,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
from views.processing_view import ProcessingView
from views.results_view import ResultsView
from views.sidebar import SidebarFrame
from views.upload_view import UploadView

# ---------------------------------------------------------------------------
# Theme setup (must happen before any CTk widget is instantiated)
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TenderAnalyzerApp:
    """
    Main application class.

    Manages:
      - Window creation and layout
      - View switching (upload → processing → results)
      - Background analysis thread lifecycle
      - Ollama health checks
    """

    def __init__(self) -> None:
        self._root = ctk.CTk()
        self._root.title(APP_TITLE)
        self._root.geometry(APP_GEOMETRY)
        self._root.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)

        # Analysis cancellation flag
        self._cancel_requested = threading.Event()
        self._analysis_thread: threading.Thread | None = None

        self._setup_layout()
        self._build_views()
        self._check_ollama_async()

    # ------------------------------------------------------------------
    # Layout & view construction
    # ------------------------------------------------------------------

    def _setup_layout(self) -> None:
        """Configure the root grid: sidebar col 0, content col 1."""
        self._root.grid_columnconfigure(0, weight=0, minsize=240)
        self._root.grid_columnconfigure(1, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

    def _build_views(self) -> None:
        """Instantiate sidebar and all content views."""
        self._sidebar = SidebarFrame(
            self._root,
            on_nav=self._handle_nav,
            on_new_analysis=self._navigate_to_upload,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        self._upload_view = UploadView(
            self._root,
            on_analyze=self._start_analysis,
        )

        self._processing_view = ProcessingView(
            self._root,
            on_cancel=self._handle_cancel,
        )

        self._results_view = ResultsView(
            self._root,
            on_new_analysis=self._navigate_to_upload,
        )

        # Start on the upload/dashboard view
        self._current_view: ctk.CTkFrame | None = None
        self._show_view(self._upload_view)

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def _show_view(self, view: ctk.CTkFrame) -> None:
        """Hide the current view and display *view* in the content area."""
        if self._current_view is not None:
            self._current_view.grid_forget()
        view.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._current_view = view

    def _navigate_to_upload(self) -> None:
        self._sidebar.set_active("dashboard")
        self._show_view(self._upload_view)
        self._check_ollama_async()

    # ------------------------------------------------------------------
    # Sidebar navigation handler
    # ------------------------------------------------------------------

    def _handle_nav(self, key: str) -> None:
        """Route sidebar navigation clicks to the appropriate view."""
        if key == "dashboard":
            self._show_view(self._upload_view)
            self._check_ollama_async()
        elif key == "analysis":
            # Only switch if we have results; otherwise go to upload
            if self._current_view is self._results_view:
                pass  # already there
            else:
                self._show_view(self._upload_view)
        elif key in ("outreach", "support", "settings"):
            # Outreach is a tab within results — navigate there if available
            if self._current_view is self._results_view:
                pass  # Results view has the Outreach tab built-in
            else:
                self._show_view(self._upload_view)

    # ------------------------------------------------------------------
    # Ollama health check
    # ------------------------------------------------------------------

    def _check_ollama_async(self) -> None:
        """Run the Ollama health check on a daemon thread."""
        def _check() -> None:
            is_online = check_ollama_connection()
            self._root.after(0, self._upload_view.update_engine_status, is_online)

        thread = threading.Thread(target=_check, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Analysis pipeline
    # ------------------------------------------------------------------

    def _start_analysis(self, pdf_path: str) -> None:
        """
        Validate Ollama is reachable, then launch the background analysis thread.
        """
        if not check_ollama_connection():
            self._show_ollama_error_dialog()
            return

        self._cancel_requested.clear()
        self._processing_view.reset()
        self._show_view(self._processing_view)
        self._sidebar.set_active("analysis")

        self._processing_view.start_spinner()

        self._analysis_thread = threading.Thread(
            target=self._run_analysis_pipeline,
            args=(pdf_path,),
            daemon=True,
        )
        self._analysis_thread.start()

    def _run_analysis_pipeline(self, pdf_path: str) -> None:
        """
        Background thread: orchestrates PDF parsing and Ollama inference.
        All UI mutations are routed through root.after() for thread safety.
        """
        # --- Step 1: Parse PDF ---
        self._root.after(0, self._processing_view.update_step, "parsing", "active")
        t_start = time.perf_counter()

        try:
            parsed_text = parse_pdf(pdf_path)
        except Exception as exc:  # noqa: BLE001
            self._root.after(0, self._processing_view.update_step, "parsing", "error")
            self._root.after(0, self._on_pipeline_error, f"PDF parsing failed: {exc}")
            return

        if self._cancel_requested.is_set():
            return

        elapsed_parse = int((time.perf_counter() - t_start) * 1000)
        self._root.after(0, self._processing_view.update_step, "parsing", "done", elapsed_parse)
        self._root.after(0, self._processing_view.set_progress, 0.25, "25%")

        # --- Step 2: Tables extracted (part of parse_pdf; report separately) ---
        self._root.after(0, self._processing_view.update_step, "tables", "active")
        # Brief pause to let the UI update visually before the next heavy op
        time.sleep(0.3)

        if self._cancel_requested.is_set():
            return

        self._root.after(0, self._processing_view.update_step, "tables", "done", elapsed_parse)
        self._root.after(0, self._processing_view.set_progress, 0.50, "50%")

        # --- Step 3: Ollama inference ---
        self._root.after(0, self._processing_view.update_step, "inference", "active")
        t_infer = time.perf_counter()

        try:
            result: dict[str, Any] = generate_analysis(parsed_text)
        except Exception as exc:  # noqa: BLE001
            self._root.after(0, self._processing_view.update_step, "inference", "error")
            self._root.after(0, self._on_pipeline_error, f"AI inference failed: {exc}")
            return

        if self._cancel_requested.is_set():
            return

        elapsed_infer = int((time.perf_counter() - t_infer) * 1000)
        self._root.after(0, self._processing_view.update_step, "inference", "done", elapsed_infer)
        self._root.after(0, self._processing_view.set_progress, 0.80, "80%")

        # --- Step 4: Build compliance matrix (fast, local) ---
        self._root.after(0, self._processing_view.update_step, "compliance", "active")
        time.sleep(0.4)

        if self._cancel_requested.is_set():
            return

        self._root.after(0, self._processing_view.update_step, "compliance", "done", 0)
        self._root.after(0, self._processing_view.set_progress, 1.0, "100%")
        self._root.after(0, self._processing_view.stop_spinner)

        # --- Transition to results view ---
        self._root.after(500, self._on_pipeline_success, result)

    # ------------------------------------------------------------------
    # Pipeline callbacks (always called on the main thread via root.after)
    # ------------------------------------------------------------------

    def _on_pipeline_success(self, result: dict[str, Any]) -> None:
        self._results_view.populate(result)
        self._show_view(self._results_view)
        self._sidebar.set_active("analysis")

    def _on_pipeline_error(self, message: str) -> None:
        self._processing_view.stop_spinner()
        self._show_error_dialog("Analysis Error", message)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _handle_cancel(self) -> None:
        """Signal the background thread to stop and return to upload view."""
        self._cancel_requested.set()
        self._processing_view.stop_spinner()
        self._navigate_to_upload()

    # ------------------------------------------------------------------
    # Error dialogs
    # ------------------------------------------------------------------

    def _show_ollama_error_dialog(self) -> None:
        """Show a dedicated error window when Ollama is not reachable."""
        dialog = ctk.CTkToplevel(self._root)
        dialog.title("Ollama Not Running")
        dialog.geometry("460x280")
        dialog.resizable(False, False)
        dialog.grab_set()  # Modal behaviour
        dialog.lift()

        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="⚠",
            font=ctk.CTkFont(size=48),
            text_color=COLOR_DANGER,
        ).grid(row=0, column=0, pady=(28, 4))

        ctk.CTkLabel(
            dialog,
            text="Ollama is not running",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).grid(row=1, column=0)

        ctk.CTkLabel(
            dialog,
            text=(
                "The application could not connect to the local Ollama server\n"
                "at http://localhost:11434\n\n"
                "Please start Ollama and try again."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="center",
        ).grid(row=2, column=0, pady=(10, 20))

        ctk.CTkButton(
            dialog,
            text="Close",
            width=120,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            command=dialog.destroy,
        ).grid(row=3, column=0, pady=(0, 28))

    def _show_error_dialog(self, title: str, message: str) -> None:
        """Generic error dialog."""
        dialog = ctk.CTkToplevel(self._root)
        dialog.title(title)
        dialog.geometry("480x240")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="✗  Error",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_DANGER,
        ).grid(row=0, column=0, pady=(24, 8))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=420,
            justify="center",
        ).grid(row=1, column=0, padx=24, pady=(0, 20))

        ctk.CTkButton(
            dialog,
            text="Close",
            width=120,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            command=dialog.destroy,
        ).grid(row=2, column=0, pady=(0, 24))

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self._root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = TenderAnalyzerApp()
    app.run()
