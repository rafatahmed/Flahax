# Measured batch pH evidence

Recipe verification requires `stock_evidence.batch_ph` in addition to stock assays,
dispenser and final-volume calibration records. Numerical pH predictions never
substitute for a batch reading. Existing records without this section remain
unverified with `missing_batch_ph_evidence`.

## Acceptance equation

The indicated pH is the displayed reading after the instrument's routine calibration.
The bound used by FlahaX is:

`total_uncertainty_ph = maximum_absolute_bias_ph + absolute_uncertainty_ph + additional_uncertainty_ph`

The first two terms come from the meter/electrode calibration. The third comes from
the batch measurement, excluding those already-counted calibration contributions.
The complete interval `[indicated_ph - total_uncertainty_ph, indicated_ph + total_uncertainty_ph]`
must lie within the requested pH range, inclusively: 6.28–6.32 for this recipe.

For example, 6.300 with residual bias 0.002, calibration uncertainty 0.003 and
additional batch uncertainty 0.005 gives 6.290–6.310 and passes. A central reading
inside the target interval does not pass when its uncertainty interval crosses a
boundary. No best-case subtraction or root-sum-square reduction of these declared
error bounds is used. These are the workflow's conservative acceptance rules, not
a claim that a particular instrument or measurement method achieves them.

## Record structure

The updated [blank template](../examples/stock-evidence-template.json) has three objects:

- `assignment`: `batch_id`, `vessel_id`, `meter_id`, `electrode_id`,
  `calibration_record_id`, `measurement_record_id`.
- `calibration`: common record fields plus `calibrated_at`, `ph_min`, `ph_max`,
  `maximum_absolute_bias_ph`, `absolute_uncertainty_ph`, `coverage` and `buffers`.
- `measurement`: common record fields plus `measured_at`, `batch_id`, `vessel_id`,
  `calibration_record_id`, `preparation_fingerprint`, `indicated_ph`,
  `additional_uncertainty_ph` and `application`.

Common fields are `record_id`, `source`, `method`, `measured_on`, `valid_until`,
`temperature_c`, `uncertainty_basis`, `meter_id` and `electrode_id`. All identities
must match assignments; all record IDs must be distinct across the complete evidence
package. The vessel must match the final-volume calibration assignment.

Dates use YYYY-MM-DD, evaluated in UTC. Timestamps include an explicit timezone,
must agree with `measured_on` in UTC, and cannot be in the future. A reading cannot
predate its calibration. Both records must be current on assessment day. The
temperature must match the recipe's modeled 25 C condition; automatic temperature
compensation does not itself establish chemical equivalence to a 25 C batch.

`uncertainty_basis` must be `total_bound_through_valid_until`. Calibration uncertainty
must cover the relevant buffer, calibration and drift contributions. Additional
batch uncertainty must cover applicable sampling, repeatability, matrix/junction,
temperature and subsequent drift effects through the declared validity period,
without double-counting calibration terms. The referenced method/report must justify
these bounds and validity windows. No conversion from standard deviations or
expanded uncertainties to guaranteed bounds is performed automatically.

Calibration `coverage` is `entire_declared_range`; `ph_min`–`ph_max` must cover the
requested pH range. `buffers` contains at least two distinct buffer references, each
with `reference` and `certified_ph` at the calibration temperature. Their certified
values must bracket the declared calibration range. Referenced certificates and the
calibration method must support their applicability and uncertainty; the software
does not independently authenticate them.

Measurement `application` must be `final_mixed_batch_no_unaccounted_additions`. A
reading taken before final dilution, or after an acid/base addition absent from the
recipe accounting, cannot certify the planned chemistry. No dosing adjustment is
silently inferred from a pH record.

## Binding a reading to a preparation

1. Submit the numerical stock recipe with completed stock, dispenser and final-volume
   records. Leave `batch_ph` absent while obtaining the preparation specification.
2. Read `stock_verification.preparation_fingerprint`. A valid final-volume assignment
   is required before a fingerprint is emitted. This step does not verify the batch.
3. Prepare the named physical batch using those instructions, then record the final
   mixed-batch pH and its applicable calibration. Include the fingerprint in the
   measurement record and bind the physical batch, vessel and instrument IDs.
4. Resubmit the same recipe with the completed evidence. All numerical and record
   checks are required for `verified: true`.

The fingerprint binds rounded stock doses, concentration/dosing specifications,
stock and dispenser identities, final vessel and volume, water-mass approximation,
temperature, pH range, phase selection and uncertainty bounds. It excludes the pH
reading itself. Numerically equivalent integer/float representations hash identically.
An actual dose, stock identity or acceptance-bound change requires a matching batch
record; a measurement from one preparation cannot certify a different search candidate.

Consequently, stock searching without measurement records remains a numerical design
operation and returns unverified candidates. Searching with completed batch evidence
can verify only candidates matching that measured preparation. For strongest-recipe
work, search first, prepare and measure the selected batch, then verify that fixed
recipe. Batch measurement cannot be predicted for newly proposed preparations.

## Result and limits

`stock_verification.batch_ph_check` reports identity bindings, total uncertainty,
the measured interval and the required interval. All pH records are included in the
existing evidence snapshot and SHA-256 digest. Records are operator-supplied;
passing does not authenticate a certificate, prove the measurement occurred, or
guarantee future pH or precipitation-free operation beyond the stated evidence scope.
Stock concentration, dosing, volume, nutrient-ratio and saturation checks all remain
mandatory. Steiner's historical 0.13-unit discrepancy remains unresolved; this gate
requires evidence for the actual batch rather than fitting the model to that discrepancy.
