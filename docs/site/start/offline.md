# Use FlahaX offline

Once installed, FlahaX calculates locally without a network connection. Keep
the instructions and input files you need before leaving a connected computer.
The grower or agronomist still reviews the result and records physical checks.

## On this page

- [What each delivery contains](#what-each-delivery-contains)
- [Keep the installed manual](#keep-the-installed-manual)
- [Keep the full website](#keep-the-full-website)
- [Keep your inputs and results](#keep-your-inputs-and-results)
- [When the version changes](#when-the-version-changes)

## What each delivery contains

| Delivery | Available locally | What to obtain separately |
|---|---|---|
| Installed wheel or source-package install | Application, catalogue/model data, `USER_GUIDE.md` and `API_REFERENCE.md` | Full website, screenshots and the example profile |
| Full source checkout | Website sources, build configuration, captures and `examples/sonneveld-appendix-i.json` | Documentation build dependencies, installed while connected |
| Built HTML directory | Audience guides, local images, downloads, reference pages and plain-text captures | The matching FlahaX installation for calculations |
| Saved batch output | `batch-sheet.html`, `report.html` and `summary.json` | Its source profile or saved session if you need to recalculate |

The source archive includes the example profile and capture assets. Building
the complete website uses the full source checkout and its documentation build
files; installing a source archive does not install the website beside the wheel.

## Keep the installed manual

This complete Python example copies the two installed Markdown resources into
an ordinary folder. It uses the installed package and needs no network access:

```python
from importlib.resources import files
from pathlib import Path

destination = Path("flahax-offline")
destination.mkdir(exist_ok=True)
for name in ("USER_GUIDE.md", "API_REFERENCE.md"):
    resource = files("flahax").joinpath("data", name)
    (destination / name).write_bytes(resource.read_bytes())
print(destination.resolve())
```

Open `USER_GUIDE.md` in a text or Markdown viewer. Keep both files together so
their relative links work. Section 12 covers Sonneveld review, rounded preparation
and replay. Links to the full website need a connection unless you also retain
the built site below.

## Keep the full website

From the full source checkout, while connected and using a virtual environment:

```bash
python -m pip install .
python -m pip install -r docs/site/requirements.txt
python -m sphinx -W --keep-going -b html docs/site build/docs-html
```

Copy **all of `build/docs-html`**, including `_static` and `_downloads`, to the
computer or folder where you will read it. Open `index.html` in a browser.
Copying only one page loses its images, styles and profile download.

Mermaid diagrams use an external rendering script. Without it, use the
[linked workflow table](choose-workflow.md), numbered review instructions,
the [accounting steps and verification tables](../agronomist/sonneveld-appendix-i.md)
and [plain-text TUI captures](../grower/sonneveld-walkthrough.md#screen-capture-provenance).
The images and these instructions are local; the diagrams add a visual summary.
The built manual's links to the current guides resolve inside the copied site.

At narrow widths or enlarged text, scroll wide tables and code blocks inside
their own panels. Open a screenshot at full size to read small values; its
caption, text record and worked table provide the same relevant information.
Text labels explain the statuses without relying on color.

## Keep your inputs and results

For the full Appendix I route, download
{download}`sonneveld-appendix-i.json <../../../examples/sonneveld-appendix-i.json>`
before going offline, or copy it from the source checkout. Follow the
[grower walkthrough](../grower/sonneveld-walkthrough.md) using its actual filename.

Keep the whole `FLAHAX_HOME` directory (default `~/.flahax`) when backing up
ordinary interview sessions: they can reference saved waters, formulas and
product/reagent lists. A Sonneveld session embeds its profile, approval and
selected result identity. Its replay needs the saved session and matching
model/input fingerprints, rather than the original import file. Retain the
original profile as the editable record for future changes.

The [Sonneveld repeat workflow](../grower/sonneveld-walkthrough.md#save-export-and-repeat)
is checked in a new process after removing the original import file. Working
offline preserves the same input, source and selected-candidate identity checks.

Save each run's three output files together in a distinct folder. Read the
qualifications and [measurements needed after mixing](../grower/mix-safely.md).
An offline calculation has the same physical-validation limits as an online one.

## When the version changes

Check `flahax --version` and retain the source revision or artifact identity
used for a calculation. Development checkouts can share the same version string
while containing different code. Review [migration guidance](migration.md) and
the [saved-session contracts](../reference/file-formats.md#sonneveld-saved-session).
A changed sample, design, product or model can require reimport and approval.
Keep the original session and exports rather than editing their fingerprints.

This guide describes the current development source. Historical release records
describe their own tagged versions; local validation does not establish that
these changes are published or that a future 0.7.0 candidate is release-ready.
