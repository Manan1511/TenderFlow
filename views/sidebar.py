"""
views/sidebar.py

Sidebar navigation frame for the Tender Analyzer application.
Displays: App branding, primary CTA, navigation items, and bottom utilities.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from core.utils import (
    COLOR_ACCENT_BLUE,
    COLOR_ACTIVE_ROW,
    COLOR_SIDEBAR_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    SIDEBAR_WIDTH,
)


class SidebarFrame(ctk.CTkFrame):
    """
    Fixed-width sidebar containing app branding, navigation, and utilities.

    Navigation items emit a callback when clicked so the main window can
    perform the view switch without the sidebar knowing about the other views.
    """

    _NAV_ITEMS: list[tuple[str, str]] = [
        ("dashboard", "⊞  Dashboard"),
        ("analysis",  "⟳  Analysis"),
        ("outreach",  "✉  Outreach"),
    ]

    _BOTTOM_ITEMS: list[tuple[str, str]] = [
        ("support",  "?  Support"),
        ("settings", "⚙  Settings"),
    ]

    def __init__(
        self,
        master: ctk.CTk,
        on_nav: Callable[[str], None],
        on_new_analysis: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLOR_SIDEBAR_BG,
            **kwargs,
        )
        self._on_nav = on_nav
        self._on_new_analysis = on_new_analysis
        self._active_key: str = "dashboard"
        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        self.grid_propagate(False)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # --- Branding ---
        branding_frame = ctk.CTkFrame(self, fg_color="transparent")
        branding_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 0))

        logo_label = ctk.CTkLabel(
            branding_frame,
            text="⬡",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLOR_ACCENT_BLUE,
        )
        logo_label.grid(row=0, column=0, sticky="w")

        title_label = ctk.CTkLabel(
            branding_frame,
            text="Precision Engine",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        title_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        tier_label = ctk.CTkLabel(
            branding_frame,
            text="Enterprise Tier",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        )
        tier_label.grid(row=1, column=1, sticky="w", padx=(10, 0))

        # --- Primary CTA ---
        cta_button = ctk.CTkButton(
            self,
            text="＋  New Tender Analysis",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#1a5dc8",
            corner_radius=8,
            height=40,
            command=self._on_new_analysis,
        )
        cta_button.grid(row=1, column=0, sticky="ew", padx=16, pady=(20, 4))

        # --- Navigation items ---
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        nav_frame.grid_columnconfigure(0, weight=1)

        for row_idx, (key, label) in enumerate(self._NAV_ITEMS):
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                font=ctk.CTkFont(size=12),
                anchor="w",
                corner_radius=6,
                height=38,
                fg_color="transparent",
                text_color=COLOR_TEXT_SECONDARY,
                hover_color=COLOR_ACTIVE_ROW,
                command=lambda k=key: self._handle_nav(k),
            )
            btn.grid(row=row_idx, column=0, sticky="ew", padx=10, pady=2)
            self._nav_buttons[key] = btn

        # Spacer that pushes bottom items down
        spacer = ctk.CTkFrame(self, fg_color="transparent", height=1)
        spacer.grid(row=3, column=0, sticky="nsew")
        self.grid_rowconfigure(3, weight=1)

        # --- Divider ---
        divider = ctk.CTkFrame(self, fg_color="#30363d", height=1, corner_radius=0)
        divider.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 6))

        # --- Bottom utility items ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=5, column=0, sticky="ew", pady=(0, 16))
        bottom_frame.grid_columnconfigure(0, weight=1)

        for row_idx, (key, label) in enumerate(self._BOTTOM_ITEMS):
            btn = ctk.CTkButton(
                bottom_frame,
                text=label,
                font=ctk.CTkFont(size=11),
                anchor="w",
                corner_radius=6,
                height=34,
                fg_color="transparent",
                text_color=COLOR_TEXT_SECONDARY,
                hover_color=COLOR_ACTIVE_ROW,
                command=lambda k=key: self._handle_nav(k),
            )
            btn.grid(row=row_idx, column=0, sticky="ew", padx=10, pady=1)

        # Apply initial active state
        self.set_active("dashboard")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active(self, key: str) -> None:
        """Highlight the nav button for *key* and dim all others."""
        self._active_key = key
        for nav_key, btn in self._nav_buttons.items():
            if nav_key == key:
                btn.configure(
                    fg_color=COLOR_ACTIVE_ROW,
                    text_color=COLOR_TEXT_PRIMARY,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLOR_TEXT_SECONDARY,
                )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_nav(self, key: str) -> None:
        self.set_active(key)
        self._on_nav(key)
