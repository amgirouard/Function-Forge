"""streamlit_app.py — Function Forge web application (Streamlit).

Run with:
    streamlit run streamlit_app.py
or:
    python run.py
"""

from __future__ import annotations

import os
import random
import sys
import threading
import warnings
import zipfile
from io import BytesIO

# Ensure the project root is on sys.path so absolute imports work
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Force the non-interactive Agg backend before any other matplotlib import.
# Required on headless servers (no display) and prevents fork-safety issues.
import matplotlib
matplotlib.use("Agg")

import streamlit as st
from matplotlib.figure import Figure

# Suppress noisy matplotlib warnings that surface in the browser log
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# Single lock so concurrent Streamlit sessions don't collide in matplotlib
_mpl_lock = threading.Lock()

from function_forge.models import AppConstants, DrawingContext
from function_forge.drawers import (
    GraphRegistry,
    get_random_params,
    _FN_SUPPORT,
    _FN_CAPABLE,
)
from function_forge.validators import CoordinateValidator


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# UI-facing dropdown groups (collapsed from the full drawer list)
MODEL_DATA: dict[str, list[str]] = {
    "Graphs":   ["Linear", "Smooth Curve", "Piecewise", "Scatter Plot", "Line Segment"],
    "Mappings": ["Mapping"],
}

# Sub-type options for grouped graph types
_CURVE_SUBTYPES     = ["Smooth Curve", "Reciprocal", "Mixed"]
_PIECEWISE_SUBTYPES = ["Piecewise", "Step Function", "Absolute Value", "Mixed"]

# All actual drawers (used for Random mode and Batch Export)
_ALL_GRAPH_DRAWERS = [
    "Linear", "Smooth Curve", "Reciprocal",
    "Piecewise", "Step Function", "Parametric", "Scatter Plot", "Line Segment",
]
_ALL_DRAWERS = _ALL_GRAPH_DRAWERS + ["Mapping"]

# Reverse lookup: actual drawer → display group in dropdown
_DRAWER_GROUP: dict[str, str] = {
    "Linear":        "Linear",
    "Smooth Curve":  "Smooth Curve",
    "Reciprocal":    "Smooth Curve",
    "Piecewise":     "Piecewise",
    "Step Function": "Piecewise",
    "Scatter Plot":  "Scatter Plot",
    "Line Segment":  "Line Segment",
    "Mapping":       "Mapping",
    "Parametric":    "Parametric",   # only via Random
}

_LT_OPTIONS = ["Vertical", "Horizontal", "Proportional", "Non-Proportional", "Mixed"]
_LT_MAP: dict[str, str | None] = {
    "Mixed":              None,
    "Vertical":         "vertical",
    "Horizontal":       "horizontal",
    "Proportional":     "proportional",
    "Non-Proportional": "non_proportional",
}
_LT_REVERSE: dict[str | None, str] = {v: k for k, v in _LT_MAP.items()}

_FN_LABELS  = ["Function", "Not a Function", "Mixed"]
_FN_MAP     = {"Function": "function", "Not a Function": "not_function", "Mixed": "random"}
_FN_REVERSE = {v: k for k, v in _FN_MAP.items()}

_MAPPING_SHAPES        = ["Oval", "Rectangle", "Mixed"]
_MAPPING_SHAPE_MAP     = {"Oval": "oval", "Rectangle": "rectangle", "Mixed": "mixed"}
_MAPPING_SHAPE_REVERSE = {v: k for k, v in _MAPPING_SHAPE_MAP.items()}

_SENTINEL = object()


# ═══════════════════════════════════════════════════════════════════════════════
# Page config (must be first Streamlit call)
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Function Forge",
    page_icon="📐",
    layout="wide",
)

