"""drawers.py — All graph drawer classes and registry for Function Forge.

Each drawer:
  1. Inherits from GraphDrawer
  2. Is decorated with @GraphRegistry.register("Name")
  3. Implements draw(ctx: DrawingContext) -> None

The draw() method receives a fully set-up matplotlib Axes (cleared, grid drawn
if requested) and is responsible only for plotting the graph itself.
"""

from __future__ import annotations

import math
import random
from typing import Callable

import numpy as np

from .models import DrawingContext, AppConstants

# ── Axis helpers ───────────────────────────────────────────────────────────────
LO = AppConstants.AXIS_MIN   # -5
HI = AppConstants.AXIS_MAX   #  5


# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

class GraphRegistry:
    _drawers: dict[str, type[GraphDrawer]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(klass: type[GraphDrawer]):
            cls._drawers[name] = klass
            return klass
        return decorator

    @classmethod
    def get_drawer(cls, name: str) -> GraphDrawer | None:
        klass = cls._drawers.get(name)
        return klass() if klass else None

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._drawers.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Base class
# ═══════════════════════════════════════════════════════════════════════════════

class GraphDrawer:
    """Base class for all graph drawers."""

    def draw(self, ctx: DrawingContext) -> None:
        raise NotImplementedError

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _setup_axes(ctx: DrawingContext) -> None:
        """Draw the coordinate grid, axes lines, and tick marks."""
        ax = ctx.ax
        ax.clear()
        ax.set_facecolor("#ffffff")

        # Generous white padding so border grid lines sit well inside the frame
        PAD = 0.8
        ax.set_xlim(LO - PAD, HI + PAD)
        ax.set_ylim(LO - PAD, HI + PAD)
        ax.set_aspect("equal", adjustable="box")

        is_print = (ctx.grid_style == "print")

        # Draw grid as explicit clipped segments — stop exactly at ±5
        if ctx.show_grid:
            grid_color = "#999999" if is_print else "#cccccc"
            grid_lw    = 1.6      if is_print else 0.8
            for i in range(LO, HI + 1):
                ax.plot([LO, HI], [i, i], color=grid_color,
                        linewidth=grid_lw, zorder=1, solid_capstyle="butt")
                ax.plot([i, i], [LO, HI], color=grid_color,
                        linewidth=grid_lw, zorder=1, solid_capstyle="butt")

        # Axis lines — clipped to ±5, drawn over grid
        axis_lw = 2.2
        ax.plot([LO, HI], [0, 0], color="#000000", linewidth=axis_lw,
                zorder=2, solid_capstyle="butt")
        ax.plot([0, 0], [LO, HI], color="#000000", linewidth=axis_lw,
                zorder=2, solid_capstyle="butt")

        # Tick marks — only in color mode
        if not is_print:
            tick_len = 0.1
            for i in range(LO, HI + 1):
                if i == 0:
                    continue
                ax.plot([i, i], [-tick_len, tick_len], color="#000000",
                        linewidth=0.9, zorder=3)
                ax.plot([-tick_len, tick_len], [i, i], color="#000000",
                        linewidth=0.9, zorder=3)

        # Chevron arrowheads on axes — same style as line arrows
        import math as _math
        _arm, _angle = 0.28, 35
        for tip, dx, dy in [
            ( (HI,  0),  1,  0),
            ( (LO,  0), -1,  0),
            ( (0,  HI),  0,  1),
            ( (0,  LO),  0, -1),
        ]:
            tip_x, tip_y = tip
            for sign in (+1, -1):
                a = _math.radians(180 - sign * _angle)
                ca, sa = _math.cos(a), _math.sin(a)
                adx = dx * ca - dy * sa
                ady = dx * sa + dy * ca
                ax.plot(
                    [tip_x, tip_x + adx * _arm],
                    [tip_y, tip_y + ady * _arm],
                    color="black", linewidth=axis_lw,
                    solid_capstyle="round", zorder=6
                )

        # Remove matplotlib spines / ticks
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])

    @staticmethod
    def _draw_vlt(ctx: DrawingContext, x_vals: list[float]) -> None:
        """Draw a sweeping vertical line test indicator."""
        if not ctx.show_vlt:
            return
        # Draw a dashed vertical line at x = 1 as VLT indicator
        ctx.ax.axvline(1.0, color="#e74c3c", linewidth=1.2,
                       linestyle="--", zorder=6, alpha=0.7,
                       label="VLT")

    @staticmethod
    def _plot_dot(ax, x: float, y: float, style: str, color: str,
                  lw: float) -> None:
        """Plot a single dot, open or closed."""
        ms = max(5, lw * 3)
        if style == "open":
            ax.plot(x, y, "o", color=color, markersize=ms,
                    markerfacecolor="white", markeredgewidth=lw,
                    markeredgecolor=color, zorder=5)
        else:
            ax.plot(x, y, "o", color=color, markersize=ms,
                    markerfacecolor=color, zorder=5)


# ═══════════════════════════════════════════════════════════════════════════════
# LINE GRAPH DRAWERS
# ═══════════════════════════════════════════════════════════════════════════════

