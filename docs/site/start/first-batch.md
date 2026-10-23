# Your first batch

This walks through one batch with `flahax mix` and RO water, the simplest case. It takes about
five minutes. You need FlahaX [installed](install.md) and a terminal: Windows Terminal,
PowerShell, `cmd`, or a Linux or macOS terminal.

## 1. Start

```bash
flahax mix
```

In a terminal FlahaX opens full screen. Arrow keys move, Enter chooses, typing filters a long
list, and Esc asks before quitting. If your terminal cannot show the full screen, the same
questions come line by line.

## 2. Answer the five steps

1. **Tanks.** Tank A and tank B capacity, the acid container, the injection ratio (litres of
   irrigation per litre of stock, often 100), the stock temperature, and whether you fill the
   tanks full or make just enough for one irrigation.
2. **Water.** Choose *RO water (no ions)* for this first batch, and press Enter at the
   concentration limits for none.
3. **Crop formula.** Choose *A packaged formula*, type `tomato` to filter the list, and pick one.
4. **Fertilizers.** Choose *The whole catalogue*, then *No* when asked to add a product. For the
   acid, choose *A new acid from its certificate* and type the formula (`HNO3`), the assay in
   % w/w and the density in kg/L from your supplier's certificate.
5. **Target pH.** Keep 5.8 or type your own. Then choose who the sheet is for (grower, agronomist
   or full report) and a name for the session.

## 3. Read the result

FlahaX calculates for a few seconds, writes the batch sheet, and opens the results on **Tanks**:
what to weigh into tank A and tank B and how much acid goes in the acid container. Tab shows
**Nutrients** and **Notes**. Press Q and then Y to leave; the recipe stays in your terminal and the
folder with `batch-sheet.html` is named on the last line.

## 4. Next time

```bash
flahax mix sessions/NAME
```

repeats the batch without questions.

**Next:** [Read the batch sheet](../grower/batch-sheet.md) and [Mix safely](../grower/mix-safely.md).
With your own water report, see [What you need](../grower/inputs.md).
