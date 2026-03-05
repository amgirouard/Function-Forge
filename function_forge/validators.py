"""validators.py — Input validation for Function Forge."""

from __future__ import annotations

import re


class CoordinateValidator:
    """Validates coordinate list strings like '(1,2), (-3,4), (0,5)'."""

    # Matches optional sign, integer or decimal
    _NUM = r"-?\s*\d+(?:\.\d+)?"
    # Matches (x, y) with flexible spacing and optional outer parens
    _PAIR = re.compile(
        rf"\(\s*({_NUM})\s*,\s*({_NUM})\s*\)"
    )

    AXIS_MIN = -5
    AXIS_MAX =  5

    @classmethod
    def parse(cls, text: str) -> tuple[list[tuple[float, float]] | None, str | None]:
        """Parse a coordinate string.

        Returns (points, None) on success, (None, error_message) on failure.
        Points that fall outside [-5, 5] are silently clamped.
        """
        if not text or not text.strip():
            return None, "No coordinates entered."

        pairs = cls._PAIR.findall(text)
        if not pairs:
            return None, "No valid (x, y) pairs found.\nUse format: (1, 2), (-3, 4)"

        points: list[tuple[float, float]] = []
        for x_str, y_str in pairs:
            try:
                x = float(x_str.replace(" ", ""))
                y = float(y_str.replace(" ", ""))
            except ValueError:
                return None, f"Invalid number: ({x_str}, {y_str})"
            # Clamp to axis range
            x = max(cls.AXIS_MIN, min(cls.AXIS_MAX, x))
            y = max(cls.AXIS_MIN, min(cls.AXIS_MAX, y))
            points.append((x, y))

        return points, None

    @classmethod
    def format_points(cls, points: list[tuple[float, float]]) -> str:
        """Format a list of points back to a readable string."""
        parts = []
        for x, y in points:
            xs = int(x) if x == int(x) else x
            ys = int(y) if y == int(y) else y
            parts.append(f"({xs}, {ys})")
        return ", ".join(parts)
