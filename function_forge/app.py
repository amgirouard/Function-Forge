"""app.py — Main application class for Function Forge.

Mirrors Fraction Forge's layout: top bar → controls row → canvas → shortcut bar.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import platform
import logging
import math
import subprocess
from io import BytesIO

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.patches as patches
import numpy as np

from .models import AppConstants, DrawingContext, GraphConfigProvider
from .validators import CoordinateValidator
from .drawers import GraphRegistry, get_random_params, random_graph_name

logger = logging.getLogger(__name__)

from .forge_widgets import (
    BTN_H,
    _StyledButton,
    _StyledEntry,
    _StyledStepper,
    _StyledCombobox,
    _StyledSlider,
    _StyledCheckbox,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tooltip
# ═══════════════════════════════════════════════════════════════════════════════

class _Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, event=None) -> None:
        if self._tip or not self._text:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self._text, justify="left",
                 bg="#ffffe0", relief="solid", borderwidth=1,
                 font=("Arial", 10), padx=4, pady=2).pack()

    def _hide(self, event=None) -> None:
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Export helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _show_batch_count_dialog(parent: tk.Widget) -> "int | None":
    """Modal dialog asking how many images to export. Returns count or None."""
    result: list = [None]
    dlg = tk.Toplevel(parent)
    dlg.title("Batch Export")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(bg=AppConstants.BG_COLOR)

    bg = AppConstants.BG_COLOR
    tk.Label(dlg, text="How many images to export?",
             bg=bg, font=("Arial", 11, "bold")).pack(pady=(16, 8), padx=20)

    count_var = tk.IntVar(value=10)

    preset_frame = tk.Frame(dlg, bg=bg)
    preset_frame.pack(pady=4, padx=20)
    for val in (5, 10, 25):
        _StyledButton(
            preset_frame, text=str(val),
            font=AppConstants.scaled_btn_font(),
            width=52, height=BTN_H,
            command=lambda v=val: count_var.set(v),
        ).pack(side=tk.LEFT, padx=4)

    custom_frame = tk.Frame(dlg, bg=bg)
    custom_frame.pack(pady=(4, 12), padx=20)
    tk.Label(custom_frame, text="Custom:", bg=bg,
             font=AppConstants.scaled_btn_font()).pack(side=tk.LEFT, padx=(0, 6))
    tk.Spinbox(custom_frame, from_=1, to=500, textvariable=count_var,
               width=6, font=AppConstants.scaled_btn_font()).pack(side=tk.LEFT)

    action_frame = tk.Frame(dlg, bg=bg)
    action_frame.pack(pady=(0, 16), padx=20)

    def _confirm() -> None:
        try:
            n = int(count_var.get())
            if n >= 1:
                result[0] = n
        except (ValueError, tk.TclError):
            pass
        dlg.destroy()

    _StyledButton(action_frame, text="Export",
                  font=AppConstants.scaled_btn_font(),
                  width=80, height=BTN_H,
                  command=_confirm).pack(side=tk.LEFT, padx=(0, 8))
    _StyledButton(action_frame, text="Cancel",
                  font=AppConstants.scaled_btn_font(),
                  width=70, height=BTN_H,
                  command=dlg.destroy).pack(side=tk.LEFT)

    dlg.update_idletasks()
    px = parent.winfo_rootx() + (parent.winfo_width() - dlg.winfo_reqwidth()) // 2
    py = parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_reqheight()) // 2
    dlg.geometry(f"+{px}+{py}")
    parent.wait_window(dlg)
    return result[0]


class _BatchProgressDialog:
    """Simple progress display during batch export."""

    def __init__(self, parent: tk.Widget, total: int) -> None:
        self.cancelled = False
        self._total = total
        dlg = tk.Toplevel(parent)
        dlg.title("Exporting\u2026")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=AppConstants.BG_COLOR)
        self._dlg = dlg

        bg = AppConstants.BG_COLOR
        self._lbl = tk.Label(dlg, text=f"Preparing {total} image\u2026",
                             bg=bg, font=("Arial", 11), pady=8, padx=20)
        self._lbl.pack()
        _StyledButton(dlg, text="Cancel",
                      font=AppConstants.scaled_btn_font(),
                      width=80, height=BTN_H,
                      command=self._on_cancel).pack(pady=(0, 12))

        dlg.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - dlg.winfo_reqwidth()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{px}+{py}")

    def update(self, current: int, model_name: str) -> None:
        self._lbl.config(text=f"Exporting {current} of {self._total}  ({model_name})")

    def _on_cancel(self) -> None:
        self.cancelled = True

    def destroy(self) -> None:
        self._dlg.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════════

class FunctionApp:
    """Main application class for Function Forge."""

    # Blended display colors for color swatches
    _SWATCH_DISPLAY: list[str] = [
        "#9BC2EA",  # Blue
        "#F29D94",  # Red
        "#8CE3B1",  # Green
        "#F8C97D",  # Orange
        "#C8A4D7",  # Purple
        "#81DAC9",  # Teal
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(AppConstants.WINDOW_TITLE)
        self._redraw_after_id: str | None = None

        # Current drawing state
        self._graph_color: str   = "#000000"   # black default (print mode)
        self._line_width: float  = AppConstants.DEFAULT_LINE_WIDTH * 2  # thicker default for print
        self._show_grid: bool    = True
        self._dot_style: str     = "closed"   # "closed" | "open"
        self._mapping_shape: str = "oval"     # "oval" | "rectangle"
        self._came_from_random: bool = False
        self._show_vlt: bool     = False
        self._grid_style: str    = "print"    # "print" | "color"
        self._show_xy_labels: bool = True
        self._current_params: dict = {}

        # UI widget placeholders
        self.fig = None
        self.canvas = None
        self.ax = None
        self.controls_row = None
        self.save_btn = None
        self.copy_btn = None
        self.batch_btn = None

        self._setup_data()
        self._setup_layout()
        self._setup_canvas_and_controllers()

    # ── Data ──────────────────────────────────────────────────────────────────

    def _setup_data(self) -> None:
        self.model_data = {
            "Graphs": [
                "Linear",
                "Smooth Curve",
                "Reciprocal",
                "Piecewise",
                "Step Function",
                "Parametric",
                "Scatter Plot",
            ],
            "Mappings": ["Mapping"],
            "Random": ["Random Graph"],
        }

    # ── Layout ────────────────────────────────────────────────────────────────

    def _setup_layout(self) -> None:
        canvas_w = 700
        canvas_h = int(canvas_w * 3 / 4)
        self._canvas_target_w = canvas_w
        self._canvas_target_h = canvas_h

        self._apply_global_fonts()

        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=0)
        self.root.rowconfigure(3, weight=0)
        self.root.columnconfigure(0, weight=1)

        self._create_top_bar()
        self._create_controls_row()
        self._create_canvas_area()
        self._create_shortcut_bar()

    def _create_top_bar(self) -> None:
        top_bar = tk.Frame(self.root, bg=AppConstants.BG_COLOR,
                           height=AppConstants.scaled_top_bar_height())
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_propagate(False)
        self.top_bar = top_bar

        self.center_container = tk.Frame(top_bar, bg=AppConstants.BG_COLOR)
        self.center_container.place(relx=0.5, rely=0.5, anchor="center")

        # Category selector
        self.cat_combo = _StyledCombobox(self.center_container,
                                          font=AppConstants.scaled_btn_font(),
                                          width=14,
                                          label="Category",
                                          bg=AppConstants.BG_COLOR)
        self.cat_combo["values"] = list(self.model_data.keys())
        self.cat_combo.set("Select Category")
        self.cat_combo.grid(row=0, column=0, padx=5, pady=5)
        self.cat_combo.bind("<<ComboboxSelected>>", self._on_category_change)

        # Graph type selector
        self.model_combo = _StyledCombobox(self.center_container,
                                            font=AppConstants.scaled_btn_font(),
                                            width=16,
                                            label="Graph Type",
                                            bg=AppConstants.BG_COLOR)
        self.model_combo.grid(row=0, column=1, padx=(8, 5), pady=5)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        # Save / Copy
        self.save_btn = _StyledButton(self.center_container, text="Save",
                                       font=AppConstants.scaled_btn_font(),
                                       width=52, height=BTN_H,
                                       command=self.save_image)
        self.save_btn.grid(row=0, column=2, padx=(12, 1), pady=5)
        self.save_btn.grid_remove()

        self.copy_btn = _StyledButton(self.center_container, text="Copy",
                                       font=AppConstants.scaled_btn_font(),
                                       width=52, height=BTN_H,
                                       command=self.copy_to_clipboard)
        self.copy_btn.grid(row=0, column=3, padx=1, pady=5)
        self.copy_btn.grid_remove()

        self.batch_btn = _StyledButton(self.center_container, text="Batch Export",
                                        font=AppConstants.scaled_btn_font(),
                                        width=90, height=BTN_H,
                                        command=self.batch_export)
        self.batch_btn.grid(row=0, column=4, padx=(1, 5), pady=5)
        self.batch_btn.grid_remove()

    def _create_controls_row(self) -> None:
        controls = tk.Frame(self.root, bg=AppConstants.BG_COLOR,
                            height=AppConstants.scaled_controls_height())
        controls.grid(row=1, column=0, sticky="ew")
        controls.grid_propagate(False)
        self.controls_row = controls

        self.controls_center = tk.Frame(controls, bg=AppConstants.BG_COLOR)
        self.controls_center.place(relx=0.5, rely=0.0, anchor="n")

        # Col 0: Input panel (coords for scatter; info for line graphs)
        self.col_inputs = tk.Frame(self.controls_center, bg=AppConstants.BG_COLOR)
        self.col_inputs.grid(row=0, column=0, sticky="n", padx=8)
        self.col_inputs.grid_remove()

        # Col 1: Options panel
        self.col_options = tk.Frame(self.controls_center, bg=AppConstants.BG_COLOR)
        self.col_options.grid(row=0, column=1, sticky="n", padx=8)
        self.col_options.grid_remove()

        # Col 2: Color + weight panel
        self.col_style = tk.Frame(self.controls_center, bg=AppConstants.BG_COLOR)
        self.col_style.grid(row=0, column=2, sticky="n", padx=8)
        self.col_style.grid_remove()

        self._build_input_panel()
        self._build_options_panel()
        self._build_style_panel()

        # Random-mode controls: three buttons, replaces all other controls
        self.random_controls = tk.Frame(self.controls_center, bg=AppConstants.BG_COLOR)
        self.random_controls.grid(row=0, column=0, columnspan=3, sticky="n", pady=8)
        self.random_controls.grid_remove()

        self.random_fire_btn = _StyledButton(
            self.random_controls, text="⟳ Random",
            font=AppConstants.scaled_btn_font(),
            width=120,
            command=self._fire_random)
        self.random_fire_btn.grid(row=0, column=0, padx=6)

        self.random_graph_btn = _StyledButton(
            self.random_controls, text="⟳ Graph",
            font=AppConstants.scaled_btn_font(),
            width=100,
            command=lambda: self._fire_random(category="Graphs"))
        self.random_graph_btn.grid(row=0, column=1, padx=6)

        self.random_mapping_btn = _StyledButton(
            self.random_controls, text="⟳ Mapping",
            font=AppConstants.scaled_btn_font(),
            width=100,
            command=lambda: self._fire_random(category="Mappings"))
        self.random_mapping_btn.grid(row=0, column=2, padx=6)

    def _build_input_panel(self) -> None:
        """Coordinate entry for scatter/discrete; param display for line graphs."""
        frame = self.col_inputs
        bg = AppConstants.BG_COLOR

        tk.Label(frame, text="Points", bg=bg,
                 font=AppConstants.scaled_header_font()).grid(
                     row=0, column=0, columnspan=2, pady=(0, 2))

        # Coordinate text entry
        self.coord_entry = _StyledEntry(frame, width=180, height=BTN_H,
                                         font=AppConstants.scaled_btn_font(),
                                         justify="left", bg=bg)
        self.coord_entry.grid(row=1, column=0, columnspan=2, pady=2)
        self.coord_entry.bind('<Return>', lambda e: self._on_coord_change())
        self.coord_entry.bind('<KeyRelease>', lambda e: self._on_coord_change())
        _Tooltip(self.coord_entry, "Enter points as: (1,2), (-3,4), (0,-1)")

        # Randomize points button
        self.rand_pts_btn = _StyledButton(
            frame, text="⟳ Randomize Points",
            font=AppConstants.scaled_btn_font(),
            width=140,
            command=self._randomize_points)
        self.rand_pts_btn.grid(row=2, column=0, columnspan=2, pady=2)

        # Error label
        self.coord_error_lbl = tk.Label(frame, text="", bg=bg,
                                         fg="#cc0000",
                                         font=AppConstants.scaled_btn_font(),
                                         wraplength=180)
        self.coord_error_lbl.grid(row=3, column=0, columnspan=2)

        # Line graph param display (shown for line graphs, hidden for set models)
        self.param_frame = tk.Frame(frame, bg=bg)
        self.param_frame.grid(row=0, column=0, columnspan=2)
        self.param_frame.grid_remove()

        tk.Label(self.param_frame, text="Parameters", bg=bg,
                 font=AppConstants.scaled_header_font()).grid(
                     row=0, column=0, columnspan=2, pady=(0, 2))

        self.param_lbl = tk.Label(self.param_frame, text="", bg=bg,
                                   font=AppConstants.scaled_btn_font(),
                                   fg="#555555", wraplength=180,
                                   justify="left")
        self.param_lbl.grid(row=1, column=0, columnspan=2)

        self.rerandom_btn = _StyledButton(
            self.param_frame, text="⟳ New Graph",
            font=AppConstants.scaled_btn_font(),
            width=120,
            command=self._rerandomize_current)
        self.rerandom_btn.grid(row=2, column=0, columnspan=2, pady=(4, 0))

    def _build_options_panel(self) -> None:
        frame = self.col_options
        bg = AppConstants.BG_COLOR

        tk.Label(frame, text="Options", bg=bg,
                 font=AppConstants.scaled_header_font()).grid(
                     row=0, column=0, columnspan=2, pady=(0, 2))

        # Show grid toggle
        self.grid_var = tk.BooleanVar(value=True)
        self._grid_chk = _StyledCheckbox(frame, text="Show Grid",
                                          variable=self.grid_var,
                                          font=AppConstants.scaled_btn_font(),
                                          bg=bg,
                                          command=self._on_grid_toggle)
        self._grid_chk.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

        # VLT toggle
        self.vlt_var = tk.BooleanVar(value=False)
        self._vlt_chk = _StyledCheckbox(frame, text="Show VLT",
                                         variable=self.vlt_var,
                                         font=AppConstants.scaled_btn_font(),
                                         bg=bg,
                                         command=self._on_vlt_toggle)
        self._vlt_chk.grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        _Tooltip(self._vlt_chk, "Overlay Vertical Line Test indicator")

        # X/Y label toggle — only shown for Mapping
        self.xy_label_var = tk.BooleanVar(value=True)
        self._xy_label_chk = _StyledCheckbox(frame, text="Show X / Y",
                                              variable=self.xy_label_var,
                                              font=AppConstants.scaled_btn_font(),
                                              bg=bg,
                                              command=self._on_xy_label_toggle)
        self._xy_label_chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=2)
        self._xy_label_chk.grid_remove()  # hidden until Mapping selected

        # Shape toggle (Oval / Rectangle) — only shown for Mapping
        shape_row = tk.Frame(frame, bg=bg)
        shape_row.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)
        self._shape_oval_btn = _StyledButton(
            shape_row, text="Oval",
            font=AppConstants.scaled_btn_font(),
            width=60, active=True,
            command=lambda: self._set_mapping_shape("oval"))
        self._shape_oval_btn.pack(side=tk.LEFT, padx=(0, 2))
        self._shape_rect_btn = _StyledButton(
            shape_row, text="Rect",
            font=AppConstants.scaled_btn_font(),
            width=60, active=False,
            command=lambda: self._set_mapping_shape("rectangle"))
        self._shape_rect_btn.pack(side=tk.LEFT)
        self._shape_row = shape_row
        self._shape_row.grid_remove()  # hidden until Mapping selected

        # Dot style (open / closed)
        tk.Label(frame, text="Endpoints:", bg=bg,
                 font=AppConstants.scaled_btn_font()).grid(
                     row=5, column=0, sticky="w", pady=(6, 0))

        dot_row = tk.Frame(frame, bg=bg)
        dot_row.grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

        self._dot_closed_btn = _StyledButton(
            dot_row, text="●  Closed",
            font=AppConstants.scaled_btn_font(),
            width=70,
            active=True,
            command=lambda: self._set_dot_style("closed"))
        self._dot_closed_btn.pack(side=tk.LEFT, padx=(0, 2))

        self._dot_open_btn = _StyledButton(
            dot_row, text="○  Open",
            font=AppConstants.scaled_btn_font(),
            width=70,
            active=False,
            command=lambda: self._set_dot_style("open"))
        self._dot_open_btn.pack(side=tk.LEFT)

    def _build_style_panel(self) -> None:
        frame = self.col_style
        bg = AppConstants.BG_COLOR

        tk.Label(frame, text="Style", bg=bg,
                 font=AppConstants.scaled_header_font()).grid(
                     row=0, column=0, columnspan=7, pady=(0, 2))

        # ── Grid style toggle: Print | Color ──────────────────────────────────
        toggle_row = tk.Frame(frame, bg=bg)
        toggle_row.grid(row=1, column=0, columnspan=7, pady=(0, 4))

        self._print_btn = _StyledButton(
            toggle_row, text="Print",
            font=AppConstants.scaled_btn_font(),
            width=52, height=BTN_H,
            active=True,
            command=lambda: self._set_grid_style("print"))
        self._print_btn.pack(side=tk.LEFT, padx=(0, 2))

        self._color_mode_btn = _StyledButton(
            toggle_row, text="Color",
            font=AppConstants.scaled_btn_font(),
            width=52, height=BTN_H,
            active=False,
            command=lambda: self._set_grid_style("color"))
        self._color_mode_btn.pack(side=tk.LEFT)

        # ── Color swatches (hidden in print mode) ─────────────────────────────
        self._color_row = tk.Frame(frame, bg=bg)
        self._color_row.grid(row=2, column=0, columnspan=7, pady=(0, 2))

        self._color_btns: list = []
        for i, (shade, display) in enumerate(
                zip(AppConstants.GRAPH_COLORS, self._SWATCH_DISPLAY)):
            swatch = tk.Canvas(self._color_row, width=20, height=20,
                                bg=bg, highlightthickness=0, cursor="hand2")
            swatch.pack(side=tk.LEFT, padx=1)
            swatch.create_oval(2, 2, 18, 18, fill=display,
                                outline="#888888", width=1, tags="dot")
            swatch.bind("<Button-1>",
                        lambda e, c=shade, w=swatch: self._set_color(c, w))
            self._color_btns.append((swatch, shade))

        self._selected_swatch = self._color_btns[0][0]
        self._highlight_swatch(self._selected_swatch)

        # Hide swatches by default (print mode)
        self._color_row.grid_remove()

        # ── Line weight slider ────────────────────────────────────────────────
        weight_row = tk.Frame(frame, bg=bg)
        weight_row.grid(row=3, column=0, columnspan=7, pady=(2, 0), sticky="w")

        tk.Label(weight_row, text="Weight:", bg=bg,
                 font=AppConstants.scaled_btn_font()).pack(side=tk.LEFT, padx=(0, 4))

        self.weight_var = tk.DoubleVar(value=AppConstants.DEFAULT_LINE_WIDTH * 2)
        self._weight_slider = _StyledSlider(
            weight_row, from_=0.5, to=5.0,
            variable=self.weight_var,
            width=110,
            bg=bg,
            command=self._on_weight_change)
        self._weight_slider.pack(side=tk.LEFT)

    def _create_canvas_area(self) -> None:
        canvas_w = self._canvas_target_w
        canvas_h = self._canvas_target_h
        self.col_canvas = tk.Frame(self.root, bg=AppConstants.CANVAS_BG_COLOR,
                                    width=canvas_w, height=canvas_h)
        self.col_canvas.grid(row=2, column=0)
        self.col_canvas.grid_propagate(False)

    def _create_shortcut_bar(self) -> None:
        shortcut_bar = tk.Frame(self.root, bg=AppConstants.BG_COLOR,
                                 height=AppConstants.scaled_shortcut_bar_height())
        shortcut_bar.grid(row=3, column=0, sticky="ew")
        shortcut_bar.grid_propagate(False)
        self.shortcut_bar = shortcut_bar
        self.shortcut_label = tk.Label(
            shortcut_bar, text="", bg=AppConstants.BG_COLOR, fg="#555555",
            font=AppConstants.scaled_btn_font(), pady=1)
        self.shortcut_label.place(relx=0.5, rely=0.5, anchor="center")

    # ── Canvas setup ──────────────────────────────────────────────────────────

    def _setup_canvas_and_controllers(self) -> None:
        canvas_w = self._canvas_target_w
        canvas_h = self._canvas_target_h
        _dpi = 100

        self.fig = Figure(figsize=(canvas_w / _dpi, canvas_h / _dpi), dpi=_dpi)
        self.fig.patch.set_facecolor(AppConstants.CANVAS_BG_COLOR)

        _mx = AppConstants.CANVAS_PAPER_MARGIN
        _axes_w = 1 - 2 * _mx
        _ratio = AppConstants.PAPER_ASPECT_RATIO
        _axes_h = (canvas_w * _axes_w) / (canvas_h * _ratio)
        _axes_h = min(_axes_h, 1.0 - 2 * _mx)
        _bottom = (1.0 - _axes_h) / 2.0
        self.ax = self.fig.add_axes([_mx, _bottom, _axes_w, _axes_h])
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.col_canvas)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.get_tk_widget().configure(takefocus=False)

        # Measure layout
        self._show_topbar_category_only()
        self.controls_row.grid_remove()
        self.root.update_idletasks()
        menu_w  = self.center_container.winfo_reqwidth() + 20
        final_w = max(menu_w, canvas_w)

        self.show_welcome()

        canvas_h = int(final_w * 3 / 4)
        final_h  = (AppConstants.scaled_top_bar_height()
                    + AppConstants.scaled_controls_height()
                    + canvas_h
                    + AppConstants.scaled_shortcut_bar_height())

        self.col_canvas.configure(width=final_w, height=canvas_h)
        self.fig.set_size_inches(final_w / _dpi, canvas_h / _dpi, forward=False)
        _axes_h = (final_w * _axes_w) / (canvas_h * _ratio)
        _axes_h = min(_axes_h, 1.0 - 2 * _mx)
        _bottom = (1.0 - _axes_h) / 2.0
        self.ax.set_position([_mx, _bottom, _axes_w, _axes_h])
        self._canvas_target_w = final_w
        self._canvas_target_h = canvas_h
        self._native_width  = final_w
        self._native_height = final_h

        self.root.geometry(f"{final_w}x{final_h}")
        self.root.resizable(True, True)
        self.root.minsize(round(final_w * 0.5), round(final_h * 0.5))
        self.root.maxsize(round(final_w * 3.0), round(final_h * 3.0))

        self._bind_shortcuts()
        self.root.bind("<Configure>", self._on_window_resize_event)

    # ── Global fonts ──────────────────────────────────────────────────────────

    def _apply_global_fonts(self) -> None:
        fs = AppConstants.scaled_ui_font_size()
        _style = ttk.Style()
        _style.configure(".", font=("Arial", fs))
        self.root.option_add("*Font", f"Arial {fs}")

    # ── Window resize ─────────────────────────────────────────────────────────

    def _on_window_resize_event(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        new_w = event.width
        if not hasattr(self, "_native_width") or self._native_width == 0:
            return
        if hasattr(self, "_last_resize_w") and abs(new_w - self._last_resize_w) < 2:
            return
        self._last_resize_w = new_w
        if hasattr(self, "_resize_after_id") and self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(
            120, lambda: self._apply_ui_scale(new_w))

    def _apply_ui_scale(self, new_width: int) -> None:
        self._resize_after_id = None
        scale = new_width / self._native_width
        screen_h = self.root.winfo_screenheight()
        native_h = self._native_height
        max_scale = (screen_h * 0.95) / native_h if native_h > 0 else 3.0
        scale = max(0.5, min(3.0, scale, max_scale))
        scale = round(scale, 2)
        if abs(scale - AppConstants.UI_SCALE) < 0.01:
            return
        AppConstants.UI_SCALE = scale
        self._apply_global_fonts()

        if self.top_bar:
            self.top_bar.configure(height=AppConstants.scaled_top_bar_height())
        if self.controls_row:
            self.controls_row.configure(height=AppConstants.scaled_controls_height())
        if hasattr(self, "shortcut_bar") and self.shortcut_bar:
            self.shortcut_bar.configure(
                height=AppConstants.scaled_shortcut_bar_height())

        _dpi = 100
        _mx = AppConstants.CANVAS_PAPER_MARGIN
        _axes_w = 1 - 2 * _mx
        _ratio = AppConstants.PAPER_ASPECT_RATIO
        canvas_w = new_width
        canvas_h = int(canvas_w * 3 / 4)
        if canvas_w <= 0 or canvas_h <= 0:
            return
        self.col_canvas.configure(width=canvas_w, height=canvas_h)
        self.fig.set_size_inches(canvas_w / _dpi, canvas_h / _dpi, forward=False)
        _axes_h = (canvas_w * _axes_w) / (canvas_h * _ratio)
        _axes_h = min(_axes_h, 1.0 - 2 * _mx)
        _bottom = (1.0 - _axes_h) / 2.0
        self.ax.set_position([_mx, _bottom, _axes_w, _axes_h])
        self._schedule_redraw()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _bind_shortcuts(self) -> None:
        mod = "Command" if platform.system() == "Darwin" else "Control"
        for key, func in [
            ('s', self.save_image),
            ('c', self.copy_to_clipboard),
        ]:
            self.root.bind_all(f'<{mod}-{key}>', lambda e, f=func: f() or "break")
            self.root.bind_all(f'<{mod}-{key.upper()}>', lambda e, f=func: f() or "break")

    # ── Top-bar visibility ────────────────────────────────────────────────────

    def _show_topbar_category_only(self) -> None:
        self.cat_combo.grid()
        self.model_combo.grid_remove()
        if self.save_btn: self.save_btn.grid_remove()
        if self.copy_btn: self.copy_btn.grid_remove()
        if self.batch_btn: self.batch_btn.grid_remove()

    def _show_topbar_category_and_model(self) -> None:
        self.cat_combo.grid()
        self.model_combo.grid(row=0, column=1, padx=(8, 5), pady=5)
        if self.save_btn: self.save_btn.grid_remove()
        if self.copy_btn: self.copy_btn.grid_remove()
        if self.batch_btn: self.batch_btn.grid_remove()

    def _show_topbar_all(self) -> None:
        self.cat_combo.grid()
        self.model_combo.grid(row=0, column=1, padx=(8, 5), pady=5)
        self.save_btn.grid(row=0, column=2, padx=(12, 1), pady=5)
        self.copy_btn.grid(row=0, column=3, padx=1, pady=5)
        self.batch_btn.grid(row=0, column=4, padx=(1, 5), pady=5)

    def _show_topbar_random(self) -> None:
        """Random category: show category + save/copy/batch, hide model picker."""
        self.cat_combo.grid()
        self.model_combo.grid_remove()
        self.save_btn.grid(row=0, column=2, padx=(12, 1), pady=5)
        self.copy_btn.grid(row=0, column=3, padx=1, pady=5)
        self.batch_btn.grid(row=0, column=4, padx=(1, 5), pady=5)

    # ── Welcome screen ────────────────────────────────────────────────────────

    def show_welcome(self) -> None:
        self._show_topbar_category_only()
        for col in (self.col_inputs, self.col_options, self.col_style):
            if col:
                col.grid_remove()
        if self.controls_row:
            self.controls_row.grid_remove()
        if hasattr(self, "shortcut_bar") and self.shortcut_bar:
            self.shortcut_bar.grid_remove()

        self.root.rowconfigure(2, weight=1)
        self.col_canvas.grid(row=2, column=0, sticky="nsew")
        if hasattr(self, "shortcut_label"):
            self.shortcut_label.config(text="")

        self.ax.clear()
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-8, 8)
        self._draw_welcome()

    def _draw_welcome(self) -> None:
        trans = self.ax.transAxes
        lw = 1.8
        ec = "#333333"

        # Mini coordinate grid decoration
        cx, cy = 0.5, 0.32
        s = 0.08

        # Mini axes
        self.ax.plot([cx - s * 1.6, cx + s * 1.6], [cy, cy],
                     color=ec, linewidth=lw * 0.8,
                     transform=trans, clip_on=False)
        self.ax.plot([cx, cx], [cy - s * 1.4, cy + s * 1.4],
                     color=ec, linewidth=lw * 0.8,
                     transform=trans, clip_on=False)

        # Mini sine wave
        t = np.linspace(cx - s * 1.5, cx + s * 1.5, 100)
        sine_x = t
        sine_y = cy + s * 0.9 * np.sin((t - cx) / s * math.pi * 1.5)
        self.ax.plot(sine_x, sine_y, color="#2563EB",
                     linewidth=lw * 1.2, transform=trans, clip_on=False)

        # Title
        self.ax.text(0.5, 0.65, "Function Forge",
                     ha="center", va="center", fontsize=26, fontweight="bold",
                     color="#333333", fontfamily="sans-serif", transform=trans)
        self.ax.text(0.5, 0.57, "Select a category to begin",
                     ha="center", va="center", fontsize=11,
                     color="#aaaaaa", fontfamily="sans-serif", transform=trans)

        self.canvas.draw()

    def _draw_coming_soon(self, category: str) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-8, 8)
        trans = self.ax.transAxes
        self.ax.text(0.5, 0.55, category,
                     ha="center", va="center", fontsize=22, fontweight="bold",
                     color="#333333", fontfamily="sans-serif", transform=trans)
        self.ax.text(0.5, 0.45, "Coming soon",
                     ha="center", va="center", fontsize=11,
                     color="#aaaaaa", fontfamily="sans-serif", transform=trans)
        self.canvas.draw()

    def _draw_category_prompt(self, category: str) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-8, 8)
        trans = self.ax.transAxes
        self.ax.text(0.5, 0.55, category,
                     ha="center", va="center", fontsize=22, fontweight="bold",
                     color="#333333", fontfamily="sans-serif", transform=trans)
        self.ax.text(0.5, 0.45, "Select a graph type to begin",
                     ha="center", va="center", fontsize=11,
                     color="#aaaaaa", fontfamily="sans-serif", transform=trans)
        self.canvas.draw()

    # ── Category / Model selection ────────────────────────────────────────────

    def _fire_random(self, category: str | None = None) -> None:
        """Pick and draw a completely random type, optionally filtered by category."""
        import random as _rand
        all_types = [
            (c, m)
            for c, models in self.model_data.items()
            if c != "Random" and (category is None or c == category)
            for m in models
        ]
        chosen_cat, chosen_model = _rand.choice(all_types)
        self._came_from_random = True

        # Update model combo silently (keep cat combo showing "Random")
        self.model_combo["values"] = self.model_data.get(chosen_cat, [])
        self.model_combo.set(chosen_model)

        # Generate params just like _on_model_change does
        self._current_params = get_random_params(chosen_model)
        if chosen_model == "Mapping":
            self._current_params["show_labels"] = self._show_xy_labels
            self._mapping_shape = self._current_params.get("shape", "oval")

        # Layout: controls row with only the Random button
        self._show_topbar_random()
        self.root.rowconfigure(2, weight=0)
        self.controls_row.grid(row=1, column=0, sticky="ew")
        self.col_canvas.grid(row=2, column=0)
        self.root.rowconfigure(1, weight=0,
                                minsize=AppConstants.scaled_controls_height())
        self._apply_ui_scale(self.root.winfo_width())
        self.shortcut_bar.grid(row=3, column=0, sticky="ew")
        self.shortcut_label.config(text="Save [Ctrl+S]     •     Copy [Ctrl+C]")
        self.col_inputs.grid_remove()
        self.col_options.grid_remove()
        self.col_style.grid_remove()
        self.random_controls.grid()

        self._schedule_redraw()

    def _on_category_change(self, event=None) -> None:
        if getattr(self, '_category_changing', False):
            return
        cat = self.cat_combo.get()

        # ── Random category: delegate entirely to _fire_random ────────────────
        if cat == "Random":
            self._category_changing = True
            self._fire_random()
            self.root.after(50, lambda: setattr(self, '_category_changing', False))
            return

        # Normal category — clear random mode
        self._came_from_random = False

        models = self.model_data.get(cat, [])
        self.model_combo["values"] = models
        self.model_combo.set("")
        self._show_topbar_category_and_model()

        for col in (self.col_inputs, self.col_options, self.col_style):
            if col:
                col.grid_remove()
        if self.controls_row:
            self.controls_row.grid_remove()
        if hasattr(self, "shortcut_bar") and self.shortcut_bar:
            self.shortcut_bar.grid_remove()
            self.shortcut_label.config(text="")

        self.root.rowconfigure(2, weight=1)
        self.col_canvas.grid(row=2, column=0, sticky="nsew")

        self.fig.clf()
        self.fig.patch.set_facecolor(AppConstants.CANVAS_BG_COLOR)
        _mx = AppConstants.CANVAS_PAPER_MARGIN
        self.ax = self.fig.add_axes([_mx, 0.1, 1 - 2 * _mx, 0.82])
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)

        if not models:
            self._draw_coming_soon(cat)
        elif len(models) == 1:
            self.model_combo.set(models[0])
            self._on_model_change()
        else:
            self._draw_category_prompt(cat)

    def _on_model_change(self, event=None) -> None:
        model = self.model_combo.get()
        if not model:
            return

        # ── "Random" entry in Graphs list: no longer in Graphs, kept for safety
        if model in ("Random", "Random Graph"):
            import random as _rand
            graphs = list(self.model_data.get("Graphs", []))
            model = _rand.choice(graphs)
            self.model_combo.set(model)
            self._came_from_random = True
        # Note: _came_from_random is only cleared by _on_category_change
        # when the user explicitly picks a non-Random category.

        # ── Layout: controls row always visible; swap random vs normal panels ──
        self._show_topbar_all() if not self._came_from_random else self._show_topbar_random()
        self.root.rowconfigure(2, weight=0)
        self.controls_row.grid(row=1, column=0, sticky="ew")
        self.col_canvas.grid(row=2, column=0)
        self.root.rowconfigure(1, weight=0,
                                minsize=AppConstants.scaled_controls_height())
        self._apply_ui_scale(self.root.winfo_width())
        self.shortcut_bar.grid(row=3, column=0, sticky="ew")
        self.shortcut_label.config(text="Save [Ctrl+S]     •     Copy [Ctrl+C]")

        if self._came_from_random:
            # Random mode: hide all normal panels, show just the Random button
            self.col_inputs.grid_remove()
            self.col_options.grid_remove()
            self.col_style.grid_remove()
            self.random_controls.grid()
            return

        # Normal mode: hide random controls, show normal panels
        self.random_controls.grid_remove()

        # Show/hide input panel based on graph type
        is_set_model  = model in ("Scatter Plot",)
        is_mapping    = model == "Mapping"
        if is_set_model:
            self._show_coord_input()
        else:
            self._show_param_display()

        self.col_options.grid()
        self.col_style.grid()

        # Show/hide controls that are only relevant for certain model types
        if is_mapping:
            self._grid_chk.grid_remove()
            self._vlt_chk.grid_remove()
            self._dot_closed_btn.master.grid_remove()
            self._xy_label_chk.grid()
            self._shape_row.grid()
            self.col_style.grid_remove()   # no color/weight for mappings
            self.rerandom_btn.configure(text="⟳ New Mapping")
        else:
            self._grid_chk.grid()
            self._vlt_chk.grid()
            self._dot_closed_btn.master.grid()
            self._xy_label_chk.grid_remove()
            self._shape_row.grid_remove()
            self.col_style.grid()
            self.rerandom_btn.configure(text="⟳ New Graph")

        # Generate initial random params
        self._current_params = get_random_params(model)
        if is_mapping:
            self._current_params["show_labels"] = self._show_xy_labels
            self._mapping_shape = self._current_params.get("shape", "oval")
            self._shape_oval_btn.set_active(self._mapping_shape == "oval")
            self._shape_rect_btn.set_active(self._mapping_shape == "rectangle")
        if is_set_model:
            # Populate entry with the random points
            pts = self._current_params.get("points", [])
            self.coord_entry.delete(0, tk.END)
            self.coord_entry.insert(0, CoordinateValidator.format_points(pts))
            self.coord_error_lbl.config(text="")
        else:
            self._update_param_label()

        self._schedule_redraw()

    def _show_coord_input(self) -> None:
        """Show the coordinate entry panel, hide param display."""
        self.param_frame.grid_remove()
        self.coord_entry.grid()
        self.rand_pts_btn.grid()
        self.coord_error_lbl.grid()
        self.col_inputs.grid()

    def _show_param_display(self) -> None:
        """Show param display panel, hide coordinate entry."""
        self.coord_entry.grid_remove()
        self.rand_pts_btn.grid_remove()
        self.coord_error_lbl.grid_remove()
        self.param_frame.grid()
        self.col_inputs.grid()

    def _update_param_label(self) -> None:
        """Format current params into a readable description."""
        model = self.model_combo.get()
        p = self._current_params
        lines = []
        if model == "Linear":
            m = p.get("slope", 1)
            b = p.get("intercept", 0)
            lines.append(f"y = {m}x + {b}" if b != 0 else f"y = {m}x")
        elif model == "Smooth Curve":
            lines.append(f"Type: {p.get('curve_type', '').title()}")
            lines.append(f"Amplitude: {p.get('amplitude', 1):.1f}")
            lines.append(f"Frequency: {p.get('frequency', 1):.1f}")
        elif model == "Piecewise":
            segs = p.get("segments", [])
            lines.append(f"{len(segs)} segments")
        elif model == "Step Function":
            steps = p.get("steps", [])
            lines.append(f"{len(steps)} steps")
        elif model == "Parametric":
            lines.append(f"Curve: {p.get('curve', '').title()}")
        elif model == "Reciprocal":
            k, h, v = p.get('k', 1), p.get('h', 0), p.get('v', 0)
            h_str = f"(x{'-' if h >= 0 else '+'}{abs(h)})" if h != 0 else "x"
            v_str = f" + {v}" if v > 0 else (f" - {abs(v)}" if v < 0 else "")
            lines.append(f"y = {k}/{h_str}{v_str}")
        self.param_lbl.config(text="\n".join(lines))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_coord_change(self) -> None:
        text = self.coord_entry.get()
        pts, err = CoordinateValidator.parse(text)
        if err:
            self.coord_error_lbl.config(text=err)
            return
        self.coord_error_lbl.config(text="")
        self._current_params = {"points": pts}
        self._schedule_redraw()

    def _on_xy_label_toggle(self) -> None:
        self._show_xy_labels = self.xy_label_var.get()
        if "show_labels" in self._current_params:
            self._current_params["show_labels"] = self._show_xy_labels
        self._schedule_redraw()

    def _set_mapping_shape(self, shape: str) -> None:
        self._mapping_shape = shape
        self._shape_oval_btn.set_active(shape == "oval")
        self._shape_rect_btn.set_active(shape == "rectangle")
        if "shape" in self._current_params:
            self._current_params["shape"] = shape
        self._schedule_redraw()

    def _on_grid_toggle(self) -> None:
        self._show_grid = self.grid_var.get()
        self._schedule_redraw()

    def _on_vlt_toggle(self) -> None:
        self._show_vlt = self.vlt_var.get()
        self._schedule_redraw()

    def _on_weight_change(self, val=None) -> None:
        self._line_width = self.weight_var.get()
        self._schedule_redraw()

    def _set_dot_style(self, style: str) -> None:
        self._dot_style = style
        self._dot_closed_btn.set_active(style == "closed")
        self._dot_open_btn.set_active(style == "open")
        self._schedule_redraw()

    def _set_color(self, color: str, swatch_widget) -> None:
        self._graph_color = color
        if self._selected_swatch:
            self._selected_swatch.delete("ring")
        self._selected_swatch = swatch_widget
        self._highlight_swatch(swatch_widget)
        self._schedule_redraw()

    def _highlight_swatch(self, swatch) -> None:
        swatch.delete("ring")
        swatch.create_oval(1, 1, 19, 19, outline="#1a1a1a",
                            width=2, tags="ring", fill="")

    def _set_grid_style(self, style: str) -> None:
        """Switch between print (dark grid, black line) and color modes."""
        self._grid_style = style
        is_print = (style == "print")
        self._print_btn.set_active(is_print)
        self._color_mode_btn.set_active(not is_print)
        if is_print:
            self._graph_color = "#000000"
            self._color_row.grid_remove()
            # Restore thick default weight for print
            self._line_width = AppConstants.DEFAULT_LINE_WIDTH * 2
            self.weight_var.set(self._line_width)
        else:
            # Restore the selected swatch color, show swatches
            for swatch, shade in self._color_btns:
                if swatch is self._selected_swatch:
                    self._graph_color = shade
                    break
            self._color_row.grid()
            # Restore normal weight for color mode
            self._line_width = AppConstants.DEFAULT_LINE_WIDTH
            self.weight_var.set(self._line_width)
        self._schedule_redraw()

    def _randomize_points(self) -> None:
        """Randomize points for scatter/discrete models."""
        model = self.model_combo.get()
        params = get_random_params(model)
        self._current_params = params
        pts = params.get("points", [])
        self.coord_entry.delete(0, tk.END)
        self.coord_entry.insert(0, CoordinateValidator.format_points(pts))
        self.coord_error_lbl.config(text="")
        self._schedule_redraw()

    def _rerandomize_current(self) -> None:
        """Generate new random params for the current graph type."""
        model = self.model_combo.get()
        self._current_params = get_random_params(model)
        if model == "Mapping":
            self._current_params["show_labels"] = self._show_xy_labels
            # Sync shape: use whatever random_params picked, update buttons
            self._mapping_shape = self._current_params.get("shape", "oval")
            self._shape_oval_btn.set_active(self._mapping_shape == "oval")
            self._shape_rect_btn.set_active(self._mapping_shape == "rectangle")
        self._update_param_label()
        self._schedule_redraw()

    def _pick_new_random_graph(self) -> None:
        """Pick a completely new random type from everything in the app."""
        self._fire_random()

    def _generate_random(self) -> None:
        """Re-roll in Random mode, or randomize within category otherwise."""
        if self._came_from_random:
            self._fire_random()
        else:
            import random
            cat = self.cat_combo.get()
            if cat not in self.model_data:
                cat = random.choice(list(self.model_data.keys()))
            models = [m for m in self.model_data.get(cat, []) if m != "Random"]
            if not models:
                return
            model = random.choice(models)
            self.model_combo.set(model)
            self._on_model_change()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _schedule_redraw(self, event=None) -> None:
        if self._redraw_after_id:
            self.root.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.root.after(
            AppConstants.DEBOUNCE_DELAY, self._generate_plot)

    def _generate_plot(self) -> None:
        self._redraw_after_id = None
        model = self.model_combo.get()
        if not model:
            return

        drawer = GraphRegistry.get_drawer(model)
        if not drawer:
            logger.warning(f"No drawer registered for: {model}")
            return

        ctx = DrawingContext(
            ax=self.ax,
            line_width=self._line_width,
            graph_color=self._graph_color,
            show_grid=self._show_grid,
            dot_style=self._dot_style,
            show_vlt=self._show_vlt,
            grid_style=self._grid_style,
            params=self._current_params,
        )

        try:
            drawer.draw(ctx)
        except Exception as exc:
            logger.error(f"Draw error: {exc}", exc_info=True)
            self._draw_error(str(exc))
            return

        self.canvas.draw()

    def _draw_error(self, message: str) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#ffffff")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_xlim(-5, 5)
        self.ax.set_ylim(-5, 5)
        self.ax.text(0, 0, message, ha="center", va="center",
                     fontsize=10, color="#cc0000", fontfamily="sans-serif",
                     wrap=True)
        self.canvas.draw()

    # ── Color swatch helpers ──────────────────────────────────────────────────

    # ── Save / Copy / Batch Export ────────────────────────────────────────────

    def save_image(self) -> None:
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("SVG files", "*.svg"),
                       ("All files", "*.*")],
            title="Save Image")
        if not filepath:
            return
        try:
            is_svg = filepath.lower().endswith(".svg")
            kwargs = dict(bbox_inches="tight",
                          facecolor=AppConstants.CANVAS_BG_COLOR)
            if not is_svg:
                kwargs["dpi"] = 200
            self.fig.savefig(filepath, **kwargs)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def copy_to_clipboard(self) -> None:
        try:
            buf = BytesIO()
            self.fig.savefig(buf, format="png", dpi=200, bbox_inches="tight",
                             facecolor=AppConstants.CANVAS_BG_COLOR)
            buf.seek(0)
            if platform.system() == "Darwin":
                process = subprocess.Popen(
                    ["osascript", "-e",
                     "set the clipboard to (read (POSIX file \"/dev/stdin\") "
                     "as «class PNGf»)"],
                    stdin=subprocess.PIPE)
                process.communicate(buf.read())
            elif platform.system() == "Windows":
                from PIL import Image
                import win32clipboard
                img = Image.open(buf)
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                output = BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
            else:
                process = subprocess.Popen(
                    ["xclip", "-selection", "clipboard", "-t", "image/png"],
                    stdin=subprocess.PIPE)
                process.communicate(buf.read())
        except Exception as exc:
            messagebox.showerror("Copy Error", str(exc))

    def batch_export(self) -> None:
        """Export N random images based on the current mode."""
        import os
        import random as _rand

        count = _show_batch_count_dialog(self.root)
        if not count:
            return

        folder = filedialog.askdirectory(title="Choose a folder for exported images")
        if not folder:
            return

        is_random = self._came_from_random
        current_model = self.model_combo.get()

        if is_random:
            pool = [
                m
                for cat, models in self.model_data.items()
                if cat != "Random"
                for m in models
            ]
        else:
            pool = [current_model]

        prog = _BatchProgressDialog(self.root, count)
        self.root.update()

        saved = 0
        for i in range(count):
            if prog.cancelled:
                break

            model_name = _rand.choice(pool)
            params = get_random_params(model_name)
            if model_name == "Mapping":
                params["show_labels"] = self._show_xy_labels

            safe = model_name.lower().replace(" ", "_")
            if is_random:
                filename = f"random_{i + 1:03d}_{safe}.png"
            else:
                filename = f"{safe}_{i + 1:03d}.png"
            filepath = os.path.join(folder, filename)

            try:
                self._render_graph_to_file(model_name, params, filepath)
                saved += 1
            except Exception as exc:
                logger.error(f"Batch export error [{i + 1}]: {exc}", exc_info=True)

            prog.update(i + 1, model_name)
            self.root.update()

        prog.destroy()

        if saved > 0:
            messagebox.showinfo(
                "Batch Export Complete",
                f"Exported {saved} image{'s' if saved != 1 else ''} to:\n{folder}")
        elif not prog.cancelled:
            messagebox.showerror("Batch Export Failed",
                                 "No images could be exported.")

    def _render_graph_to_file(self, model_name: str, params: dict,
                               filepath: str) -> None:
        """Render a single graph to a PNG file using an off-screen Figure."""
        fig = Figure(figsize=(7, 5.25), dpi=200)
        fig.patch.set_facecolor(AppConstants.CANVAS_BG_COLOR)

        _mx = AppConstants.CANVAS_PAPER_MARGIN
        ax = fig.add_axes([_mx, 0.1, 1 - 2 * _mx, 0.82])
        ax.set_facecolor("#ffffff")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("black")
            spine.set_linewidth(1.0)

        ctx = DrawingContext(
            ax=ax,
            line_width=self._line_width,
            graph_color=self._graph_color,
            show_grid=self._show_grid,
            dot_style=self._dot_style,
            show_vlt=False,
            grid_style=self._grid_style,
            params=params,
        )

        drawer = GraphRegistry.get_drawer(model_name)
        if drawer:
            drawer.draw(ctx)

        fig.savefig(filepath, format="png", dpi=200, bbox_inches="tight",
                    facecolor=AppConstants.CANVAS_BG_COLOR)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    root = tk.Tk()
    app = FunctionApp(root)
    root.mainloop()