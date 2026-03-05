"""Shared prompt constants used by all template modules."""

FRAMING_RULES = (
    "\nFRAMING — CRITICAL:\n"
    "- Place a 1-pixel-wide MAGENTA (#FF00FF) vertical line between each sprite/frame "
    "as a separator\n"
    "- Each sprite occupies an equal-width cell in the horizontal row\n"
    "- The magenta separator must span the FULL height of the image\n"
    "- Do NOT place magenta lines at the left or right edges — only BETWEEN sprites\n"
    "- Do NOT use magenta (#FF00FF) anywhere else in the artwork\n"
    "- The background behind each sprite must be fully transparent"
)