# ── Compact sidebar spacing ───────────────────────────────────────────────────
st.markdown("""
<style>
/* Tighten vertical rhythm throughout the sidebar */
[data-testid="stSidebar"] .stRadio,
[data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stSlider,
[data-testid="stSidebar"] .stButton,
[data-testid="stSidebar"] .stDownloadButton,
[data-testid="stSidebar"] .stNumberInput {
    margin-top: 0rem;
    margin-bottom: 0rem;
    padding-top: 0rem;
    padding-bottom: 0rem;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
    gap: 0rem;
}
[data-testid="stSidebar"] hr {
    margin-top: 0.4rem;
    margin-bottom: 0.4rem;
}
/* Remove gap between Vertical/Horizontal and Proportional rows using DevTools class */
.st-key-lt_radio_group {
    margin-top: -1.5rem !important;
}
.st-key-_lt_row2 {
    margin-top: -1.45rem !important;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Session-state initialisation
# ═══════════════════════════════════════════════════════════════════════════════

def _init_state() -> None:
    defaults: dict = {
        "category":          "Graphs",
        "graph_group":       "Linear",   # what the dropdown shows
        "model":             "Linear",   # actual drawer name
        "params":            {},
        "fn_type":           "random",
        "linear_type":       None,
        "curve_subtype":     None,       # None | "Smooth Curve" | "Reciprocal"
        "piecewise_subtype": None,       # None | "Piecewise" | "Step Function"
        "show_grid":         True,
        "grid_style":        "print",
        "graph_color":       "#000000",
        "line_width":        4.0,
        "mapping_shape":     "mixed",
        "show_xy_labels":    True,
        "scatter_text":      "",
        "lineseg_text":      "",
        "batch_fn_type":      "random",
        "batch_display_type": "graph",
        "batch_count":        10,
        "batch_zip":          None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_drawer(graph_group: str,
                    curve_subtype: str | None,
                    piecewise_subtype: str | None,
                    fn_type: str = "random") -> str:
    """Return the actual drawer name for a given group + sub-type selection."""
    if graph_group == "Smooth Curve":
        if curve_subtype == "Reciprocal":
            return "Reciprocal"
        if curve_subtype == "Smooth Curve":
            return "Smooth Curve"
        return random.choice(["Smooth Curve", "Reciprocal"])
    if graph_group == "Piecewise":
        if piecewise_subtype == "Step Function":
            return "Step Function"
        if piecewise_subtype in ("Piecewise", "Absolute Value"):
            return "Piecewise"
        return random.choice(["Piecewise", "Step Function"])
    return graph_group  # Linear, Scatter Plot, Mapping, etc.


def _regen(
    graph_group:       str | None = None,
    linear_type:       object     = _SENTINEL,
    curve_subtype:     object     = _SENTINEL,
    piecewise_subtype: object     = _SENTINEL,
    fn_type:           str | None = None,
) -> None:
    """Resolve the actual drawer, generate params, store in session_state."""
    gg = graph_group or st.session_state.graph_group
    ft = fn_type     or st.session_state.fn_type
    lt = st.session_state.linear_type       if linear_type       is _SENTINEL else linear_type
    cs = st.session_state.curve_subtype     if curve_subtype     is _SENTINEL else curve_subtype
    ps = st.session_state.piecewise_subtype if piecewise_subtype is _SENTINEL else piecewise_subtype

    actual = _resolve_drawer(gg, cs, ps, ft)
    st.session_state.model  = actual
    st.session_state.params = get_random_params(
        actual, fn_type=ft,
        linear_type=lt if actual == "Linear" else None,
        mapping_shape=st.session_state.get("mapping_shape", "mixed"),
        piecewise_subtype=ps if actual == "Piecewise" else None,
    )
    if actual == "Scatter Plot":
        pts = st.session_state.params.get("points", [])
        st.session_state.scatter_text = CoordinateValidator.format_points(pts)
    if actual == "Line Segment":
        p = st.session_state.params
        st.session_state.lineseg_text = CoordinateValidator.format_points([
            (p.get("x0", -3.0), p.get("y0", -2.0)),
            (p.get("x1",  3.0), p.get("y1",  2.0)),
        ])


def _render_figure(model: str, params: dict, *,
                   line_width: float, graph_color: str,
                   show_grid: bool, grid_style: str) -> Figure:
    """Create and return a rendered matplotlib Figure (thread-safe)."""
    with _mpl_lock:
        fig = Figure(figsize=(7, 5.25))
        fig.patch.set_facecolor("white")
        _mx = AppConstants.CANVAS_PAPER_MARGIN
        ax  = fig.add_axes([_mx, _mx, 1 - 2 * _mx, 1 - 2 * _mx])

        ctx = DrawingContext(
            ax=ax,
            line_width=line_width,
            graph_color=graph_color,
            show_grid=show_grid,
            dot_style="closed",
            show_vlt=False,
            grid_style=grid_style,
            params=params,
        )

        drawer = GraphRegistry.get_drawer(model)
        if drawer:
            drawer.draw(ctx)

    return fig


def _build_batch_zip(count: int, fn_type: str, display_type: str) -> bytes:
    """Generate ``count`` graphs and return them as an in-memory ZIP."""
    if display_type == "graph":
        pool = list(_ALL_GRAPH_DRAWERS)
    elif display_type == "mapping":
        pool = ["Mapping"]
    else:
        pool = list(_ALL_DRAWERS)

    capable  = _FN_CAPABLE.get(fn_type, list(_FN_CAPABLE["random"]))
    filtered = [m for m in pool if m in capable] or pool

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(count):
            model_name = random.choice(filtered)
            params     = get_random_params(model_name, fn_type=fn_type)
            fig = _render_figure(
                model_name, params,
                line_width=4.0, graph_color="#000000",
                show_grid=True, grid_style="print",
            )
            img = BytesIO()
            with _mpl_lock:
                fig.savefig(img, format="png", dpi=200,
                            bbox_inches="tight", pad_inches=0.05,
                            facecolor="white")
                fig.clf()
            safe = model_name.lower().replace(" ", "_")
            zf.writestr(f"{safe}_{i + 1:03d}.png", img.getvalue())

    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📐 Function Forge")
    st.divider()

    # ── Category ──────────────────────────────────────────────────────────────
    all_cats = list(MODEL_DATA.keys()) + ["Random"]
    cat_idx  = all_cats.index(st.session_state.category) \
               if st.session_state.category in all_cats else 0
    category = st.selectbox("Category", all_cats, index=cat_idx)

    if category != st.session_state.category:
        st.session_state.category          = category
        st.session_state.linear_type       = None
        st.session_state.curve_subtype     = None
        st.session_state.piecewise_subtype = None
        if category != "Random":
            first = MODEL_DATA.get(category, ["Linear"])[0]
            st.session_state.graph_group = first
            _regen(graph_group=first,
                   linear_type=None, curve_subtype=None, piecewise_subtype=None)

    # ── Random category ───────────────────────────────────────────────────────
    if category == "Random":
        # Function type — horizontal row
        fn_label_r  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
        fn_choice_r = st.radio(
            "Type", _FN_LABELS,
            index=_FN_LABELS.index(fn_label_r),
            key="fn_radio_random",
            horizontal=True,
        )
        st.session_state.fn_type = _FN_MAP[fn_choice_r]

        # Buttons — single column
        capable = _FN_CAPABLE.get(st.session_state.fn_type,
                                   list(_FN_CAPABLE["random"]))
        if st.button("⟳ Random", use_container_width=True):
            pool = [m for m in _ALL_DRAWERS if m in capable] or _ALL_DRAWERS
            m = random.choice(pool)
            st.session_state.graph_group = _DRAWER_GROUP.get(m, m)
            st.session_state.model       = m
            st.session_state.params      = get_random_params(
                m, fn_type=st.session_state.fn_type)

        if st.button("⟳ Graph", use_container_width=True):
            pool = [m for m in _ALL_GRAPH_DRAWERS if m in capable] \
                   or _ALL_GRAPH_DRAWERS
            m = random.choice(pool)
            st.session_state.graph_group = _DRAWER_GROUP.get(m, m)
            st.session_state.model       = m
            st.session_state.params      = get_random_params(
                m, fn_type=st.session_state.fn_type)

        if st.button("⟳ Mapping", use_container_width=True):
            st.session_state.graph_group = "Mapping"
            st.session_state.model       = "Mapping"
            st.session_state.params      = get_random_params(
                "Mapping", fn_type=st.session_state.fn_type)

    # ── Normal category ───────────────────────────────────────────────────────
    else:
        models      = MODEL_DATA.get(category, [])
        prev_group  = st.session_state.graph_group

        # For the Mappings category there's only one type, so show a blank
        # placeholder label instead of "Mapping" in the dropdown.
        if category == "Mappings":
            st.selectbox("Graph Type", ["---"], index=0, disabled=True)
            graph_group = "Mapping"
            if graph_group != prev_group:
                st.session_state.graph_group       = graph_group
                st.session_state.linear_type       = None
                st.session_state.curve_subtype     = None
                st.session_state.piecewise_subtype = None
                _regen(graph_group=graph_group,
                       linear_type=None, curve_subtype=None, piecewise_subtype=None)
        else:
            group_idx   = models.index(prev_group) if prev_group in models else 0
            graph_group = st.selectbox("Graph Type", models, index=group_idx)

            if graph_group != prev_group:
                st.session_state.graph_group       = graph_group
                st.session_state.linear_type       = None
                st.session_state.curve_subtype     = None
                st.session_state.piecewise_subtype = None
                _regen(graph_group=graph_group,
                       linear_type=None, curve_subtype=None, piecewise_subtype=None)

        # ── Linear: sub-types → New Graph ─────────────────────────────────────
        if graph_group == "Linear":
            cur_lt   = st.session_state.linear_type
            lt_label = _LT_REVERSE.get(cur_lt, "Mixed")

            _LT_ROW1 = ["Vertical", "Horizontal"]
            _LT_ROW2 = ["Proportional", "Non-Proportional", "Mixed"]

            def _on_lt_row1_change():
                st.session_state.linear_type = _LT_MAP[st.session_state._lt_row1]
                _regen(linear_type=st.session_state.linear_type)

            def _on_lt_row2_change():
                st.session_state.linear_type = _LT_MAP[st.session_state._lt_row2]
                _regen(linear_type=st.session_state.linear_type)

            st.markdown("**Line Type**")
            with st.container(key="lt_radio_group"):
                st.markdown("""<style>
div[data-testid="lt_radio_group"] [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
</style>""", unsafe_allow_html=True)
                st.radio(
                    "lt_row1", _LT_ROW1,
                    index=_LT_ROW1.index(lt_label) if lt_label in _LT_ROW1 else None,
                    horizontal=True,
                    label_visibility="collapsed",
                    key="_lt_row1",
                    on_change=_on_lt_row1_change,
                )
                st.radio(
                    "lt_row2", _LT_ROW2,
                    index=_LT_ROW2.index(lt_label) if lt_label in _LT_ROW2 else None,
                    horizontal=False,
                    label_visibility="collapsed",
                    key="_lt_row2",
                    on_change=_on_lt_row2_change,
                )

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

        # ── Smooth Curve: fn type → sub-types → New Graph ─────────────────────
        elif graph_group == "Smooth Curve":
            fn_label_sc  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            fn_choice_sc = st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_sc),
                key="fn_radio_smoothcurve",
                horizontal=True,
            )
            new_ft_sc = _FN_MAP[fn_choice_sc]
            if new_ft_sc != st.session_state.fn_type:
                st.session_state.fn_type = new_ft_sc
                _regen(fn_type=new_ft_sc)

            available_subtypes = _CURVE_SUBTYPES
            cur_cs   = st.session_state.curve_subtype
            cs_label = cur_cs if cur_cs in available_subtypes else "Mixed"
            cs_choice = st.radio(
                "Curve Type", available_subtypes,
                index=available_subtypes.index(cs_label),
                key="cs_radio",
            )
            new_cs = None if cs_choice == "Mixed" else cs_choice
            if new_cs != st.session_state.curve_subtype:
                st.session_state.curve_subtype = new_cs
                _regen(curve_subtype=new_cs)

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

        # ── Piecewise: sub-types → New Graph ───────────────────────────────────
        elif graph_group == "Piecewise":
            cur_ps    = st.session_state.piecewise_subtype
            ps_label  = cur_ps if cur_ps in _PIECEWISE_SUBTYPES else "Mixed"
            ps_choice = st.radio(
                "Piece Type", _PIECEWISE_SUBTYPES,
                index=_PIECEWISE_SUBTYPES.index(ps_label),
                key="ps_radio",
            )
            new_ps = None if ps_choice == "Mixed" else ps_choice
            if new_ps != st.session_state.piecewise_subtype:
                st.session_state.piecewise_subtype = new_ps
                _regen(piecewise_subtype=new_ps)

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

        # ── Scatter Plot ───────────────────────────────────────────────────────
        elif graph_group == "Scatter Plot":
            fn_label_s  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            fn_choice_s = st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_s),
                key="fn_radio_scatter",
                horizontal=True,
            )
            new_ft_s = _FN_MAP[fn_choice_s]
            if new_ft_s != st.session_state.fn_type:
                st.session_state.fn_type = new_ft_s
                _regen(fn_type=new_ft_s)

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

            st.divider()
            st.markdown("**Points**")
            scatter_text = st.text_input(
                "Coordinates",
                value=st.session_state.scatter_text,
                placeholder="(1,2), (-3,4), (0,-1)",
            )
            if scatter_text != st.session_state.scatter_text:
                st.session_state.scatter_text = scatter_text
            pts, err = (CoordinateValidator.parse(scatter_text)
                        if scatter_text.strip() else (None, None))
            if err:
                st.error(err)
            elif pts:
                st.session_state.params = {"points": pts}

        # ── Line Segment ───────────────────────────────────────────────────────
        elif graph_group == "Line Segment":
            fn_label_ls  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            fn_choice_ls = st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_ls),
                key="fn_radio_lineseg",
                horizontal=True,
            )
            new_ft_ls = _FN_MAP[fn_choice_ls]
            if new_ft_ls != st.session_state.fn_type:
                st.session_state.fn_type = new_ft_ls
                _regen(fn_type=new_ft_ls)

            if st.button("⟳ New Graph", use_container_width=True, key="new_lineseg"):
                _regen()

            st.divider()
            st.markdown("**Points**")
            # Build display text from current params
            _ls_p = st.session_state.params
            _ls_default = CoordinateValidator.format_points([
                (_ls_p.get("x0", -3.0), _ls_p.get("y0", -2.0)),
                (_ls_p.get("x1",  3.0), _ls_p.get("y1",  2.0)),
            ])
            ls_text = st.text_input(
                "Two endpoints",
                value=st.session_state.lineseg_text or _ls_default,
                placeholder="(-3, -2), (3, 2)",
            )
            if ls_text != st.session_state.lineseg_text:
                st.session_state.lineseg_text = ls_text
            ls_pts, ls_err = (CoordinateValidator.parse(ls_text)
                              if ls_text.strip() else (None, None))
            if ls_err:
                st.error(ls_err)
            elif ls_pts:
                if len(ls_pts) < 2:
                    st.error("Enter exactly 2 points.")
                else:
                    p0, p1 = ls_pts[0], ls_pts[1]
                    st.session_state.params = {
                        "x0": p0[0], "y0": p0[1],
                        "x1": p1[0], "y1": p1[1],
                    }

        # ── Mapping: fn type → shape → New Mapping ───────────────────────────
        elif graph_group == "Mapping":
            fn_label_m  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            fn_choice_m = st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_m),
                key="fn_radio_mapping",
                horizontal=True,
            )
            new_ft_m = _FN_MAP[fn_choice_m]
            if new_ft_m != st.session_state.fn_type:
                st.session_state.fn_type = new_ft_m
                _regen(fn_type=new_ft_m)

            cur_shape_key = _MAPPING_SHAPE_REVERSE.get(
                st.session_state.mapping_shape, "Mixed")
            shape_choice = st.radio(
                "Shape", _MAPPING_SHAPES,
                index=_MAPPING_SHAPES.index(cur_shape_key),
                key="mapping_shape_radio",
                horizontal=True,
            )
            new_shape = _MAPPING_SHAPE_MAP[shape_choice]
            if new_shape != st.session_state.mapping_shape:
                st.session_state.mapping_shape = new_shape
                if new_shape != "mixed" and "shape" in st.session_state.params:
                    st.session_state.params["shape"] = new_shape

            if st.button("⟳ New Mapping", use_container_width=True):
                _regen()

    # ── Options ───────────────────────────────────────────────────────────────
    _model    = st.session_state.model
    _category = st.session_state.category

    # Show Grid — hidden for Mapping and Random
    if _model != "Mapping" and _category != "Random":
        st.divider()
        st.markdown("**Options**")
        st.session_state.show_grid = st.checkbox(
            "Show Grid", value=st.session_state.show_grid)

        if _model != "Scatter Plot":
            prev_gs   = st.session_state.grid_style
            gs_choice = st.radio(
                "Style", ["Print", "Color"], horizontal=True,
                index=0 if prev_gs == "print" else 1,
            )
            new_gs = "print" if gs_choice == "Print" else "color"
            if new_gs != prev_gs:
                st.session_state.grid_style  = new_gs
                st.session_state.graph_color = "#000000" if new_gs == "print" else "#2563EB"

            if st.session_state.grid_style == "color":
                st.session_state.graph_color = st.color_picker(
                    "Line Color", value=st.session_state.graph_color)

            st.session_state.line_width = st.slider(
                "Line Weight", 0.5, 5.0,
                value=float(st.session_state.line_width), step=0.5)

    # Mapping options — X/Y label only (Shape is shown inline above New Mapping, hidden in Random)
    if _model == "Mapping" and _category != "Random":
        st.divider()
        st.markdown("**Options**")
        new_xy = st.checkbox("Show X / Y", value=st.session_state.show_xy_labels)
        if new_xy != st.session_state.show_xy_labels:
            st.session_state.show_xy_labels = new_xy
            if "show_labels" in st.session_state.params:
                st.session_state.params["show_labels"] = new_xy

    # Function type — Graphs category only, for "either" models (not handled inline above)
    if _category == "Graphs" and _model not in ("Mapping", "Scatter Plot", "Line Segment", "Smooth Curve"):
        support = _FN_SUPPORT.get(_model, "either")
        if support == "either":
            st.divider()
            st.markdown("**Function Type**")
            fn_label  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            fn_choice = st.radio(
                "fn_type_radio", _FN_LABELS, horizontal=True,
                index=_FN_LABELS.index(fn_label),
                label_visibility="collapsed",
            )
            new_ft = _FN_MAP[fn_choice]
            if new_ft != st.session_state.fn_type:
                st.session_state.fn_type = new_ft
                _regen(fn_type=new_ft)

    # ── Downloads & Batch Export ──────────────────────────────────────────────
    st.divider()

    # Render once, save to both PNG and SVG buffers
    _png_buf = BytesIO()
    _svg_buf = BytesIO()
    try:
        _dl_fig = _render_figure(
            st.session_state.model, st.session_state.params,
            line_width=st.session_state.line_width,
            graph_color=st.session_state.graph_color,
            show_grid=st.session_state.show_grid,
            grid_style=st.session_state.grid_style,
        )
        _dl_fig.savefig(_png_buf, format="png", dpi=200,
                        bbox_inches="tight", pad_inches=0.05,
                        facecolor="white")
        _dl_fig.savefig(_svg_buf, format="svg",
                        bbox_inches="tight", pad_inches=0.05,
                        facecolor="white")
        _dl_fig.clf()
    except Exception:
        pass

    _fname = st.session_state.model.lower().replace(" ", "_")
    st.download_button(
        "⬇ Download PNG",
        data=_png_buf.getvalue(),
        file_name=f"{_fname}.png",
        mime="image/png",
        use_container_width=True,
    )
    st.download_button(
        "⬇ Download SVG",
        data=_svg_buf.getvalue(),
        file_name=f"{_fname}.svg",
        mime="image/svg+xml",
        use_container_width=True,
    )

    with st.expander("Batch Export"):
        b_count = st.number_input(
            "Count", min_value=1, max_value=500,
            value=st.session_state.batch_count, step=1)
        st.session_state.batch_count = int(b_count)

        b_disp_choice = st.radio(
            "Display", ["Graph", "Mapping", "Mixed"],
            horizontal=True,
            index=["graph", "mapping", "mixed"].index(
                st.session_state.batch_display_type),
            key="batch_display_radio",
        )
        st.session_state.batch_display_type = b_disp_choice.lower()

        b_fn_choice = st.radio(
            "Type", ["Function", "Not a Function", "Mixed"],
            horizontal=True,
            index=["function", "not_function", "random"].index(
                st.session_state.batch_fn_type),
            key="batch_fn_radio",
        )
        st.session_state.batch_fn_type = _FN_MAP.get(b_fn_choice, "random")

        if st.button("Generate ZIP", use_container_width=True):
            with st.spinner(f"Generating {st.session_state.batch_count} graphs…"):
                st.session_state.batch_zip = _build_batch_zip(
                    st.session_state.batch_count,
                    st.session_state.batch_fn_type,
                    st.session_state.batch_display_type,
                )

        if st.session_state.batch_zip:
            st.download_button(
                "⬇ Download ZIP",
                data=st.session_state.batch_zip,
                file_name="batch_export.zip",
                mime="application/zip",
                use_container_width=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Main area — graph display
# ═══════════════════════════════════════════════════════════════════════════════

if not st.session_state.params:
    _regen()

model  = st.session_state.model
params = st.session_state.params

try:
    fig = _render_figure(
        model, params,
        line_width=st.session_state.line_width,
        graph_color=st.session_state.graph_color,
        show_grid=st.session_state.show_grid,
        grid_style=st.session_state.grid_style,
    )

    st.pyplot(fig, width="stretch")
    fig.clf()

except Exception as exc:
    st.error(f"Draw error: {exc}")
