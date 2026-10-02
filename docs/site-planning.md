# Site inputs, calculated EC screening and injector sizing (unreleased)

The source water belongs to the user/site: there is **no default water
analysis**. Crop Ca target 104 mg/L minus measured water Ca 20 mg/L gives an
84 mg/L fertilizer gap, but does not identify bicarbonate, chloride or pH.
Full acid/base chemistry remains separate from nutrient target accounting.

## CLI

The existing `python -m flahax < recipe.json` stdin contract remains unchanged.
New commands accept JSON on stdin; `--interactive` prompts instead. Prompts
are on stderr and the result is one JSON object on stdout. No database,
hardware or external service is modified.

```powershell
$env:PYTHONPATH = 'src'
python -m flahax workflow --interactive
python -m flahax ec --interactive
python -m flahax size --interactive
```

The workflow requests a path to a JSON array of actual fertilizer records,
crop targets and **explicit** source-water nutrients, target pH and final
solution volume. Optional chemistry, acid and stock sections are entered as
JSON records. Blank optional records return `needs_input`; they do not become
invented measurements. Supply zero explicitly when known. All nutrient values
are elemental mg/L; nitrate/ammonium are expressed as N.

JSON workflow fields:

| Field | Meaning |
|---|---|
| `salts` | Explicit product array, same record schema as the original CLI |
| `targets`, `water` | Nutrient mg/L maps; water required; `{}` is an explicit all-zero declaration |
| `target_ph`, `final_volume_litres` | Required numerical pH target and final irrigation volume |
| `maximum_concentrations` | Optional explicit hard nutrient mg/L caps |
| `equilibrium` | Optional complete chemistry record described below |
| `acids` | Optional standard nitric/phosphoric candidate records and limits |
| `stocks` | Optional tank, ratio and sourced compatibility/solubility records |

The `equilibrium` object uses `water_totals` (analytical basis mol/kg-water),
`water_mass_kg` (final solvent inventory), `water_analysis_id`,
`complete_analysis: true`, `carbon_boundary: "closed"`, `temperature_c: 25`,
and explicit `phases` (empty array means aqueous-only). This is an advanced
analytical input, not a claim that a nutrient table is complete. Use the
existing [water-to-delivery contracts](water-to-delivery.md); no alkalinity
mg/L-to-total-carbon conversion is silently assumed. Catalogue identity/assay
and water nutrient-vs-molal agreement are checked before calculating pH.

`acids` contains `products`, `maximum_nutrient_error_percent`,
`maximum_reagent_volume_litres` and optional `preferred_product_id`. Each
product needs `id`, `source`, `revision`, timezone-qualified `recordedAt`,
`chemicalFormula` (`HNO3` or `H3PO4` only), `massFraction` (0-1, not percent),
and `densityKgPerL`. No industrial assay/density is assumed. Nitric adds N;
phosphoric adds P; both must meet formulation constraints after dosing.
The lower-level four-acid API and prior reference fixtures remain preserved
for compatibility, but are not the standard workflow choices.

`stocks` contains `final_litres_per_stock_litre`, `temperature_c`,
`tanks: [{"id":"A", "capacity_litres":100}, ...]`, `compatibility_rules`,
and `solubility_limits`, using the existing sourced stock contracts. Tank
capacity is not a water chemistry input. CLI planning does not emit actuator
commands or require new pump calibration measurements.

## No-new-measurements EC screening

```json
{
  "doses_g_per_litre": {
    "Ultrasol K Plus": 0.5,
    "Ultrasol Calcium": 0.25,
    "Ultrasol MKP": 0.1
  },
  "water_ec_ms_cm": 0.5,
  "temperature_c": 25,
  "channel": "irrigation",
  "acid_added": false
}
```

