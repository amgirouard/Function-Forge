# Function Forge

Interactive graph builder for math teachers, built with Tkinter and Matplotlib.  
Part of the **Forge** family alongside Fraction Forge and Geometry Forge.

## Running

```bash
python run.py
```

Or as a package:

```bash
python -m function_forge
```

## Project Structure
```
Function Forge/
├── run.py                         ← Launch the app
└── function_forge/                ← The package
    ├── __init__.py                ← Package setup (logging, public API)
    ├── __main__.py                ← Enables `python -m function_forge`
    ├── models.py                  ← Data types, constants, graph model configs
    ├── validators.py              ← Coordinate input validation logic
    ├── drawers.py                 ← All graph drawer classes + registry
    ├── forge_widgets.py           ← Shared styled UI widgets (buttons, entries, sliders, etc.)
    └── app.py                     ← Main application class (FunctionApp)
```

## Which File Do I Edit?

### I want to change a constant, default value, or color
**→ `models.py`**

`AppConstants` has all the magic numbers: axis range, default line width, graph colors, font sizes, canvas settings, and UI scaling. `GraphConfig` and `GraphConfigProvider` are here too, along with `DrawingContext` — the data class passed to every drawer on each redraw.

### I want to add a new graph type or fix how an existing one draws
**→ `drawers.py`**

Every graph type has its own drawer class (e.g. `LinearDrawer`, `MappingDrawer`). To add a new type, create a class that inherits from `GraphDrawer`, decorate it with `@GraphRegistry.register("My Graph")`, and implement the `draw()` method. You'll also need to:
- Add a `GraphConfig` entry in `models.py` inside `_build_graph_configs()`
- Add the graph name to the appropriate category list in `app.py`
- Add an entry to `_RANDOM_DRAWERS` in `drawers.py` and implement `random_params()` on the class if random generation is desired

### I want to change input validation (e.g. coordinate parsing)
**→ `validators.py`**

`CoordinateValidator` parses coordinate strings like `(1, 2), (-3, 4)` and returns a list of `(float, float)` tuples or an error message. It also clamps out-of-range values to the axis bounds.

### I want to change the UI layout, menus, buttons, or keyboard shortcuts
**→ `app.py`**

`FunctionApp` owns the full Tkinter layout: the category/graph selectors, controls row, options panel, toolbar, canvas setup, save/copy, and keyboard bindings. The `model_data` dict in `app.py` is also where you register which graph types appear under which category.

### I want to change the look of buttons, entries, dropdowns, sliders, or checkboxes
**→ `forge_widgets.py`**

All Canvas-drawn UI primitives live here and are shared across the Forge app family. The full widget catalog:

| Class | Replaces | Notes |
|---|---|---|
| `_StyledButton` | `tk.Button` | Rounded, drop-shadow, hover/active/disabled states |
| `_StyledEntry` | `tk.Entry` | Rounded border, focus ring, same `.get()/.insert()/.delete()` API |
| `_StyledStepper` | `tk.Spinbox` | `[− value +]` in one unified Canvas rect |
| `_StyledCombobox` | `ttk.Combobox` | Custom popup, fires `<<ComboboxSelected>>` |
| `_ColorSwatchButton` | — | `_StyledButton` variant with a solid color fill and selection dot |
| `_StyledSlider` | `ttk.Scale` | iOS-style thumb, optional center tick, `.get()/.set()/variable=` |
| `_StyledCheckbox` | `tk.Checkbutton` | Rounded square, macOS-style checkmark, `.get()/.set()/variable=` |

`BTN_H` (default `20`) is a single constant that controls the height of every widget at once. The `_ForgeTheme` dataclass is the single source of truth for all colors and radii — pass a custom instance to any widget to override the theme.

This file has **zero app-specific dependencies** (no imports from `models`, `drawers`, etc.) so it can be dropped into any Forge package as-is.

## Current Graph Types

| Category | Graph Type | Description |
|----------|------------|-------------|
| Graphs | Linear | Straight line — configurable slope and y-intercept over [−5, 5] |
| Graphs | Smooth Curve | Cubic bezier-style curve through random control points |
| Graphs | Piecewise | Multiple line segments with open/closed endpoints at each break |
| Graphs | Step Function | Horizontal step segments with open/closed dots at discontinuities |
| Graphs | Parametric | Closed parametric curve — a relation, not a function |
| Graphs | Scatter Plot | Discrete plotted points from a coordinate list |
| Mappings | Mapping | Two-oval mapping diagram with arrows from domain (X) to range (Y) |

## Adding a New Graph Type — Checklist

1. **`drawers.py`** — create a class inheriting `GraphDrawer`, decorate with `@GraphRegistry.register("Name")`, implement `draw()`, and add a `random_params()` classmethod
2. **`models.py`** — add a `GraphConfig` entry inside `_build_graph_configs()`
3. **`app.py`** — add the graph name to the relevant category list in `model_data`
4. **`drawers.py`** — add an entry to `_RANDOM_DRAWERS` so the Random button can reach it

## Features

- **Print / Color mode toggle** — print mode uses a bold dark grid and black line; color mode uses a lighter grid and lets you pick a line color
- **6 graph colors** — pick from blue, red, green, orange, purple, teal (color mode only)
- **Vertical Line Test overlay** — toggle a dashed red VLT indicator line on any graph
- **Open / Closed dot style** — switch between filled and hollow endpoint dots for piecewise and step graphs
- **Show/Hide X·Y labels** — toggle domain/range labels on mapping diagrams
- **Line weight slider** — adjust stroke weight to match your worksheet formatting
- **⟳ Random** — generate a random graph of any type in the current category with one click
- **Re-randomize** — generate new random parameters for the current graph type
- **Save as PNG / SVG** — export at 200 dpi for crisp worksheet images
- **Copy to clipboard** — paste directly into documents (macOS, Windows, and Linux supported)

## Dependencies

- Python 3.10+
- `tkinter` (usually bundled with Python)
- `matplotlib`
- `numpy`

## Design Notes

Function Forge mirrors Fraction Forge's architecture and visual design:
- Same gray toolbar, white canvas with black border, 4:3 aspect ratio
- Same Category → Graph Type dropdown pattern
- Same Font/Weight controls, Save/Copy in top bar, shortcut bar at bottom
- Same `GraphDrawer`/`GraphRegistry` pattern (parallel to `ModelDrawer`/`ModelRegistry`)
- Same `AppConstants` structure with scaling support
- Same file organization (`models.py`, `drawers.py`, `validators.py`, `app.py`)
- Same `forge_widgets.py` for all styled UI primitives

The coordinate grid is drawn manually as explicit line segments clipped to [−5, 5] rather than using matplotlib's built-in grid, giving precise control over line weight and color in both print and color modes. Chevron arrowheads on axis ends and line ends are also drawn manually so their style matches exactly across graph types.
