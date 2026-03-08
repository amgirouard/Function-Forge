"""models.py — Data types, constants, and graph model configs for Function Forge."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# App-wide constants
# ═══════════════════════════════════════════════════════════════════════════════

class AppConstants:
    WINDOW_TITLE        = "Function Forge"
    BG_COLOR            = "#e8e8e8"
    CANVAS_BG_COLOR     = "#e0e0e0"
    DEFAULT_LINE_WIDTH  = 2.0
    DEFAULT_FONT_SIZE   = 11
    DEFAULT_FONT_FAMILY = "sans-serif"
    DEBOUNCE_DELAY      = 80          # ms

    # Layout
    TOP_BAR_HEIGHT      = 40
    CONTROLS_HEIGHT     = 110
    SHORTCUT_BAR_HEIGHT = 24
    CANVAS_PAPER_MARGIN = 0.06
    PAPER_ASPECT_RATIO  = 4 / 3

    # Entry width
    ENTRY_WIDTH         = 60

    # Graph axes range
    AXIS_MIN = -5
    AXIS_MAX =  5

    # Graph colors (line colors)
    GRAPH_COLORS = [
        "#2563EB",  # Blue
        "#DC2626",  # Red
        "#16A34A",  # Green
        "#D97706",  # Orange
        "#7C3AED",  # Purple
        "#0891B2",  # Teal
    ]

    # UI scaling
    UI_SCALE: float = 1.0

    @classmethod
    def _s(cls, v: int | float) -> int:
        return max(1, round(v * cls.UI_SCALE))

    @classmethod
    def scaled_top_bar_height(cls) -> int:
        return cls._s(cls.TOP_BAR_HEIGHT)

    @classmethod
    def scaled_controls_height(cls) -> int:
        return cls._s(cls.CONTROLS_HEIGHT)

    @classmethod
    def scaled_shortcut_bar_height(cls) -> int:
        return cls._s(cls.SHORTCUT_BAR_HEIGHT)

    @classmethod
    def scaled_btn_font(cls) -> tuple[str, int]:
        return ("Arial", cls._s(10))

    @classmethod
    def scaled_header_font(cls) -> tuple[str, int, str]:
        return ("Arial", cls._s(10), "bold")

    @classmethod
    def scaled_ui_font_size(cls) -> int:
        return cls._s(10)


# ═══════════════════════════════════════════════════════════════════════════════
# Drawing context — passed to every drawer
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DrawingContext:
    ax: Any                              # matplotlib Axes
    line_width: float = 2.0
    graph_color: str  = "#2563EB"
    show_grid: bool   = True
    dot_style: str    = "closed"         # "closed" | "open"
    show_vlt: bool    = False
    grid_style: str   = "print"        # "print" | "color"
    # Graph-type-specific params (set by each drawer)
    params: dict      = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Graph model config
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GraphConfig:
    name:           str
    category:       str
    is_function:    bool | None = None   # None = can be either (e.g. scatter)
    supports_random: bool = True
    description:    str = ""


class GraphConfigProvider:
    _configs: dict[str, GraphConfig] = {}

    @classmethod
    def register(cls, config: GraphConfig) -> None:
        cls._configs[config.name] = config

    @classmethod
    def get(cls, name: str) -> GraphConfig | None:
        return cls._configs.get(name)


def _build_graph_configs() -> None:
    configs = [
        # Graphs
        GraphConfig("Linear",        "Graphs",   is_function=True),
        GraphConfig("Smooth Curve",  "Graphs",   is_function=True),
        GraphConfig("Piecewise",     "Graphs",   is_function=True),
        GraphConfig("Step Function", "Graphs",   is_function=True),
        GraphConfig("Parametric",    "Graphs",   is_function=False,
                    description="Closed curve — relation, not a function"),
        GraphConfig("Scatter Plot",  "Graphs",   is_function=None),
        GraphConfig("Reciprocal",    "Graphs",   is_function=False,
                    description="y = k/(x-h)+v — hyperbola with asymptotes"),
        # Mappings
        GraphConfig("Mapping",       "Mappings", is_function=None),
    ]
    for c in configs:
        GraphConfigProvider.register(c)


_build_graph_configs()