@GraphRegistry.register("Linear")
class LinearDrawer(GraphDrawer):
    """y = mx + b over [-5, 5], plus vertical and horizontal special cases."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        line_type = p.get("line_type")  # "vertical" | "horizontal" | None

        if line_type == "vertical":
            x_val = p.get("x_val", 0.0)
            x = np.full(400, float(x_val))
            y = np.linspace(LO, HI, 400)
            mask = np.ones(len(x), dtype=bool)
            ax.plot(x, y, color=ctx.graph_color,
                    linewidth=ctx.line_width, zorder=4, solid_capstyle="round")
            self._draw_chevron(ax, x_val, HI,  0,  1, ctx.graph_color, ctx.line_width)
            self._draw_chevron(ax, x_val, LO,  0, -1, ctx.graph_color, ctx.line_width)

        elif line_type == "horizontal":
            y_val = p.get("y_val", 0.0)
            x = np.linspace(LO, HI, 400)
            y = np.full(400, float(y_val))
            mask = np.ones(len(x), dtype=bool)
            ax.plot(x, y, color=ctx.graph_color,
                    linewidth=ctx.line_width, zorder=4, solid_capstyle="round")
            self._draw_chevron(ax, HI, y_val,  1,  0, ctx.graph_color, ctx.line_width)
            self._draw_chevron(ax, LO, y_val, -1,  0, ctx.graph_color, ctx.line_width)

        else:
            slope     = p.get("slope", 1.0)
            intercept = p.get("intercept", 0.0)
            x = np.linspace(LO, HI, 400)
            y = slope * x + intercept
            # Only plot strictly in-range points — no boundary clipping artifacts
            mask = (y >= LO) & (y <= HI)
            if mask.any():
                ax.plot(x[mask], y[mask], color=ctx.graph_color,
                        linewidth=ctx.line_width, zorder=4, solid_capstyle="round")
            self._add_line_arrows(ax, x, y, mask, ctx.graph_color, ctx.line_width)

        if ctx.show_vlt:
            self._draw_vlt(ctx, list(x))

    @staticmethod
    def _draw_chevron(ax, tip_x, tip_y, dx, dy, color, lw):
        """Draw a single chevron arrowhead at (tip_x, tip_y) pointing in (dx, dy)."""
        import math
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        arm, angle_deg = 0.45, 35
        for sign in (+1, -1):
            a = math.radians(180 - sign * angle_deg)
            ca, sa = math.cos(a), math.sin(a)
            ax.plot(
                [tip_x, tip_x + (ux * ca - uy * sa) * arm],
                [tip_y, tip_y + (ux * sa + uy * ca) * arm],
                color=color, linewidth=lw,
                solid_capstyle="round", zorder=5
            )

    @staticmethod
    def _add_line_arrows(ax, x, y, mask, color, lw):
        """Draw chevron arrowheads at each end of the line.

        Samples direction from far enough back that tight turns at the
        boundary don't produce a messy/misleading arrow direction.
        """
        import math
        vis_x = x[mask]
        vis_y = y[mask]
        n = len(vis_x)
        if n < 20:
            return

        arm = 0.45
        angle_deg = 35

        def draw_chevron(tip_x, tip_y, dx, dy):
            length = math.hypot(dx, dy)
            if length == 0:
                return
            ux, uy = dx / length, dy / length
            for sign in (+1, -1):
                a = math.radians(180 - sign * angle_deg)
                ca, sa = math.cos(a), math.sin(a)
                ax.plot(
                    [tip_x, tip_x + (ux * ca - uy * sa) * arm],
                    [tip_y, tip_y + (ux * sa + uy * ca) * arm],
                    color=color, linewidth=lw,
                    solid_capstyle="round", zorder=5
                )

        def best_direction(vx, vy, tip_idx, toward_tip):
            """Return direction vector that best represents the curve at tip_idx.

            Tries progressively larger look-back distances and picks the one
            whose angle changes least over the last portion — i.e. the
            straightest local tangent, avoiding messy tight-turn artifacts.
            """
            total = len(vx)
            # Candidate look-back step sizes
            candidates = [6, 12, 20, 30, min(50, total // 3)]
            best_dx, best_dy = None, None
            best_straightness = -1
            for step in candidates:
                if tip_idx == -1 or tip_idx == total - 1:
                    # end arrow
                    i0 = max(0, total - 1 - step)
                    i1 = total - 1
                else:
                    # start arrow
                    i0 = 0
                    i1 = min(total - 1, step)
                dx = vx[i1] - vx[i0]
                dy = vy[i1] - vy[i0]
                length = math.hypot(dx, dy)
                if length < 1e-6:
                    continue
                # Measure straightness: dot of this vector with mid-segment vector
                mid = (i0 + i1) // 2
                half = max(1, (i1 - i0) // 4)
                mdx = vx[min(mid + half, total-1)] - vx[max(mid - half, 0)]
                mdy = vy[min(mid + half, total-1)] - vy[max(mid - half, 0)]
                mlen = math.hypot(mdx, mdy)
                if mlen < 1e-6:
                    continue
                straightness = abs((dx * mdx + dy * mdy) / (length * mlen))
                if straightness > best_straightness:
                    best_straightness = straightness
                    best_dx, best_dy = dx, dy
            return best_dx or 1, best_dy or 0

        # End chevron
        dx_end, dy_end = best_direction(vis_x, vis_y, -1, True)
        draw_chevron(vis_x[-1], vis_y[-1], dx_end, dy_end)

        # Start chevron (flip direction so it points away from curve)
        dx_st, dy_st = best_direction(vis_x, vis_y, 0, False)
        draw_chevron(vis_x[0], vis_y[0], -dx_st, -dy_st)

    @classmethod
    def random_params(cls, line_type: str | None = None, **_) -> dict:
        if line_type == "vertical":
            x_val = random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
            return {"line_type": "vertical", "x_val": float(x_val)}
        if line_type == "horizontal":
            y_val = random.choice([-4, -3, -2, -1, 0, 1, 2, 3, 4])
            return {"line_type": "horizontal", "y_val": float(y_val)}
        if line_type == "proportional":
            slope = random.choice([-3, -2, -1, -0.5, 0.5, 1, 2, 3])
            return {"line_type": "proportional", "slope": slope, "intercept": 0.0}
        if line_type == "non_proportional":
            slope = random.choice([-3, -2, -1, -0.5, 0.5, 1, 2, 3])
            intercept = random.choice([-3, -2, -1, 1, 2, 3])
            return {"line_type": "non_proportional", "slope": slope, "intercept": float(intercept)}
        slope = random.choice([-3, -2, -1, -0.5, 0.5, 1, 2, 3])
        intercept = random.randint(-3, 3)
        return {"slope": slope, "intercept": intercept}


@GraphRegistry.register("Smooth Curve")
class SmoothCurveDrawer(GraphDrawer):
    """Sinusoidal / polynomial smooth curve."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        curve_type = p.get("curve_type", "sine")
        amplitude  = p.get("amplitude", 2.0)
        frequency  = p.get("frequency", 1.0)
        phase      = p.get("phase", 0.0)
        v_shift    = p.get("v_shift", 0.0)

        # Sideways curves: x = f(y) — relations, not functions
        if curve_type in ("quadratic_h", "cubic_h", "sine_h"):
            a = p.get("a", 1.0)
            h = p.get("h", 0.0)
            k = p.get("k", 0.0)
            y = np.linspace(LO, HI, 600)
            if curve_type == "quadratic_h":
                x = a * (y - k) ** 2 + h              # sideways parabola
            elif curve_type == "cubic_h":
                x = a * (y - k) ** 3 + h              # sideways S-curve (a is pre-scaled small)
            else:  # sine_h
                freq = p.get("freq", 1.0)
                x = a * np.sin(freq * (y - k)) + h    # sideways sine wave

            in_range = (x >= LO) & (x <= HI)
            # _plot_segments expects (horizontal_vals, vertical_vals) — pass (x, y)
            # but here x is the horizontal axis value for each sample, y is vertical
            SmoothCurveDrawer._plot_segments(ax, x, y, in_range,
                                              ctx.graph_color, ctx.line_width)

            # Arrowheads: find the two open ends of the visible curve.
            # The curve may split into two arms (parabola) or be one sweep (cubic).
            # Walk through contiguous in_range segments and draw a chevron at each end.
            indices = np.where(in_range)[0]
            if len(indices) >= 4:
                breaks = list(np.where(np.diff(indices) > 1)[0] + 1)
                segs = np.split(indices, breaks)
                import math as _m
                def _chev(tip_x, tip_y, dx, dy):
                    length = _m.hypot(dx, dy)
                    if length == 0:
                        return
                    ux, uy = dx / length, dy / length
                    arm, ang = 0.45, 35
                    for sign in (+1, -1):
                        a2 = _m.radians(180 - sign * ang)
                        ca, sa = _m.cos(a2), _m.sin(a2)
                        ax.plot([tip_x, tip_x + (ux*ca - uy*sa)*arm],
                                [tip_y, tip_y + (ux*sa + uy*ca)*arm],
                                color=ctx.graph_color, linewidth=ctx.line_width,
                                solid_capstyle="round", zorder=5)
                for seg in segs:
                    if len(seg) < 4:
                        continue
                    step = min(20, len(seg) // 3)
                    # tip at the low-y end of segment
                    i0, i1 = seg[0], seg[step]
                    _chev(x[i0], y[i0], x[i0] - x[i1], y[i0] - y[i1])
                    # tip at the high-y end of segment
                    i0, i1 = seg[-1], seg[-1 - step]
                    _chev(x[i0], y[i0], x[i0] - x[i1], y[i0] - y[i1])

            if ctx.show_vlt:
                self._draw_vlt(ctx, list(x))
            return

        x = np.linspace(LO, HI, 600)

        if curve_type == "sine":
            y = amplitude * np.sin(frequency * x + phase) + v_shift
        elif curve_type == "cosine":
            y = amplitude * np.cos(frequency * x + phase) + v_shift
        elif curve_type == "cubic":
            y = (amplitude / 25) * x ** 3 + v_shift
        elif curve_type == "quadratic":
            y = (amplitude / 5) * x ** 2 + v_shift
        else:
            y = amplitude * np.sin(frequency * x + phase) + v_shift

        # Only plot points strictly within the grid — no clipping to boundary
        # Split into contiguous segments so out-of-range gaps don't get connected
        in_range = (y >= LO) & (y <= HI)
        SmoothCurveDrawer._plot_segments(ax, x, y, in_range,
                                          ctx.graph_color, ctx.line_width)

        # Arrowheads at ends using in-range mask
        LinearDrawer._add_line_arrows(
            ax, x, y, in_range, ctx.graph_color, ctx.line_width
        )

        if ctx.show_vlt:
            self._draw_vlt(ctx, list(x))

    @staticmethod
    def _plot_segments(ax, x, y, mask, color, lw):
        """Plot only in-range points, breaking into separate segments at gaps."""
        import numpy as np
        # Find contiguous True runs in mask
        indices = np.where(mask)[0]
        if len(indices) == 0:
            return
        # Split into runs where index jumps by more than 1
        breaks = np.where(np.diff(indices) > 1)[0] + 1
        segments = np.split(indices, breaks)
        for seg in segments:
            if len(seg) < 2:
                continue
            ax.plot(x[seg], y[seg], color=color, linewidth=lw,
                    zorder=4, solid_capstyle="round")

    @classmethod
    def random_params(cls, fn_type: str = "random") -> dict:
        # quadratic_h, cubic_h, sine_h are non-functions (sideways curves)
        if fn_type == "not_function":
            curve_type = random.choice(["quadratic_h", "cubic_h", "sine_h"])
        elif fn_type == "function":
            curve_type = random.choice(["sine", "cosine", "cubic", "quadratic"])
        else:
            curve_type = random.choice(["sine", "cosine", "cubic", "quadratic",
                                        "quadratic_h", "cubic_h", "sine_h"])

        if curve_type in ("quadratic_h", "cubic_h", "sine_h"):
            h = random.uniform(-1.5, 1.5)
            k = random.uniform(-1.5, 1.5)
            if curve_type == "quadratic_h":
                # a controls how wide the parabola opens — 0.3–0.8 keeps it clearly visible
                a = random.choice([-0.8, -0.6, -0.4, 0.4, 0.6, 0.8])
                return {"curve_type": "quadratic_h", "a": a, "h": h, "k": k}
            elif curve_type == "cubic_h":
                # x = a*(y-k)^3 + h; y in [-5,5] so need a~0.03–0.07 for visible sweep
                a = random.choice([-0.07, -0.05, -0.04, 0.04, 0.05, 0.07])
                return {"curve_type": "cubic_h", "a": a, "h": h, "k": k}
            else:  # sine_h: x = a*sin(freq*(y-k)) + h
                a    = random.choice([-3.0, -2.5, -2.0, 2.0, 2.5, 3.0])
                freq = random.choice([0.5, 0.75, 1.0])
                return {"curve_type": "sine_h", "a": a, "h": h, "k": k, "freq": freq}

        amplitude  = random.uniform(1.5, 4.0)
        frequency  = random.choice([0.5, 1.0, 1.5, 2.0])
        phase      = random.uniform(0, math.pi)
        v_shift    = random.uniform(-1.5, 1.5)
        return {
            "curve_type": curve_type,
            "amplitude": amplitude,
            "frequency": frequency,
            "phase": phase,
            "v_shift": v_shift,
        }


@GraphRegistry.register("Piecewise")
class PiecewiseDrawer(GraphDrawer):
    """Piecewise linear function: 2–3 connected or disconnected segments."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        # segments: list of {"x0", "y0", "x1", "y1", "open_left", "open_right"}
        segments = p.get("segments", self._default_segments())

        for seg in segments:
            x0, y0 = seg["x0"], seg["y0"]
            x1, y1 = seg["x1"], seg["y1"]
            open_l  = seg.get("open_left", False)
            open_r  = seg.get("open_right", False)

            ax.plot([x0, x1], [y0, y1], color=ctx.graph_color,
                    linewidth=ctx.line_width, zorder=4,
                    solid_capstyle="round")

            # Endpoint dots
            self._plot_dot(ax, x0, y0,
                           "open" if open_l else ctx.dot_style,
                           ctx.graph_color, ctx.line_width)
            self._plot_dot(ax, x1, y1,
                           "open" if open_r else ctx.dot_style,
                           ctx.graph_color, ctx.line_width)

        if ctx.show_vlt:
            self._draw_vlt(ctx, [])

    @staticmethod
    def _default_segments() -> list[dict]:
        return [
            {"x0": -4, "y0": 3,  "x1": -1, "y1": 1,
             "open_left": False, "open_right": True},
            {"x0": -1, "y0": -1, "x1": 2,  "y1": 2,
             "open_left": False, "open_right": True},
            {"x0": 2,  "y0": -2, "x1": 4,  "y1": 0,
             "open_left": False, "open_right": False},
        ]

    @staticmethod
    def _random_fn_segments() -> list[dict]:
        """Non-overlapping segments — always a function."""
        n_segs = random.randint(2, 3)
        breakpoints = sorted(random.sample(range(-4, 5), n_segs - 1))
        xs = [LO + 1] + breakpoints + [HI - 1]
        segments = []
        for i in range(n_segs):
            x0, x1 = xs[i], xs[i + 1]
            y0 = random.randint(-4, 4)
            y1 = random.randint(-4, 4)
            open_r = (i < n_segs - 1) and random.choice([True, False])
            segments.append({
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "open_left": False, "open_right": open_r,
            })
        return segments

    @staticmethod
    def _random_not_fn_segments() -> list[dict]:
        """Segments with closed shared boundaries → same x maps to two y values → not a function."""
        n_segs = random.randint(2, 3)
        breakpoints = sorted(random.sample(range(-3, 4), n_segs - 1))
        xs = [LO + 1] + breakpoints + [HI - 1]
        segments = []
        prev_y1 = None
        for i in range(n_segs):
            x0, x1 = xs[i], xs[i + 1]
            # Ensure this segment's left y differs from prev segment's right y
            y0 = random.randint(-4, 4)
            if prev_y1 is not None:
                while y0 == prev_y1:
                    y0 = random.randint(-4, 4)
            y1 = random.randint(-4, 4)
            segments.append({
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "open_left": False, "open_right": False,
            })
            prev_y1 = y1
        return segments

    @classmethod
    def random_params(cls, fn_type: str = "random") -> dict:
        if fn_type == "not_function":
            return {"segments": cls._random_not_fn_segments()}
        if fn_type == "random" and random.random() < 0.5:
            return {"segments": cls._random_not_fn_segments()}
        return {"segments": cls._random_fn_segments()}


@GraphRegistry.register("Step Function")
class StepFunctionDrawer(GraphDrawer):
    """Horizontal steps — classic floor/ceiling function style."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        # steps: list of {"x0", "x1", "y", "open_left", "open_right"}
        steps = p.get("steps", self._default_steps())

        for step in steps:
            x0, x1, y = step["x0"], step["x1"], step["y"]
            open_l = step.get("open_left", False)
            open_r = step.get("open_right", True)

            ax.plot([x0, x1], [y, y], color=ctx.graph_color,
                    linewidth=ctx.line_width, zorder=4,
                    solid_capstyle="butt")

            self._plot_dot(ax, x0, y,
                           "open" if open_l else ctx.dot_style,
                           ctx.graph_color, ctx.line_width)
            self._plot_dot(ax, x1, y,
                           "open" if open_r else ctx.dot_style,
                           ctx.graph_color, ctx.line_width)

        if ctx.show_vlt:
            self._draw_vlt(ctx, [])

    @staticmethod
    def _default_steps() -> list[dict]:
        return [
            {"x0": -5, "x1": -2, "y":  2, "open_left": False, "open_right": True},
            {"x0": -2, "x1":  1, "y": -1, "open_left": False, "open_right": True},
            {"x0":  1, "x1":  4, "y":  3, "open_left": False, "open_right": True},
            {"x0":  4, "x1":  5, "y":  0, "open_left": False, "open_right": False},
        ]

    @classmethod
    def random_params(cls) -> dict:
        n_steps = random.randint(3, 5)
        # Create n_steps non-overlapping horizontal segments
        width = (HI - LO) / n_steps
        steps = []
        for i in range(n_steps):
            x0 = LO + i * width
            x1 = x0 + width
            y  = random.randint(-4, 4)
            steps.append({
                "x0": round(x0, 1), "x1": round(x1, 1), "y": y,
                "open_left": False, "open_right": (i < n_steps - 1),
            })
        return {"steps": steps}


@GraphRegistry.register("Parametric")
class ParametricDrawer(GraphDrawer):
    """Closed parametric curve — a relation, not a function."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        curve = p.get("curve", "ellipse")
        rx    = p.get("rx", 3.0)
        ry    = p.get("ry", 2.0)
        cx    = p.get("cx", 0.0)
        cy    = p.get("cy", 0.0)
        twist = p.get("twist", 0.0)  # for figure-8 / lemniscate

        t = np.linspace(0, 2 * math.pi, 600)

        if curve == "ellipse":
            x = cx + rx * np.cos(t)
            y = cy + ry * np.sin(t)
        elif curve == "lemniscate":
            # Lemniscate of Bernoulli style
            scale = p.get("scale", 3.0)
            denom = 1 + np.sin(t) ** 2
            x = cx + scale * np.cos(t) / denom
            y = cy + scale * np.sin(t) * np.cos(t) / denom
        elif curve == "limacon":
            a = p.get("a", 2.0)
            b = p.get("b", 1.5)
            r = a + b * np.cos(t)
            x = cx + r * np.cos(t)
            y = cy + r * np.sin(t)
        else:
            x = cx + rx * np.cos(t)
            y = cy + ry * np.sin(t)

        # Clip to axis range
        x = np.clip(x, LO, HI)
        y = np.clip(y, LO, HI)

        ax.plot(x, y, color=ctx.graph_color,
                linewidth=ctx.line_width, zorder=4)

        # Direction chevron partway along the curve
        mid = len(t) // 4
        dx = x[mid + 4] - x[mid]
        dy = y[mid + 4] - y[mid]
        LinearDrawer._add_line_arrows.__func__ if False else None
        # Inline chevron for parametric
        import math as _math
        arm, angle_deg = 0.28, 35
        tip_x, tip_y = x[mid + 4], y[mid + 4]
        length = _math.hypot(dx, dy)
        if length > 0:
            ux, uy = dx / length, dy / length
            for sign in (+1, -1):
                a = _math.radians(180 - sign * angle_deg)
                ca, sa = _math.cos(a), _math.sin(a)
                adx = ux * ca - uy * sa
                ady = ux * sa + uy * ca
                ctx.ax.plot(
                    [tip_x, tip_x + adx * arm],
                    [tip_y, tip_y + ady * arm],
                    color=ctx.graph_color, linewidth=ctx.line_width,
                    solid_capstyle="round", zorder=5
                )

        if ctx.show_vlt:
            self._draw_vlt(ctx, list(x))

    @classmethod
    def random_params(cls) -> dict:
        curve = random.choice(["ellipse", "ellipse", "lemniscate", "limacon"])
        if curve == "ellipse":
            return {
                "curve": "ellipse",
                "rx": random.uniform(1.5, 4.0),
                "ry": random.uniform(1.0, 3.5),
                "cx": random.uniform(-1.0, 1.0),
                "cy": random.uniform(-1.0, 1.0),
            }
        elif curve == "lemniscate":
            return {
                "curve": "lemniscate",
                "scale": random.uniform(2.0, 4.0),
                "cx": 0.0, "cy": 0.0,
            }
        else:  # limacon
            return {
                "curve": "limacon",
                "a": random.uniform(1.5, 3.0),
                "b": random.uniform(0.5, 2.0),
                "cx": 0.0, "cy": 0.0,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# SET MODEL DRAWERS
# ═══════════════════════════════════════════════════════════════════════════════

@GraphRegistry.register("Scatter Plot")
class ScatterPlotDrawer(GraphDrawer):
    """Discrete scatter points with no connecting lines."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        points = p.get("points", [])
        if not points:
            return

        for x, y in points:
            self._plot_dot(ax, x, y, ctx.dot_style,
                           ctx.graph_color, ctx.line_width)

        if ctx.show_vlt:
            self._draw_vlt(ctx, [pt[0] for pt in points])

    @classmethod
    def random_params(cls, fn_type: str = "random") -> dict:
        n = random.randint(5, 10)
        if fn_type == "random":
            is_function = random.choice([True, False])
        else:
            is_function = (fn_type == "function")
        if is_function:
            xs = random.sample(range(LO + 1, HI), min(n, HI - LO - 1))
            points = [(x, random.randint(LO + 1, HI - 1)) for x in xs]
        else:
            # Guarantee at least one x appears twice (definite non-function)
            xs_pool = list(range(LO + 1, HI))
            unique_count = min(n - 1, len(xs_pool))
            unique_xs = random.sample(xs_pool, unique_count)
            repeat_x = random.choice(unique_xs)
            points = [(x, random.randint(LO + 1, HI - 1)) for x in unique_xs]
            existing_y = next(y for x, y in points if x == repeat_x)
            diff_y = random.choice([y for y in range(LO + 1, HI) if y != existing_y])
            points.append((repeat_x, diff_y))
            random.shuffle(points)
        return {"points": points}


@GraphRegistry.register("Discrete Points")
class DiscretePointsDrawer(GraphDrawer):
    """Isolated points forming an ordered set (like a mapping output)."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax = ctx.ax
        p = ctx.params

        points = p.get("points", [])
        if not points:
            return

        for x, y in points:
            self._plot_dot(ax, x, y, ctx.dot_style,
                           ctx.graph_color, ctx.line_width)

        if ctx.show_vlt:
            self._draw_vlt(ctx, [pt[0] for pt in points])

    @classmethod
    def random_params(cls) -> dict:
        n = random.randint(4, 8)
        is_function = random.choice([True, False])
        if is_function:
            xs = random.sample(range(LO + 1, HI), min(n, HI - LO - 1))
            points = sorted([(x, random.randint(LO + 1, HI - 1)) for x in xs])
        else:
            xs = [random.randint(LO + 1, HI - 1) for _ in range(n)]
            ys = [random.randint(LO + 1, HI - 1) for _ in range(n)]
            points = sorted(zip(xs, ys))
        return {"points": list(points)}



# ═══════════════════════════════════════════════════════════════════════════════
# MAPPING DRAWER
# ═══════════════════════════════════════════════════════════════════════════════

@GraphRegistry.register("Mapping")
class MappingDrawer(GraphDrawer):
    """Two-oval mapping diagram with arrows between domain and range values."""

    def draw(self, ctx: DrawingContext) -> None:
        import math as _m
        ax = ctx.ax
        ax.clear()
        ax.set_facecolor("#ffffff")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.set_aspect("equal", adjustable="box")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])

        p           = ctx.params
        domain_raw     = p.get("domain", [1, 2, 3])
        range_vals_raw = p.get("range_vals", [4, 5, 6])
        arrows_raw     = p.get("arrows", [(0, 0), (1, 1), (2, 2)])
        show_labels    = p.get("show_labels", True)
        lw             = max(1.2, ctx.line_width * 0.55)

        # ── Filter: only show values that participate in at least one arrow ──────
        used_d = {di for di, ri in arrows_raw}
        used_r = {ri for di, ri in arrows_raw}
        # Build index remapping: old index → new index (or None if filtered out)
        d_keep   = [i for i in range(len(domain_raw))     if i in used_d]
        r_keep   = [i for i in range(len(range_vals_raw)) if i in used_r]
        d_remap  = {old: new for new, old in enumerate(d_keep)}
        r_remap  = {old: new for new, old in enumerate(r_keep)}
        domain     = [domain_raw[i]     for i in d_keep]
        range_vals = [range_vals_raw[i] for i in r_keep]
        arrows     = [
            (d_remap[di], r_remap[ri])
            for di, ri in arrows_raw
            if di in d_remap and ri in r_remap
        ]

        # ── Shape & geometry ─────────────────────────────────────────────────
        shape  = p.get("shape", "oval")   # "oval" | "rectangle"
        lx, rx = 2.5, 7.5
        cy     = 5.0
        ow     = 1.55   # half-width  (wider -> rounder feel)
        oh     = 2.8    # half-height (shorter than before)

        container_lw = max(1.8, lw * 1.2)

        from matplotlib.patches import Ellipse, FancyBboxPatch
        for cx in (lx, rx):
            if shape == "rectangle":
                radius = 0.45
                ax.add_patch(FancyBboxPatch(
                    (cx - ow, cy - oh), ow * 2, oh * 2,
                    boxstyle=f"round,pad=0,rounding_size={radius}",
                    fill=False, edgecolor="#000000",
                    linewidth=container_lw, zorder=2
                ))
            else:
                ax.add_patch(Ellipse(
                    (cx, cy), width=ow * 2, height=oh * 2,
                    fill=False, edgecolor="#000000",
                    linewidth=container_lw, zorder=2
                ))

        # ── X / Y labels above shapes ─────────────────────────────────────────
        if show_labels:
            ax.text(lx, cy + oh + 0.45, "X", ha="center", va="bottom",
                    fontsize=15, fontweight="bold", color="#000000", zorder=3)
            ax.text(rx, cy + oh + 0.45, "Y", ha="center", va="bottom",
                    fontsize=15, fontweight="bold", color="#000000", zorder=3)

        # ── Value positions — centred horizontally inside each shape ──────────
        def value_positions(values, cx):
            n = len(values)
            if n == 0:
                return []
            span = min(oh * 1.35, max(0.1, (n - 1) * 0.95))
            ys = [cy] if n == 1 else [
                cy - span / 2 + i * span / (n - 1) for i in range(n)
            ]
            return [(cx, y) for y in ys]   # centred on oval axis

        d_pos = value_positions(domain,     lx)
        r_pos = value_positions(range_vals, rx)

        fs_val = 16   # large, bold numbers
        for i, (vx, vy) in enumerate(d_pos):
            ax.text(vx, vy, str(domain[i]), ha="center", va="center",
                    fontsize=fs_val, fontweight="bold", color="#000000", zorder=3)
        for i, (vx, vy) in enumerate(r_pos):
            ax.text(vx, vy, str(range_vals[i]), ha="center", va="center",
                    fontsize=fs_val, fontweight="bold", color="#000000", zorder=3)

        # ── Arrows — from just right of each domain number to just left of range number
        arrow_lw = max(1.0, ctx.line_width * 0.45)
        # Estimate text half-width based on font size in data units
        # At fontsize 16 in a 0-10 axis space, ~0.35 units per character
        char_w = 0.38

        # Base chevron geometry
        BASE_ARM   = 0.28
        angle_deg  = 30
        tip_sep    = 2 * BASE_ARM * _m.sin(_m.radians(angle_deg)) * 0.55  # tightened

        from collections import Counter
        in_visits = Counter(ri for di, ri in arrows)
        in_index  = {}

        for (di, ri) in arrows:
            if di >= len(d_pos) or ri >= len(r_pos):
                continue

            d_text = str(domain[di])
            r_text = str(range_vals[ri])
            d_half = len(d_text) * char_w / 2 + 0.12
            r_half = len(r_text) * char_w / 2 + 0.12

            sx = d_pos[di][0] + d_half
            sy = d_pos[di][1]

            base_ex = r_pos[ri][0] - r_half
            base_ey = r_pos[ri][1]

            n_in  = in_visits[ri]
            i_in  = in_index.get(ri, 0)
            in_index[ri] = i_in + 1
            tip_offset = (i_in - (n_in - 1) / 2) * tip_sep if n_in > 1 else 0.0

            ex = base_ex
            ey = base_ey + tip_offset

            dx, dy = ex - sx, ey - sy
            if _m.hypot(dx, dy) < 0.1:
                continue

            ax.plot([sx, ex], [sy, ey], color="#000000",
                    linewidth=arrow_lw, zorder=4, solid_capstyle="round")

            # Scale chevron arm down for crowded targets: each extra arrow
            # shrinks the arm so heads stay tight rather than overlapping.
            arm = BASE_ARM / max(1, n_in ** 0.6)

            length = _m.hypot(dx, dy)
            ux, uy = dx / length, dy / length
            for sign in (+1, -1):
                a = _m.radians(180 - sign * angle_deg)
                ca, sa = _m.cos(a), _m.sin(a)
                ax.plot(
                    [ex, ex + (ux * ca - uy * sa) * arm],
                    [ey, ey + (ux * sa + uy * ca) * arm],
                    color="#000000", linewidth=arrow_lw,
                    solid_capstyle="round", zorder=5
                )

        ctx.ax.figure.canvas.draw()

    @classmethod
    def random_params(cls, fn_type: str = "random", shape: str = "mixed") -> dict:
        import random
        style = random.choice(["ones", "fives"])
        pool  = list(range(0, 21)) if style == "ones" else list(range(0, 101, 5))

        nd = random.randint(2, 5)
        nr = random.randint(2, 5)
        domain     = sorted(random.sample(pool, min(nd, len(pool))))
        range_vals = sorted(random.sample(pool, min(nr, len(pool))))

        if fn_type == "function":
            is_function = True
        elif fn_type == "not_function":
            is_function = False
        else:
            is_function = random.random() < 0.5

        out_count = [0] * nd
        in_count  = [0] * nr
        arrows    = []
        pairs = [(di, ri) for di in range(nd) for ri in range(nr)]
        random.shuffle(pairs)

        if is_function:
            # Every domain value gets exactly one arrow → strict function
            # Shuffle domain indices and assign each one a range target
            domain_order = list(range(nd))
            random.shuffle(domain_order)
            for di in domain_order:
                candidates = [ri for ri in range(nr) if in_count[ri] < 3]
                if not candidates:
                    break
                ri = random.choice(candidates)
                arrows.append((di, ri))
                out_count[di] += 1
                in_count[ri]  += 1
        else:
            # Non-function: at least one domain value maps to 2+ range values
            target = random.randint(nd + 1, min(nd * 2, nd * nr))
            for di, ri in pairs:
                if len(arrows) >= target:
                    break
                if out_count[di] >= 3 or in_count[ri] >= 3:
                    continue
                arrows.append((di, ri))
                out_count[di] += 1
                in_count[ri]  += 1
            # Ensure at least one domain value has 2 outgoing arrows
            multi_out = [di for di in range(nd) if out_count[di] >= 2]
            if not multi_out:
                # Force one domain value to get a second arrow
                for di in range(nd):
                    extras = [(di, ri) for ri in range(nr)
                              if (di, ri) not in arrows and in_count[ri] < 3]
                    if extras:
                        di2, ri2 = random.choice(extras)
                        arrows.append((di2, ri2))
                        break

        chosen_shape = (
            random.choice(["oval", "rectangle"])
            if shape in ("mixed", None)
            else shape
        )
        return {
            "domain":      domain,
            "range_vals":  range_vals,
            "arrows":      arrows,
            "show_labels": True,
            "shape":       chosen_shape,
        }

# ═══════════════════════════════════════════════════════════════════════════════
# RECIPROCAL DRAWER
# ═══════════════════════════════════════════════════════════════════════════════

@GraphRegistry.register("Reciprocal")
class ReciprocalDrawer(GraphDrawer):
    """y = k / (x - h) + v  — hyperbola with vertical and horizontal asymptotes."""

    def draw(self, ctx: DrawingContext) -> None:
        self._setup_axes(ctx)
        ax  = ctx.ax
        p   = ctx.params

        k = p.get("k",  1.0)   # stretch / flip
        h = p.get("h",  0.0)   # horizontal shift (vertical asymptote at x=h)
        v = p.get("v",  0.0)   # vertical shift   (horizontal asymptote at y=v)

        # Draw asymptotes as light dashed lines
        asy_color = "#aaaaaa"
        asy_lw    = 1.0
        ax.plot([h, h], [LO, HI], color=asy_color, linewidth=asy_lw,
                linestyle="--", zorder=2, solid_capstyle="butt")
        ax.plot([LO, HI], [v, v], color=asy_color, linewidth=asy_lw,
                linestyle="--", zorder=2, solid_capstyle="butt")

        # Plot each branch separately, skipping the singularity at x == h
        eps   = 1e-6
        x_all = np.linspace(LO, HI, 1200)

        for branch_mask in [x_all < h - eps, x_all > h + eps]:
            xb = x_all[branch_mask]
            if len(xb) < 2:
                continue
            yb = k / (xb - h) + v
            in_range = (yb >= LO) & (yb <= HI)
            SmoothCurveDrawer._plot_segments(
                ax, xb, yb, in_range, ctx.graph_color, ctx.line_width
            )
            # Arrowhead at the far end of each branch
            LinearDrawer._add_line_arrows(
                ax, xb, yb, in_range, ctx.graph_color, ctx.line_width
            )

        if ctx.show_vlt:
            self._draw_vlt(ctx, list(x_all))

    @classmethod
    def random_params(cls) -> dict:
        k = random.choice([-3, -2, -1, 1, 2, 3])
        h = random.choice([-2, -1, 0, 1, 2])
        v = random.choice([-2, -1, 0, 1, 2])
        return {"k": k, "h": h, "v": v}


# ═══════════════════════════════════════════════════════════════════════════════
# Random generation dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_RANDOM_DRAWERS: dict[str, type] = {
    "Linear":          LinearDrawer,
    "Smooth Curve":    SmoothCurveDrawer,
    "Piecewise":       PiecewiseDrawer,
    "Step Function":   StepFunctionDrawer,
    "Parametric":      ParametricDrawer,
    "Scatter Plot":    ScatterPlotDrawer,
    "Reciprocal":      ReciprocalDrawer,
    "Mapping":         MappingDrawer,
}

# ── Function-type classification ───────────────────────────────────────────────

# "function"     → always passes the vertical line test
# "not_function" → always fails the vertical line test
# "either"       → can be either depending on random params
_FN_SUPPORT: dict[str, str] = {
    "Linear":        "function",
    "Smooth Curve":  "either",
    "Reciprocal":    "function",
    "Step Function": "function",
    "Parametric":    "not_function",
    "Piecewise":     "either",
    "Scatter Plot":  "either",
    "Line Segment":  "either",
    "Mapping":       "either",
}

# Graph names eligible to be drawn for each fn_type filter
_FN_CAPABLE: dict[str, list[str]] = {
    "function": [
        "Linear", "Smooth Curve", "Reciprocal", "Step Function",
        "Piecewise", "Scatter Plot", "Line Segment", "Mapping",
    ],
    "not_function": [
        "Parametric", "Piecewise", "Scatter Plot", "Smooth Curve",
        "Line Segment", "Mapping",
    ],
    "random": list(_RANDOM_DRAWERS.keys()),
}


def get_random_params(graph_name: str, fn_type: str = "random",
                      linear_type: str | None = None,
                      mapping_shape: str = "mixed") -> dict:
    """Return randomly generated params for the given graph type."""
    klass = _RANDOM_DRAWERS.get(graph_name)
    if klass and hasattr(klass, "random_params"):
        if graph_name == "Linear" and linear_type is not None:
            return klass.random_params(line_type=linear_type)
        if graph_name == "Mapping":
            return klass.random_params(fn_type=fn_type, shape=mapping_shape)
        try:
            return klass.random_params(fn_type=fn_type)
        except TypeError:
            return klass.random_params()
    return {}


def random_graph_name(category: str | None = None) -> str:
    """Pick a random graph name, optionally filtered by category."""
    from .models import GraphConfigProvider
    names = list(_RANDOM_DRAWERS.keys())
    if category:
        from .models import GraphConfigProvider
        names = [n for n in names
                 if (cfg := GraphConfigProvider.get(n)) and cfg.category == category]
    return random.choice(names) if names else "Linear"