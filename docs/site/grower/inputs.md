# What you need before you start

Have these ready before you run `flahax mix`. With RO or desalinated water alone you need no lab report.

| You need | Where it comes from |
|---|---|
| A water analysis with its **measured pH** and **bicarbonate** (or alkalinity) | Your water laboratory. For RO or desalinated water alone, nothing: use `ro`. |
| A crop formula | One of the packaged formulas, or your own targets in mg/L |
| Your acid's strength and density, if the feed needs acid | The acid supplier's certificate of analysis |
| Any maximum concentrations you must respect (for example Na and Cl) | Your crop guidelines or advisor. FlahaX never assumes one. |
| FlahaX installed | `python -m pip install flahax`, or `python -m pip install --upgrade flahax` if you have an older version (see [install](../developer/python-api.md)) |

The lab report is entered as printed, in its own units; see [Run a batch](run-a-batch.md). For the file format used by `flahax batch`, see [A batch from files](../agronomist/batch-command.md).
