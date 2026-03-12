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
import zipfile
from io import BytesIO

# Ensure the project root is on sys.path so absolute imports work
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import streamlit as st
from matplotlib.figure import Figure

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

MODEL_DATA: dict[str, list[str]] = {
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
}

_LT_OPTIONS  = ["Any", "Vertical", "Horizontal", "Proportional", "Non-Prop."]
_LT_MAP: dict[str, str | None] = {
    "Any":          None,
    "Vertical":     "vertical",
    "Horizontal":   "horizontal",
    "Proportional": "proportional",
    "Non-Prop.":    "non_proportional",
}
_LT_REVERSE: dict[str | None, str] = {v: k for k, v in _LT_MAP.items()}

_FN_LABELS  = ["Function", "Not a Fn", "Either"]
_FN_MAP     = {"Function": "function", "Not a Fn": "not_function", "Either": "random"}
_FN_REVERSE = {v: k for k, v in _FN_MAP.items()}


# ═══════════════════════════════════════════════════════════════════════════════
# Page config (must be first Streamlit call)
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Function Forge",
    page_icon="📐",
    layout="wide",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Session-state initialisation
# ═══════════════════════════════════════════════════════════════════════════════

def _init_state() -> None:
    defaults: dict = {
        "category":      "Graphs",
        "model":         "Linear",
        "params":        {},
        "fn_type":       "random",
        "linear_type":   None,
        "show_grid":     True,
        "show_vlt":      False,
        "dot_style":     "closed",
        "grid_style":    "print",
        "graph_color":   "#000000",
        "line_width":    4.0,
        "mapping_shape": "oval",
        "show_xy_labels": True,
        "scatter_text":  "",
        # batch export sticky settings
        "batch_fn_type":      "random",
        "batch_display_type": "graph",
        "batch_count":        10,
        "batch_zip":          None,   # bytes | None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _regen(
    model:       str | None = None,
    linear_type: str | None = ...,   # type: ignore[assignment]  sentinel
    fn_type:     str | None = None,
) -> None:
    """Generate new random params and store in session_state.params."""
    m  = model    or st.session_state.model
    ft = fn_type  or st.session_state.fn_type
    lt = st.session_state.linear_type if linear_type is ... else linear_type  # type: ignore[comparison-overlap]
    st.session_state.params = get_random_params(
        m, fn_type=ft,
        linear_type=lt if m == "Linear" else None,
    )
    # Keep scatter text in sync
    if m == "Scatter Plot":
        pts = st.session_state.params.get("points", [])
        st.session_state.scatter_text = CoordinateValidator.format_points(pts)


