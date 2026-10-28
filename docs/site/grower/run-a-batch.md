# Run a batch with `flahax mix`

`flahax mix` asks for the same five things in order and remembers your answers,
so the next batch is one command:

1. **Specification**: tank A, tank B and acid container sizes, the injection
   ratio, the temperature, and whether you fill the tanks full (several
   irrigations) or make just enough for one irrigation.
2. **Water analysis**: RO water, a saved analysis, or a new one typed from the
   lab report in its own units (mg/L, meq/L or mmol/L; NO3 and SO4 as printed).
   Enter means *not measured*, `0` a measured zero, and `<0.02` below detection,
   as the lab prints it. The charge balance is shown at once.
3. **Crop formula**: a packaged formula, a saved one, or a packaged one changed
   value by value.
4. **Fertilizers available**: the catalogue, a saved store, or ticking what you
   have. A product you add is either a **chemical** (MKP, calcium nitrate) with
   the label on your bag, or a **compound** (an NPK 20-20-20 + TE) typed from its
   data sheet: the nitrogen forms, P2O5, K2O, the micronutrients and the
   chelating agent. FlahaX checks that the label's charges balance; a compound
   that does not balance is still used for nutrients, but no acid is planned for
   that batch.
5. **pH requirement**: the target pH of the irrigation solution.

```bash
flahax mix                          # first time: answers the five steps
flahax mix sessions/tomato-ro       # next time: no questions
```

In a terminal window (Windows Terminal, the Windows console, or a Linux or macOS
terminal of at least 80 x 24) `flahax mix` opens full screen. The arrow keys
move, Enter chooses, typing narrows a long list such as the crop formulas, Space
ticks the fertilizers you have, and Esc asks before quitting. The steps go
forward only. In a wide window your answers so far stay on the left. When the
batch is calculated the result opens on **Tanks** (tank A, tank B and the acid
container with what to weigh); Tab shows **Nutrients** (the agronomist table and
the pH path) and **Notes** (every review note once). A blocked batch opens on
Notes with the reason. The sheets are written before the result appears, the
same as in the line-by-line mode. `flahax mix --plain` keeps the line-by-line
questions, which are also used automatically when the output is not a terminal
(a script, a pipe or an editor's output panel).

At the end choose who the result is for. **Grower**: the batch sheet with tank
A and tank B (prepared litres and grams to weigh, with tick boxes), the acid
container and the checks after mixing. **Agronomist**: the same, plus the
nutrient table (target, from water, required, achieved, final, difference),
the limits and the pH path. **Developer or manager**: both, plus the full
report and `summary.json`. Use the calculated tank assignments: additional tanks
may be required, and equipment capacity never waives an incompatibility. A blocked
result shows diagnostic quantities without preparation instructions. Missing or
condition-limited solubility evidence remains qualified in the result.

## Resizing, stopping and reopening

The full-screen view redraws when the window size changes. Esc or Q on the results
asks before leaving; Ctrl+C also leaves the result screen. Sheets already written
remain available. During the interview, stopping before all answers are complete
saves nothing. After answers have been saved, a calculation error does not turn the
saved session into an accepted result.

The terminal attempts to restore its cursor, normal screen and console mode on
exit, including input disconnection and output errors. If a console cannot support
full-screen mode, use `flahax mix --plain`. A closed terminal cannot display cleanup
output; reopen a terminal if the host window itself has disconnected.

Saved-session replay uses the same calculation and result identity as plain mode.
Changed saved inputs/model sources are rejected for review, and changed result
content is rejected before display. Review and explicitly migrate stale sessions
as described in the developer guide; no terminal action grants result acceptance.


The steps below do the same with `flahax batch`, one command with files, for
scripts and for checking a plan by hand.
