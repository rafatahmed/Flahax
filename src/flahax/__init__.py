"""FlahaX: choose salt weights that minimize formulation Δ%."""

from .engine import LIBRARY, gap_for, load_library, recommend, solve_weights

__all__ = ["LIBRARY", "gap_for", "load_library", "recommend", "solve_weights"]
__version__ = "0.1.0"
