"""Sphinx configuration for the FlahaX documentation site."""
import os

from flahax import __version__

project = "FlahaX"
release = __version__
version = __version__

extensions = ["myst_parser"]
source_suffix = {".md": "markdown"}

html_theme = "furo"
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

exclude_patterns = ["_build"]


def _rewrite_included_links(app, relative_path, parent_docname, content):
    """Point the package's own cross-links at the pages that include them.

    USER_GUIDE.md and API_REFERENCE.md ship inside the wheel and link each
    other by bare file name; on the site those files are the manual and the
    reference pages, so the links are rewritten in memory at include time.
    """
    if relative_path.name == "USER_GUIDE.md":
        content[0] = content[0].replace("](API_REFERENCE.md)", "](../api/reference.md)")
    elif relative_path.name == "API_REFERENCE.md":
        content[0] = content[0].replace("](USER_GUIDE.md)", "](../guide/manual.md)")


def setup(app):
    app.connect("include-read", _rewrite_included_links)
