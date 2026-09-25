"""FlahaX: choose salt weights that minimize formulation Δ%."""

from .composition import InputError
from .engine import gap_for, load_library, recommend, solve_weights

__all__ = ["InputError", "gap_for", "load_library", "recommend", "solve_weights"]
__version__ = "0.2.0"
