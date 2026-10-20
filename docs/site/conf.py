"""Sphinx configuration for the FlahaX documentation site."""
from flahax import __version__

project = "FlahaX"
release = __version__
version = __version__

extensions = ["myst_parser"]
source_suffix = {".md": "markdown"}

html_theme = "furo"

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

exclude_patterns = ["_build"]