def _render_figure(model: str, params: dict, *, line_width: float,
                   graph_color: str, show_grid: bool, dot_style: str,
                   show_vlt: bool, grid_style: str) -> Figure:
    """Create and return a rendered matplotlib Figure."""
    fig = Figure(figsize=(7, 5.25))
    fig.patch.set_facecolor("white")
    _mx = AppConstants.CANVAS_PAPER_MARGIN
    ax  = fig.add_axes([_mx, _mx, 1 - 2 * _mx, 1 - 2 * _mx])

    ctx = DrawingContext(
        ax=ax,
        line_width=line_width,
        graph_color=graph_color,
        show_grid=show_grid,
        dot_style=dot_style,
        show_vlt=show_vlt,
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
        pool = list(MODEL_DATA["Graphs"])
    elif display_type == "mapping":
        pool = ["Mapping"]
    else:
        pool = [m for ms in MODEL_DATA.values() for m in ms]

    # Filter by fn_type capability
    capable = _FN_CAPABLE.get(fn_type, list(_FN_CAPABLE["random"]))
    filtered = [m for m in pool if m in capable]
    if not filtered:
        filtered = pool

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(count):
            model_name = random.choice(filtered)
            params     = get_random_params(model_name, fn_type=fn_type)
            fig = _render_figure(
                model_name, params,
                line_width=4.0, graph_color="#000000",
                show_grid=True, dot_style="closed",
                show_vlt=False, grid_style="print",
            )
            img = BytesIO()
            fig.savefig(img, format="png", dpi=200,
                        bbox_inches="tight", pad_inches=0.05,
                        facecolor="white")
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
        st.session_state.category    = category
        st.session_state.linear_type = None
        # Auto-pick first model in new category (or keep for Random)
        if category != "Random":
            first = MODEL_DATA.get(category, ["Linear"])[0]
            st.session_state.model = first
            _regen(model=first)

    # ── Random category controls ──────────────────────────────────────────────
    if category == "Random":
        fn_label_r = _FN_REVERSE.get(st.session_state.fn_type, "Either")
        fn_choice_r = st.radio(
            "Type", _FN_LABELS, horizontal=True,
            index=_FN_LABELS.index(fn_label_r),
            key="fn_radio_random",
        )
        st.session_state.fn_type = _FN_MAP[fn_choice_r]

        col1, col2, col3 = st.columns(3)
        if col1.button("⟳ Random", use_container_width=True):
            all_models = [m for ms in MODEL_DATA.values() for m in ms]
            capable    = _FN_CAPABLE.get(st.session_state.fn_type,
                                          list(_FN_CAPABLE["random"]))
            pool = [m for m in all_models if m in capable] or all_models
            m = random.choice(pool)
            st.session_state.model = m
            _regen(model=m)
        if col2.button("⟳ Graph", use_container_width=True):
            capable = _FN_CAPABLE.get(st.session_state.fn_type,
                                       list(_FN_CAPABLE["random"]))
            pool = [m for m in MODEL_DATA["Graphs"] if m in capable] \
                   or MODEL_DATA["Graphs"]
            m = random.choice(pool)
            st.session_state.model = m
            _regen(model=m)
        if col3.button("⟳ Mapping", use_container_width=True):
            st.session_state.model = "Mapping"
            _regen(model="Mapping")

    # ── Normal category: model selector + New Graph ───────────────────────────
    else:
        models   = MODEL_DATA.get(category, [])
        prev_mdl = st.session_state.model
        mdl_idx  = models.index(prev_mdl) if prev_mdl in models else 0
        model    = st.selectbox("Graph Type", models, index=mdl_idx)

        if model != prev_mdl:
            st.session_state.model       = model
            st.session_state.linear_type = None
            _regen(model=model)

        if st.button("⟳ New Graph", use_container_width=True):
            _regen()

        # ── Linear line-type selector ─────────────────────────────────────────
        if model == "Linear":
            st.markdown("**Line Type**")
            cur_lt    = st.session_state.linear_type
            lt_label  = _LT_REVERSE.get(cur_lt, "Any")
            lt_choice = st.radio(
                "line_type_radio", _LT_OPTIONS,
                index=_LT_OPTIONS.index(lt_label),
                horizontal=True,
                label_visibility="collapsed",
            )
            new_lt = _LT_MAP[lt_choice]
            if new_lt != st.session_state.linear_type:
                st.session_state.linear_type = new_lt
                _regen(linear_type=new_lt)

    # ── Common options ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Options**")

    _model = st.session_state.model

    st.session_state.show_grid = st.checkbox(
        "Show Grid", value=st.session_state.show_grid)

    if _model != "Mapping":
        st.session_state.show_vlt = st.checkbox(
            "Show VLT", value=st.session_state.show_vlt,
            help="Overlay a Vertical Line Test indicator")

    # Dot style
    if _model != "Mapping":
        dot_choice = st.radio(
            "Endpoints", ["● Closed", "○ Open"], horizontal=True,
            index=0 if st.session_state.dot_style == "closed" else 1,
        )
        st.session_state.dot_style = "closed" if "Closed" in dot_choice else "open"

    # Grid style (print vs colour)
    if _model != "Mapping":
        prev_gs  = st.session_state.grid_style
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

    # Mapping-specific options
    if _model == "Mapping":
        shape_choice = st.radio(
            "Shape", ["Oval", "Rectangle"], horizontal=True,
            index=0 if st.session_state.mapping_shape == "oval" else 1,
        )
        new_shape = shape_choice.lower()
        if new_shape != st.session_state.mapping_shape:
            st.session_state.mapping_shape = new_shape
            if "shape" in st.session_state.params:
                st.session_state.params["shape"] = new_shape

        new_xy = st.checkbox("Show X / Y", value=st.session_state.show_xy_labels)
        if new_xy != st.session_state.show_xy_labels:
            st.session_state.show_xy_labels = new_xy
            if "show_labels" in st.session_state.params:
                st.session_state.params["show_labels"] = new_xy

    # Function type (only for "either" models)
    support = _FN_SUPPORT.get(_model, "either")
    if support == "either":
        st.divider()
        st.markdown("**Function Type**")
        fn_label = _FN_REVERSE.get(st.session_state.fn_type, "Either")
        fn_choice = st.radio(
            "fn_type_radio", _FN_LABELS, horizontal=True,
            index=_FN_LABELS.index(fn_label),
            label_visibility="collapsed",
        )
        new_ft = _FN_MAP[fn_choice]
        if new_ft != st.session_state.fn_type:
            st.session_state.fn_type = new_ft
            _regen(fn_type=new_ft)

    # Scatter Plot: coordinate entry
    if _model == "Scatter Plot":
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

        if st.button("⟳ Randomize Points", use_container_width=True):
            _regen()

    # ── Batch Export ─────────────────────────────────────────────────────────
    st.divider()
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
            "Type", ["Function", "Not a Fn", "Mixed"],
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

# Ensure params exist before rendering
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
        dot_style=st.session_state.dot_style,
        show_vlt=st.session_state.show_vlt if model != "Mapping" else False,
        grid_style=st.session_state.grid_style,
    )

    st.pyplot(fig, use_container_width=True)

    # Download current graph as PNG
    png_buf = BytesIO()
    fig.savefig(png_buf, format="png", dpi=200,
                bbox_inches="tight", pad_inches=0.05,
                facecolor="white")
    st.download_button(
        "⬇ Download PNG",
        data=png_buf.getvalue(),
        file_name=f"{model.lower().replace(' ', '_')}.png",
        mime="image/png",
    )

except Exception as exc:
    st.error(f"Draw error: {exc}")
