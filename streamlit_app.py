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

import pathlib as _pathlib

import streamlit as st
import streamlit.components.v1 as _components
from matplotlib.figure import Figure
from PIL import Image as _PILImage

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

APP_TITLE       = "Function Forge"
ICON_HEIGHT     = 68
TITLE_FONT_SIZE = 40

_icon_path = str(_pathlib.Path(__file__).parent / "assets" / "icon.png")
try:
    _favicon = _PILImage.open(_icon_path)
    _favicon.load()
except FileNotFoundError:
    _favicon = "📐"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar style ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Bebas Neue font (industrial all-caps) ─────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');

/* ── Compact sidebar widget spacing ───────────────────────────────────── */
section[data-testid="stSidebar"] .stElementContainer {
    margin-bottom: -0.4rem;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stCheckbox,
section[data-testid="stSidebar"] .stSlider,
section[data-testid="stSidebar"] .stSelectbox,
section[data-testid="stSidebar"] .stRadio,
section[data-testid="stSidebar"] .stButton,
section[data-testid="stSidebar"] .stDownloadButton,
section[data-testid="stSidebar"] .stNumberInput {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {
    gap: 0.25rem;
}
/* ── Tighten gap between individual radio options ──────────────────────── */
section[data-testid="stSidebar"] .stRadio > div {
    gap: 0.05rem !important;
}
/* ── Pull row2 of the Line Type split-radio up to match within-row spacing  */
.st-key-_lt_row2 {
    margin-top: -0.9rem !important;
}
</style>
""", unsafe_allow_html=True)

_components.html("""<script>
(function(){
  var css=[
    '[data-testid="stSidebarContent"]{padding-top:0!important}',
    '[data-testid="stSidebar"] hr{margin-top:0!important;margin-bottom:0!important;padding-top:0!important;padding-bottom:0!important}',
    '[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(hr){margin:0!important;padding:0!important;min-height:0!important}',
    'section[data-testid="stSidebar"]{z-index:10!important}',
  ].join('');
  function fix(){
    try{
      var doc=window.parent.document;
      var s=doc.getElementById('sidebar-style-fix');
      if(s&&s===doc.head.lastElementChild)return;
      if(s)s.remove();
      s=doc.createElement('style');s.id='sidebar-style-fix';s.textContent=css;
      doc.head.appendChild(s);
    }catch(e){}
  }
  fix();
  try{new MutationObserver(fix).observe(window.parent.document.head,{childList:true});}catch(e){}
})();
</script>""", height=0)


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
    try:
        import base64 as _b64
        with open(_icon_path, 'rb') as _f:
            _icon_b64 = _b64.b64encode(_f.read()).decode()
        st.markdown(
            f'<div style="display:flex;align-items:flex-end;gap:10px;'
            f'padding-bottom:1.5rem;margin-top:-2rem;">'
            f'<img src="data:image/png;base64,{_icon_b64}" '
            f'style="display:block;height:{ICON_HEIGHT}px;width:auto;flex-shrink:0;"/>'
            f'<svg width="100%" style="display:block;flex:1;min-width:0;overflow:visible;" '
            f'height="{ICON_HEIGHT - 24}">'
            f'<text x="0" y="{ICON_HEIGHT - 28}" textLength="100%" '
            f'lengthAdjust="spacingAndGlyphs" font-size="{TITLE_FONT_SIZE}" '
            f"font-family=\"'Bebas Neue',sans-serif\" fill=\"currentColor\">"
            f'{APP_TITLE}'
            f'</text></svg>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        st.markdown(
            f'<svg width="100%" height="{ICON_HEIGHT - 24}" '
            f'style="display:block;overflow:visible;padding-bottom:1.5rem;">'
            f'<text x="0" y="{ICON_HEIGHT - 28}" textLength="100%" '
            f'lengthAdjust="spacingAndGlyphs" font-size="{TITLE_FONT_SIZE}" '
            f"font-family=\"'Bebas Neue',sans-serif\" fill=\"currentColor\">"
            f'{APP_TITLE}'
            f'</text></svg>',
            unsafe_allow_html=True,
        )
    st.divider()

    # ── Category ──────────────────────────────────────────────────────────────
    all_cats = list(MODEL_DATA.keys()) + ["Random"]

    def _on_category_change():
        cat = st.session_state._sel_category
        st.session_state.category          = cat
        st.session_state.linear_type       = None
        st.session_state.curve_subtype     = None
        st.session_state.piecewise_subtype = None
        if cat != "Random":
            first = MODEL_DATA.get(cat, ["Linear"])[0]
            st.session_state.graph_group = first
            _regen(graph_group=first,
                   linear_type=None, curve_subtype=None, piecewise_subtype=None)

    category = st.selectbox("Category", all_cats,
                            index=all_cats.index(st.session_state.category)
                                  if st.session_state.category in all_cats else 0,
                            key="_sel_category",
                            on_change=_on_category_change)

    # ── Random category ───────────────────────────────────────────────────────
    if category == "Random":
        # Function type — horizontal row
        def _on_fn_random(): st.session_state.fn_type = _FN_MAP[st.session_state.fn_radio_random]
        fn_label_r  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
        st.radio(
            "Type", _FN_LABELS,
            index=_FN_LABELS.index(fn_label_r),
            key="fn_radio_random",
            horizontal=True,
            on_change=_on_fn_random,
        )

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
            st.divider()
        else:
            def _on_graph_group_change():
                gg = st.session_state._sel_graph_group
                st.session_state.graph_group       = gg
                st.session_state.linear_type       = None
                st.session_state.curve_subtype     = None
                st.session_state.piecewise_subtype = None
                _regen(graph_group=gg,
                       linear_type=None, curve_subtype=None, piecewise_subtype=None)

            group_idx   = models.index(prev_group) if prev_group in models else 0
            graph_group = st.selectbox("Graph Type", models, index=group_idx,
                                       key="_sel_graph_group",
                                       on_change=_on_graph_group_change)

        st.divider()

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
            def _on_fn_sc():
                st.session_state.fn_type = _FN_MAP[st.session_state.fn_radio_smoothcurve]
                _regen(fn_type=st.session_state.fn_type)
            st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_sc),
                key="fn_radio_smoothcurve",
                horizontal=True,
                on_change=_on_fn_sc,
            )

            available_subtypes = _CURVE_SUBTYPES
            cur_cs   = st.session_state.curve_subtype
            cs_label = cur_cs if cur_cs in available_subtypes else "Mixed"
            def _on_cs():
                v = st.session_state.cs_radio
                st.session_state.curve_subtype = None if v == "Mixed" else v
                _regen(curve_subtype=st.session_state.curve_subtype)
            st.radio(
                "Curve Type", available_subtypes,
                index=available_subtypes.index(cs_label),
                key="cs_radio",
                on_change=_on_cs,
            )

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

        # ── Piecewise: sub-types → New Graph ───────────────────────────────────
        elif graph_group == "Piecewise":
            cur_ps    = st.session_state.piecewise_subtype
            ps_label  = cur_ps if cur_ps in _PIECEWISE_SUBTYPES else "Mixed"
            def _on_ps():
                v = st.session_state.ps_radio
                st.session_state.piecewise_subtype = None if v == "Mixed" else v
                _regen(piecewise_subtype=st.session_state.piecewise_subtype)
            st.radio(
                "Piece Type", _PIECEWISE_SUBTYPES,
                index=_PIECEWISE_SUBTYPES.index(ps_label),
                key="ps_radio",
                on_change=_on_ps,
            )

            if st.button("⟳ New Graph", use_container_width=True):
                _regen()

        # ── Scatter Plot ───────────────────────────────────────────────────────
        elif graph_group == "Scatter Plot":
            fn_label_s  = _FN_REVERSE.get(st.session_state.fn_type, "Mixed")
            def _on_fn_s():
                st.session_state.fn_type = _FN_MAP[st.session_state.fn_radio_scatter]
                _regen(fn_type=st.session_state.fn_type)
            st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_s),
                key="fn_radio_scatter",
                horizontal=True,
                on_change=_on_fn_s,
            )

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
            def _on_fn_ls():
                st.session_state.fn_type = _FN_MAP[st.session_state.fn_radio_lineseg]
                _regen(fn_type=st.session_state.fn_type)
            st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_ls),
                key="fn_radio_lineseg",
                horizontal=True,
                on_change=_on_fn_ls,
            )

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
            def _on_fn_m():
                st.session_state.fn_type = _FN_MAP[st.session_state.fn_radio_mapping]
                _regen(fn_type=st.session_state.fn_type)
            st.radio(
                "Function Type", _FN_LABELS,
                index=_FN_LABELS.index(fn_label_m),
                key="fn_radio_mapping",
                horizontal=True,
                on_change=_on_fn_m,
            )

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

    # ── Math Forges suite ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
<div style="text-align:center;line-height:1.8;">
  <span style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;display:block;">Algebra Forge</span>
  <span style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;display:block;">Data Forge</span>
  <span style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;display:block;">Fraction Forge</span>
  <span style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;display:block;opacity:0.4;">Function Forge</span>
  <a href="https://geometry-forge.streamlit.app/" target="_blank"
     style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;display:block;
            color:inherit;text-decoration:none;">Geometry Forge</a>
</div>
""", unsafe_allow_html=True)

    # ── Ko-fi widget — injected into parent page so the floating button escapes the iframe ──
    _components.html("""
<script>
(function(){
  var doc = window.parent.document;
  if(doc.getElementById('kofi-overlay-script')) return;
  var s = doc.createElement('script');
  s.id = 'kofi-overlay-script';
  s.src = 'https://storage.ko-fi.com/cdn/scripts/overlay-widget.js';
  s.onload = function(){
    window.parent.kofiWidgetOverlay.draw('amgirouard', {
      'type': 'floating-chat',
      'floating-chat.donateButton.text': 'Support Me',
      'floating-chat.donateButton.background-color': '#323842',
      'floating-chat.donateButton.text-color': '#fff'
    });
  };
  doc.head.appendChild(s);
})();
</script>
""", height=0)


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

    _pad, _main, _ = st.columns([1, 2, 1])
    with _main:
        st.pyplot(fig, use_container_width=True)
    fig.clf()

except Exception as exc:
    st.error(f"Draw error: {exc}")
