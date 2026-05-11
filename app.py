"""
app.py — Tender Analyzer: Precision Engine

Entry point and main application orchestrator.

Architecture:
  - CustomTkinter dark-mode UI with a fixed sidebar + swappable content area
  - All views live in the same grid cell and are raised to front via tkraise()
    so there is never a blank-frame flash during transitions.
  - A LoadingOverlay (spinning braille-dot animation) is shown during
    transitions that involve heavy work, preventing perceived glitches.
  - Background thread handles PDF parsing + Ollama inference.
  - All UI updates from the background thread use root.after() for thread safety.
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


# ---------------------------------------------------------------------------
# Loading overlay widget
# ---------------------------------------------------------------------------

class _LoadingOverlay(ctk.CTkFrame):
    """
    A full-area overlay that shows a spinning braille-dot animation.

    Placed in the same grid cell as all content views and raised to the top
    during brief transitions to prevent any blank-frame flash.
    """

    _SPINNER_FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    _SPINNER_INTERVAL_MS = 80

    def __init__(self, master: ctk.CTkFrame, **kwargs: Any) -> None:
        super().__init__(master, fg_color="#0d1117", **kwargs)
        self._frame_idx: int = 0
        self._after_id: str | None = None
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        centre = ctk.CTkFrame(self, fg_color="transparent")
        centre.grid(row=0, column=0)

        self._spinner_label = ctk.CTkLabel(
            centre,
            text=self._SPINNER_FRAMES[0],
            font=ctk.CTkFont(size=52),
            text_color=COLOR_ACCENT_BLUE,
        )
        self._spinner_label.grid(row=0, column=0, pady=(0, 10))

        self._status_label = ctk.CTkLabel(
            centre,
            text="Please wait...",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._status_label.grid(row=1, column=0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, message: str = "Please wait...") -> None:
        """Raise the overlay and start the spinner animation."""
        self._status_label.configure(text=message)
        self.tkraise()
        self._start_animation()

    def hide(self) -> None:
        """Stop the spinner (caller must raise the desired view afterwards)."""
        self._stop_animation()

    def set_message(self, message: str) -> None:
        self._status_label.configure(text=message)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_animation(self) -> None:
        self._stop_animation()
        self._animate()

    def _stop_animation(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:  # noqa: BLE001
                pass
            self._after_id = None

    def _animate(self) -> None:
        self._spinner_label.configure(text=self._SPINNER_FRAMES[self._frame_idx])
        self._frame_idx = (self._frame_idx + 1) % len(self._SPINNER_FRAMES)
        self._after_id = self.after(self._SPINNER_INTERVAL_MS, self._animate)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class TenderAnalyzerApp:
    """
    Main application class.

    Manages:
      - Window creation and layout
      - View switching via tkraise() — eliminates blank-frame flashing
      - Background analysis thread lifecycle
      - Ollama health checks
    """

    # Delay (ms) the loading overlay is shown before raising the next view.
    # Long enough to render one spinner frame, short enough to feel instant.
    _TRANSITION_DELAY_MS = 250

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
        """Configure root grid: sidebar col 0, content container col 1."""
        self._root.grid_columnconfigure(0, weight=0, minsize=240)
        self._root.grid_columnconfigure(1, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

    def _build_views(self) -> None:
        """
        Build the sidebar and stack all content views in a shared container.

        All views + the loading overlay are placed at the same grid position
        (row=0, col=0) inside _content_frame. Switching views uses tkraise()
        instead of grid_forget/grid, which eliminates the blank-frame flash.
        """
        self._sidebar = SidebarFrame(
            self._root,
            on_nav=self._handle_nav,
            on_new_analysis=self._navigate_to_upload,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # Shared container — all content views live inside this frame
        self._content_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # Instantiate all views in the same cell — Z-order determines what's visible
        self._upload_view = UploadView(
            self._content_frame,
            on_analyze=self._start_analysis,
        )
        self._upload_view.grid(row=0, column=0, sticky="nsew")

        self._processing_view = ProcessingView(
            self._content_frame,
            on_cancel=self._handle_cancel,
        )
        self._processing_view.grid(row=0, column=0, sticky="nsew")

        self._results_view = ResultsView(
            self._content_frame,
            on_new_analysis=self._navigate_to_upload,
        )
        self._results_view.grid(row=0, column=0, sticky="nsew")

        # Loading overlay — always on top during transitions
        self._loading_overlay = _LoadingOverlay(self._content_frame)
        self._loading_overlay.grid(row=0, column=0, sticky="nsew")

        # Start with upload view on top
        self._upload_view.tkraise()

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def _show_view(self, view: ctk.CTkFrame) -> None:
        """
        Instantly raise *view* to the front with no blank-frame flash.

        Uses tkraise() on pre-gridded views — the tkinter compositor always
        has something to draw, so there is no visible gap between views.
        """
        view.tkraise()

    def _show_view_with_spinner(
        self,
        view: ctk.CTkFrame,
        message: str = "Please wait...",
        delay_ms: int | None = None,
    ) -> None:
        """
        Show the loading spinner briefly, then raise *view*.

        Used for transitions that feel instantaneous but might cause a
        perception of lag (e.g. view with heavy widget construction).
        """
        delay = delay_ms if delay_ms is not None else self._TRANSITION_DELAY_MS
        self._loading_overlay.show(message)
        self._root.after(delay, self._finish_transition, view)

    def _finish_transition(self, view: ctk.CTkFrame) -> None:
        self._loading_overlay.hide()
        view.tkraise()

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
            # Show results if available, otherwise go to upload
            self._show_view(self._results_view)
        elif key in ("outreach", "support", "settings"):
            # Outreach is a tab inside results_view
            self._show_view(self._results_view)

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
        """Validate Ollama is reachable, then launch the background thread."""
        # Show spinner while the connection check happens (it's a network call)
        self._loading_overlay.show("Connecting to Ollama...")

        def _check_and_launch() -> None:
            is_online = check_ollama_connection()
            if not is_online:
                self._root.after(0, self._loading_overlay.hide)
                self._root.after(0, self._upload_view.tkraise)
                self._root.after(0, self._show_ollama_error_dialog)
                return

            # Transition: show processing view
            self._root.after(0, self._prepare_processing_view, pdf_path)

        threading.Thread(target=_check_and_launch, daemon=True).start()

    def _prepare_processing_view(self, pdf_path: str) -> None:
        """Reset the processing view and start the analysis thread (main thread)."""
        self._cancel_requested.clear()
        self._processing_view.reset()
        self._loading_overlay.hide()
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
            self._root.after(0, self._on_pipeline_error, f"PDF parsing failed:\n{exc}")
            return

        if self._cancel_requested.is_set():
            return

        elapsed_parse = int((time.perf_counter() - t_start) * 1000)
        self._root.after(0, self._processing_view.update_step, "parsing", "done", elapsed_parse)
        self._root.after(0, self._processing_view.set_progress, 0.25, "25%")

        # --- Step 2: Report table extraction (done inside parse_pdf) ---
        self._root.after(0, self._processing_view.update_step, "tables", "active")
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
            self._root.after(0, self._on_pipeline_error, f"AI inference failed:\n{exc}")
            return

        if self._cancel_requested.is_set():
            return

        elapsed_infer = int((time.perf_counter() - t_infer) * 1000)
        self._root.after(0, self._processing_view.update_step, "inference", "done", elapsed_infer)
        self._root.after(0, self._processing_view.set_progress, 0.80, "80%")

        # --- Step 4: Compliance matrix ---
        self._root.after(0, self._processing_view.update_step, "compliance", "active")
        time.sleep(0.4)

        if self._cancel_requested.is_set():
            return

        self._root.after(0, self._processing_view.update_step, "compliance", "done", 0)
        self._root.after(0, self._processing_view.set_progress, 1.0, "100%")
        self._root.after(0, self._processing_view.stop_spinner)

        # Transition to results view — brief spinner so widget construction
        # doesn't cause a flash when the results view raises to front
        self._root.after(
            400,
            self._on_pipeline_success,
            result,
        )

    # ------------------------------------------------------------------
    # Pipeline callbacks (always called on the main thread via root.after)
    # ------------------------------------------------------------------

    def _on_pipeline_success(self, result: dict[str, Any]) -> None:
        # Populate first (off-screen), then show with a spinner transition
        self._results_view.populate(result)
        self._show_view_with_spinner(
            self._results_view,
            message="Building results...",
            delay_ms=300,
        )
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
        dialog.grab_set()
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
        """Generic error dialog with a scrollable message area."""
        dialog = ctk.CTkToplevel(self._root)
        dialog.title(title)
        dialog.geometry("520x280")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            dialog,
            text="✗  Error",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_DANGER,
        ).grid(row=0, column=0, pady=(24, 8))

        # Use a textbox so long error messages (e.g. the 500 explanation) are readable
        msg_box = ctk.CTkTextbox(
            dialog,
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_CARD_BG,
            text_color=COLOR_TEXT_SECONDARY,
            wrap="word",
            state="normal",
        )
        msg_box.insert("0.0", message)
        msg_box.configure(state="disabled")
        msg_box.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

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