Pass this object to `python -m flahax ec`: **1.52 mS/cm**, status
`screening_estimate`, unknown numerical accuracy. This is a separate example,
not the pepper recipe. Coefficients come from the supplied SQM sheet, with
source hash/page retained in results. Exact commercial identities are required;
generic catalogue names are not aliases. Full method limits and source review:
[source-sheet review](source-sheet-review.md).

Alternatively provide `water_tds_ppm` and `tds_factor`, not water EC as well.
This is a meter-equivalent conversion, not a universal gravimetric TDS law.
For example 250 ppm / (1000 * 0.5) = 0.5 mS/cm.

The command does **not** fit a calibration or request new EC measurements.
It also does not extrapolate the single-salt brochure values to A/B stocks,
acid-treated mixtures or unknown trace products. Those return `not_supported`
with null EC and a specific reason, not zero or a partial-sum total. Other
temperatures and total product load above 1 g/L are outside this deliberately
restricted screening policy. The acid-adjusted or full pepper EC and general
concentrated-stock model remain open work.

## Injector design requirements

```json
{
  "equipment_type": "dosatron",
  "active_area_m2": 2000,
  "gross_depth_mm": 5,
  "duration_hours": 2,
  "channels": {
    "A": {"final_litres_per_stock_litre":100, "available_stock_litres":100},
    "B": {"final_litres_per_stock_litre":100, "available_stock_litres":100}
  }
}
```

Pass to `python -m flahax size`: 10,000 L final irrigation, 5,000 L/h final
flow, **100 L stock and 50 L/h per channel**. Alternatively specify
`final_volume_litres` instead of area/depth. Use concurrently irrigated area
and gross applied depth; whole farm size alone cannot specify a flow.
Supported equipment categories: `dosing_pump`, `venturi`, `dosatron`.

The ratio is final L per stock L: at 100x with two tanks, carrier water is
9,800 L, not 10,000 L plus an extra 200 L. Each channel is 1% of final volume,
but 1.020408% of common carrier volume. This latter ratio is **not** a universal
device setting: serial injectors have different local inlet flows. Include
separate acid stock volume as a channel if applicable. Check prepared-stock
inventory, not just tank nominal capacity.

Output lists missing pressure, hydraulic layout, fluid properties and
manufacturer operating curves, and leaves `selected_model` null. This is a
design specification, not a purchase recommendation or control command.
Farm/tank dimensions cannot determine those absent parameters.

## Example and validation

```powershell
$env:PYTHONPATH = 'src'
python -m examples.calculated_site_planning
python -m unittest tests.test_site_planning tests.test_examples tests.test_water_workflow tests.test_release_hygiene
```

The combined HTML report includes a separate calculated screening graph/table,
unavailable A/B predictions and a per-channel sizing table. The older
fictional calibration example remains labelled as a distinct API demo.

### Local verification, 2026-09-30

- `PYTHONPATH=src FLAHAX_REQUIRE_PHREEQC=1 python -m unittest discover -s tests -t .`:
  **149 tests passed, 207.550 s, zero skips** (environment variables set with
  `$env:...` in PowerShell). PHREEQC live replay used the existing external
  installation; its executable and base database were not modified.
- Initial sandboxed full run: 149 tests, two temporary-directory permission
  errors in live PHREEQC replay. The successful full rerun used approved
  temporary-directory access; no test or tolerance was removed to pass.
- Focused workflow/examples/source-input tests: 31 passed in 73.327 s.
  Final site-input/release-hygiene check: 13 passed in 1.175 s.
- `python -m compileall -q src examples`: passed.
- `git diff --check`: passed (line-ending normalization warnings only).
- `python -m examples.run_all --output build/site-planning-reviewed`: generated
  HTML, Markdown and JSON; browser inspection confirmed the calculated EC chart,
  unavailable-stock rows and per-channel flow table render correctly.

These checks verify arithmetic, data transcription and rejection boundaries;
they do not establish experimental accuracy of the screening approximation,
validate a concentrated-stock conductivity model, or approve equipment.
