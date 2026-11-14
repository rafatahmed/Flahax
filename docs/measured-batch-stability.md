# Measured batch stability

`stable` is a separate, stricter result than preparation `verified`. A numerically
acceptable recipe, or a batch with complete preparation and pH records, is not
automatically stable. Supply `batch_stability` alongside `stock_evidence` in a fixed
stock-recipe request. The [blank template](../examples/batch-stability-template.json)
contains no real measurements and cannot pass as supplied.

## Accepted example policy

The user-selected illustrative policy uses preparation, 24 h, 72 h and 168 h
observations, turbidity at most 1 NTU and at least 95% dissolved calcium and phosphorus
retention. The example also declares a one-hour late sampling allowance and 5%
initial nutrient agreement tolerance. All policy fields are explicit and configurable:

```json
{
  "required_hours": [0, 24, 72, 168],
  "maximum_delay_hours": 1,
  "maximum_turbidity_ntu": 1,
  "minimum_retention_fraction": 0.95,
  "initial_nutrient_relative_tolerance": 0.05
}
```

These are engineering acceptance choices, not experimentally validated shelf-life
limits for Steiner's recipe. NTU is a quantitative clarity criterion, not a recorded
visual inspection. Each required sample must occur within `[required_hour,
required_hour + maximum_delay_hours]`; early samples do not establish the full
required elapsed time. The baseline is exactly the verified initial batch-pH sample.
Every supplied observation is checked, including intermediate or extra samples;
a failed intermediate result cannot be hidden by a passing final sample.

## Required identity, protocol and observations

`assignment` contains the verified `batch_id`, `vessel_id` and
`preparation_fingerprint`. Records from another preparation cannot establish stability.
`protocol` requires an identifier, source, storage conditions, filter pore size and
the following declarations:

- `dissolved_basis`: `filtered_elemental_Ca_and_total_dissolved_P`.
- `turbidity_sample`: `representative_unfiltered_batch`.
- `material_accounting`: `no_additions_withdrawals_count_as_loss`.

The filtration pore size must be positive and no larger than 0.45 micrometres, with
one consistent method throughout the series. Record the actual method and cutoff;
finer filtration defines a different operational fraction. For phosphorus, use
total dissolved P reported as elemental P, not mg/L phosphate or an interchangeable
orthophosphate-only assay. EPA Method 365.3 distinguishes dissolved phosphorus in
the filtered, digested sample from directly measured orthophosphate. This reference
supports the analytical distinction, not FlahaX's stability limits or certification
of a laboratory method. [EPA Method 365.3](https://www.epa.gov/sites/default/files/2015-08/documents/method_365-3_1978.pdf).

Each observation has a unique `observation_id`, timezone-qualified `sampled_at`,
four measurement records, and a `ph_measurement`:

| Measurement key | Units and interpretation |
|---|---|
| `turbidity_ntu` | NTU, representative unfiltered batch sample |
| `dissolved_calcium_mg_l` | mg/L elemental Ca in the defined filtrate |
| `dissolved_phosphorus_mg_l` | mg/L total elemental dissolved P in the defined filtrate |
| `volume_litres` | Remaining batch volume at sampling, not the original fill volume |

Each measurement record requires `value`, `absolute_uncertainty`, `instrument_id`,
`calibration_reference`, `method`, `source`, and
`uncertainty_basis: total_bounded_error`. The bound must include applicable bias,
calibration, sampling and analytical contributions. Calibration/report references
are retained but not downloaded, parsed or independently authenticated by this gate.
Laboratory measurements must refer to the timestamped sample and documented
preservation/processing method, even if analysis occurs later.

Each sample includes its contemporaneous batch-pH measurement in the existing pH
record schema. The baseline record must exactly match the initial verified reading.
Later readings require distinct IDs and use the same declared meter/electrode
calibration, which must remain applicable and current. Their full uncertainty
intervals must remain inside the recipe's pH interval. This version does not accept
an undocumented instrument change or a second calibration midway through the study.

## Conservative calculations

For each measurement, let the interval be `[max(0, value - U), value + U]`.

1. Clarity passes only if the upper turbidity bound is at most the declared limit.
2. For Ca and P, multiply concentration and volume interval endpoints to obtain
   remaining dissolved nutrient mass in mg.
3. Initial Ca and P mass intervals must lie within the declared tolerance of the
   rounded recipe's calculated elemental amounts. This rejects an already-depleted
   baseline. The baseline measured-volume interval must also fit the preparation's
   final-volume bound.
4. For every later sample, require
   `current_mass_lower / initial_mass_upper >= minimum_retention_fraction` for
   both Ca and P. Baseline uncertainty therefore counts as well as later uncertainty.

For example, a central Ca result of 95% of baseline is insufficient if its uncertainty
allows retention below 95%. Evaporation cannot hide mass loss by increasing measured
concentration. Sampling withdrawals count as losses from the remaining batch; this
is conservative and can reject a study with excessive sampling even without
precipitation. Nutrient additions, replacement water or replacement samples require
a different mass-balance workflow and are not accepted under this protocol.

## Output and scope

`stability_assessment` includes the submitted records and SHA-256 digest, per-sample
turbidity bounds, Ca/P mass intervals, retention lower bounds, pH checks, missing
sampling times, observation start/end and declared policy. Statuses are:

- `stable`: all preparation, observation and schedule requirements passed.
- `not_stable`: at least one observation failed the declared acceptance criteria;
  this does not by itself identify a precipitate or prove physical instability.
- `insufficient_evidence`: no observed criterion failure, but required times are missing.
- `invalid_evidence`: malformed, mismatched, future-dated or unsupported records.
- `unverified`: missing stability records or an unverified preparation.

Only `stable` sets the top-level `stable: true`. Consume the flag together with
`qualified_duration_hours`, `observation_end`, the policy and recorded conditions.
The example qualifies the declared seven-day study only. It does not prove continuous
clarity between samples, later shelf life, all-nutrient retention, crop suitability or
hydroxyapatite kinetics. Nutrient loss cannot be attributed to precipitation alone.

When `batch_stability` is supplied to a search, failing candidates are excluded and
the selected candidate is checked again. Measured records qualify only the matching
physical preparation; search and plan first, then prepare and observe the batch.
No real longitudinal data are bundled, and the existing Steiner recipe remains
without a stability qualification until actual records are supplied.
