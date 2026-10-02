# Stock and irrigation EC planning (unreleased)

For the new **no-new-measurements** manufacturer-anchor screening path and
interactive CLI, see [site planning](site-planning.md) and the
[source-sheet review](source-sheet-review.md). The calibrated method below
is optional and separate; no measured profile is required by the new screening
command. Neither method invents concentrated-stock evidence.

`plan_ec_delivery` estimates EC25 independently for each concentrated stock
tank and the combined diluted irrigation mixture. It connects the existing
`StockPlan` to recipe-preserving injection volumes and, optionally, calibrated
pump runtimes. It never multiplies dilute EC by the concentration ratio, adds
A/B conductivities, or substitutes EC for nutrient balance.

## What a user supplies

At operation time the reading can be **water EC in mS/cm at 25 C**, or
**meter-equivalent TDS in ppm with the meter's configured conversion factor**.
The recipe, A/B assignment, concentration/injection ratio, final batch volume,
water-source identity and calibration records are configuration inputs—not
information recoverable from that single reading.

For a meter factor `f`, `EC(mS/cm) = TDS(ppm) / (1000*f)`.
Thus 250 ppm at factor 0.5 means 0.5 mS/cm. Do not silently assume a factor or
apply this identity to gravimetric TDS. See the
[manufacturer's EC/TDS explanation](https://knowledge.hannainst.com/en/knowledge/ec-tds-what-is-the-relationship-between-tds-and-ec).

Water EC alone **cannot** provide defensible universal EC predictions for
arbitrary concentrated fertilizers. Conductivity depends on ionic composition
and temperature ([USGS measurement guidance](https://pubs.usgs.gov/publication/tm9A6.3)).
The existing Davies equilibrium model is not extended into concentrated stock
conditions here. This increment is a bounded empirical calibration engine,
not a new first-principles conductivity or concentrated-electrolyte model.

## Calibration required once per supported recipe/source/protocol

Supply separate measured profiles for `tank:A`, `tank:B` (or actual tank IDs)
and `irrigation`. Each profile is a complete rectangular grid of **total EC**
over source-water EC and fertilizer strength. Strength 1 denotes the base
recipe's g/L in the final irrigation solution; a 100x stock is queried at
strength 100. The irrigation profile is queried at strength 1.

Interpolation is bilinear between adjacent measured grid nodes. A one-point
axis is usable only at that exact coordinate. No extrapolation is performed.
Curved/high-concentration behavior needs sufficiently dense measured points;
linear interpolation between measurements is not an assertion of universal
linearity. The profile's protocol must identify commercial grades/lots, water
source, preparation, temperature, meter calibration and any reagent additions.
The library checks supplied structure and identity, not whether measurements
were actually performed. No real measured EC calibration pack ships here.

Each profile contains:

| Field | Meaning |
|---|---|
| `schemaVersion` | String `"1"` |
| `id`, `source`, `revision`, `recordedAt`, `protocol` | Nonempty provenance; timestamp includes timezone |
| `channel` | `irrigation` or `tank:<id>` |
| `water_source_id` | Configured source/protocol identity; equal EC from a different source does not imply equal composition |
| `reference_temperature_c` | 25; this initial implementation also requires stocks prepared at 25 C |
| `recipe_key` | SHA-256 from `ec_recipe_key(stocks, channel, reagent_doses_g_per_l=...)` |
| `points` | Objects with `water_ec_ms_cm`, `strength`, `ec_ms_cm`; finite, nonnegative, unique complete grid |
| `validated_max_error_ms_cm` | Optional externally validated interpolation-error bound; omitted means unknown, not zero |

Recipe keys bind product identity/name, base dose and the shipped catalogue
assays. Separate acid/reagent doses, when present, are keyed by versioned
reagent-record ID and g/L of final mixture. They affect the irrigation key,
not the stock-tank keys. Calibration strength varies the fertilizer part;
separate reagent doses remain at their declared values. Changing those doses
requires matching new evidence. Omitting reagent doses means **pre-acid EC**,
not EC after an unaccounted acid addition.

## API and injection connection

```python
from flahax import plan_ec_delivery

# `stocks` is returned by plan_stocks or workflow.stages['stocks'].value.
# The configured profiles are real measured records, not guessed constants.
# plan = plan_ec_delivery(
#     stocks, profiles=profiles, water_source_id='site-water-protocol-v1',
#     water_ec_ms_cm=0.5,
#     pump_calibrations={'A': pump_a, 'B': pump_b},
#     available_volumes={'A': available_a, 'B': available_b},
# )
```

For an executable, self-contained **synthetic** example:

```powershell
$env:PYTHONPATH = 'src'
python -m examples.ec_and_injection
```

The example declares 100 L final solution and 100x stocks. Each used tank
contributes 1 L, or 10 mL/L of final solution. A/B together contribute 2 L;
the ratio is **per channel**, not a 1 L combined injection. Injection volume
times each stock concentration recovers its original recipe mass. Separate
acid volume and final-volume make-up still need their own planning.

An optional pump calibration maps each stock channel to its flow, uncertainty,
valid dose range and recorded time. Existing pump guards check inventory,
channel identity, calibrated range and age. Runtime is volume divided by
calibrated flow. These are planning values, not commands sent to equipment.
This version does not automatically adjust injection to reach an EC setpoint:
doing so would change nutrient doses and require a new nutrient/pH assessment.

## Results and guardrails

`ECDeliveryPlan` contains:

- `water_ec_ms_cm`: normalized input.
- `predictions`: independent `ECPrediction` values by channel, with `estimated`,
  `needs_input` or `blocked` status; estimated EC, optional supplied error
  bound, profile ID/hash and diagnostic fields.
- `injections`: litres, final-litres/stock-litre ratio and mL/L per tank.
- `pump_commands`: optional bounded runtime plans; operator verification required.
- `audit`: model ID, recipe keys, original water reading/scale, source and reagent boundary.

Missing profiles return `needs_input` with no EC number. A mismatched or
out-of-range profile returns `blocked` for its own channel without deleting
valid results from other channels. Malformed common inputs or inconsistent
stock assignments raise `DeliveryError`. Recipe-based injection arithmetic can
still be reported when EC evidence is missing; that does not approve the recipe
or authorize EC-driven correction. Verify EC after preparation/dilution using
meters rated for the relevant stock and irrigation ranges.

## Evidence boundary

`tests/test_conductivity.py` checks known bilinear results, independent tank and
combined EC, EC/TDS conversion, record identity, reagent changes, missing and
out-of-range calibration, temperature, dose conservation and pump guards.
`examples/ec_and_injection.py` deliberately uses fictional curved profiles to
exercise the algorithm. Passing these tests proves software behavior, **not**
physical EC accuracy for a commercial formulation. A site or manufacturer
calibration pack with hold-out validation is still required for that claim.

Local verification on Windows/Python 3.14.0, 2026-09-28: the full suite with
`PYTHONPATH=src` and `FLAHAX_REQUIRE_PHREEQC=1` passed 137 tests in 167.484 s,
with no skips. After the final overflow-safe TDS arithmetic adjustment,
`python -m unittest tests.test_conductivity tests.test_examples tests.test_release_hygiene -q`
passed all 17 tests. Compilation and `git diff --check` passed. Clean wheel
and sdist installation checks passed before that final arithmetic adjustment
(`build/ec-distribution-verification.json`); these are local development checks,
not hosted release approval or a physical EC accuracy certification.
