"""Function Forge — Interactive graph builder for math teachers."""

from __future__ import annotations

import logging
import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

__all__ = ["main"]


def main() -> None:
    from .app import main as _main
    _main()
