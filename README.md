# Function Forge

Interactive graph builder for math teachers, built with Streamlit and Matplotlib.
Part of the **Forge** family alongside Fraction Forge and Geometry Forge.

## Running

```bash
pip install -r requirements.txt
python run.py
```

Or directly with Streamlit:

```bash
streamlit run streamlit_app.py
```

Or as a package:

```bash
python -m function_forge
```

Then open **http://localhost:8501** in your browser.

## Project Structure

```
Function Forge/
├── run.py                         ← Launch the app
├── streamlit_app.py               ← Streamlit web UI
├── requirements.txt               ← Python dependencies
└── function_forge/                ← The package
    ├── __init__.py                ← Package setup (logging, public API)
    ├── __main__.py                ← Enables `python -m function_forge`
    ├── models.py                  ← Data types, constants, graph model configs
    ├── validators.py              ← Coordinate input validation logic
    └── drawers.py                 ← All graph drawer classes + registry
```

## Which File Do I Edit?

### I want to change a constant, default value, or color
**→ `models.py`**

`AppConstants` has all the magic numbers: axis range, default line width, graph colors, and canvas settings. `GraphConfig` and `GraphConfigProvider` are here too, along with `DrawingContext` — the data class passed to every drawer on each redraw.

### I want to add a new graph type or fix how an existing one draws
**→ `drawers.py`**

Every graph type has its own drawer class (e.g. `LinearDrawer`, `MappingDrawer`). To add a new type, create a class that inherits from `GraphDrawer`, decorate it with `@GraphRegistry.register("My Graph")`, and implement the `draw()` method. You'll also need to:
- Add a `GraphConfig` entry in `models.py` inside `_build_graph_configs()`
- Add the graph name to the `MODEL_DATA` dict in `streamlit_app.py`
- Add an entry to `_RANDOM_DRAWERS` in `drawers.py` and implement `random_params()` on the class if random generation is desired

### I want to change input validation (e.g. coordinate parsing)
**→ `validators.py`**

`CoordinateValidator` parses coordinate strings like `(1, 2), (-3, 4)` and returns a list of `(float, float)` tuples or an error message. It also clamps out-of-range values to the axis bounds.

### I want to change the UI layout, controls, or sidebar
**→ `streamlit_app.py`**

This is the full Streamlit app. All session state, sidebar controls, graph rendering, and download buttons live here. The `MODEL_DATA` dict at the top is where you register which graph types appear under which category.

## Current Graph Types

| Category | Graph Type | Description |
|----------|------------|-------------|
| Graphs | Linear | Straight line — slope/intercept, or Vertical, Horizontal, Proportional, Non-Proportional |
| Graphs | Smooth Curve | Sinusoidal or polynomial smooth curve |
| Graphs | Piecewise | Multiple line segments with open/closed endpoints at each break |
| Graphs | Step Function | Horizontal step segments with open/closed dots at discontinuities |
| Graphs | Parametric | Closed parametric curve — a relation, not a function |
| Graphs | Scatter Plot | Discrete plotted points from a coordinate list |
| Graphs | Reciprocal | Hyperbola — y = k/(x−h)+v with asymptotes |
| Mappings | Mapping | Two-oval mapping diagram with arrows from domain (X) to range (Y) |

## Adding a New Graph Type — Checklist

1. **`drawers.py`** — create a class inheriting `GraphDrawer`, decorate with `@GraphRegistry.register("Name")`, implement `draw()`, and add a `random_params()` classmethod
2. **`models.py`** — add a `GraphConfig` entry inside `_build_graph_configs()`
3. **`streamlit_app.py`** — add the graph name to the relevant category list in `MODEL_DATA`
4. **`drawers.py`** — add an entry to `_RANDOM_DRAWERS` so the Random button can reach it

## Features

- **Print / Color mode toggle** — print mode uses a bold dark grid and black line; color mode uses a lighter grid and a color picker for the line
- **Vertical Line Test overlay** — toggle a dashed red VLT indicator line on any graph
- **Open / Closed dot style** — switch between filled and hollow endpoint dots for piecewise and step graphs
- **Linear line type selector** — lock generation to Vertical, Horizontal, Proportional, or Non-Proportional lines (or leave on Any for fully random)
- **Show/Hide X·Y labels** — toggle domain/range labels on mapping diagrams
- **Line weight slider** — adjust stroke weight to match your worksheet formatting
- **⟳ New Graph** — generate a new random graph of the current type with one click
- **Random mode** — generate a random graph from any type, graphs only, or mappings only
- **Function type filter** — lock generation to Function, Not a Function, or Either
- **Download PNG** — export the current graph at 200 dpi for crisp worksheet images
- **Batch Export** — generate up to 500 random graphs and download as a ZIP of PNGs

## Dependencies

- Python 3.10+
- `streamlit >= 1.35.0`
- `matplotlib >= 3.8.0`
- `numpy >= 1.26.0`

## Design Notes

The coordinate grid is drawn manually as explicit line segments clipped to [−5, 5] rather than using matplotlib's built-in grid, giving precise control over line weight and color in both print and color modes. Chevron arrowheads on axis ends and line ends are also drawn manually so their style matches exactly across graph types.

All graph rendering logic (`drawers.py`, `models.py`, `validators.py`) is UI-framework-agnostic — it only depends on matplotlib and numpy, making it straightforward to swap the frontend if needed.
