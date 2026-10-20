"""Sphinx configuration for the FlahaX documentation site."""
import os

from flahax import __version__

project = "FlahaX"
release = __version__
version = __version__

extensions = ["myst_parser", "sphinx_design", "sphinx_copybutton"]
source_suffix = {".md": "markdown"}

html_theme = "furo"
html_title = "FlahaX"
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
html_static_path = ["_static"]
html_css_files = ["flahax.css"]
html_favicon = "_static/brand/v2/flahax-logo-color.png"
html_theme_options = {
    "light_logo": "brand/v2/flahax-logo-color.png",
    "dark_logo": "brand/v2/flahax-logo-white.png",
    "sidebar_hide_name": True,
    "source_repository": "https://github.com/rafatahmed/Flahax/",
    "source_branch": "main",
    "source_directory": "docs/site/",
    "light_css_variables": {
        "color-brand-primary": "#1f6b45",
        "color-brand-content": "#1f6b45",
        "color-brand-visited": "#4a5d8f",
        "font-stack": "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        "font-stack--monospace": "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#6cc995",
        "color-brand-content": "#6cc995",
        "color-brand-visited": "#a3b2dc",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/rafatahmed/Flahax",
            "html": '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>',
            "class": "",
        },
    ],
}

copybutton_prompt_text = r">>> |\.\.\. |\$ |PS> "
copybutton_prompt_is_regexp = True

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
