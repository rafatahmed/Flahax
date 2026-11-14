# Stock assay, dispenser and final-volume calibration records

Stock recipe `verified` is true only when numerical checks, measured batch pH and all applicable
supplied-record checks pass. `stock_verification` reports the numerical status,
evidence status, failure details, per-stock checks, UTC assessment date and record
snapshot/hash. A numerical `passed` or search `found` alone is not evidence verification.

No real laboratory records are bundled. The blank
[`stock-evidence-template.json`](../examples/stock-evidence-template.json) deliberately
contains nulls and cannot pass. Populate it from actual measurements and add the
object as `stock_evidence` to a fixed-stock recipe or stock-search request.
Synthetic records exist only in unit tests and must not be treated as measurements.

## Binding records to delivery

`assignments` maps each of the six exact formula/hydrate strings to `stock_id`,
`dispenser_id`, `assay_record_id` and `calibration_record_id`. Stock IDs identify
specific physical batches, not generic fertilizer names. Six distinct IDs are
required for the six separate stocks. Record IDs must be unique across both lists.

Every stock assay or dispenser calibration record requires these fields:

| Field | Meaning |
|---|---|
| `record_id` | Unique assay or calibration identifier |
| `stock_id` | Exact stock batch to which the measurement applies |
| `source` | Certificate/report reference; retained verbatim, not downloaded or authenticated |
| `method` | Measurement method and applicable procedure reference |
| `measured_on`, `valid_until` | ISO dates, YYYY-MM-DD; current UTC date must be inside the interval |
| `temperature_c` | Must match the recipe's modeled 25 C condition |
| `uncertainty_basis` | Must be `total_bound_through_valid_until` |

The stated uncertainty must cover the relevant preparation, measurement, repeatability,
drift and stability contributions through expiry. Standard deviations and expanded
uncertainties are not automatically converted to guaranteed bounds. The operator must
justify the submitted bounded-error interpretation in the referenced method/report.
Unknown fields are rejected so conflicting units or alternate uncertainty fields
cannot be silently ignored. Unassigned records and missing referenced records are rejected.

## Assay records

Each `assays` entry additionally requires:

- `formula`: the exact compound/hydrate assigned to the stock.
- `measured_concentration_g_l`: measured active-compound-equivalent concentration.
- `absolute_uncertainty_g_l`: nonnegative total absolute error bound.
- `concentration_basis`: `specified_compound_equivalent_g_l`.
- `reactive_impurities`: `excluded_by_measurement`.

The gate checks full interval containment:

`abs(measured_concentration_g_l - recipe_stock_concentration_g_l) + absolute_uncertainty_g_l`

must not exceed `recipe_stock_concentration_g_l * concentration_relative_error`.
The lower measured bound must also remain positive. This accounts for bias away
from the nominal stock value as well as assay uncertainty. For a 10 g/L stock at
±0.1%, 10.005 ±0.005 g/L fits; 10.006 ±0.005 g/L does not.

Measurements do not silently replace the concentrations used for dosing. If an assay
does not fit, explicitly update `concentrations_g_l` and replan the doses and chemistry.
KOH total alkalinity alone does not establish the specified KOH concentration when
carbonate is present. The chemical-basis and impurity assertions require supporting
measurements; entering their enum strings is not a laboratory determination.

## Calibration records

Each `calibrations` entry additionally requires:

- `dispenser_id`, matching the assigned device.
- `dose_min_ml`, `dose_max_ml`, containing the actual rounded delivered dose.
- `maximum_absolute_bias_ml`, a nonnegative measured bias bound over that range.
- `absolute_uncertainty_ml`, the additional nonnegative error bound.
- `coverage`: `entire_declared_range`.

The calibration must match the actual stock liquid and temperature. Water-only
calibration is not implicitly transferred to a different liquid. The gate requires
`maximum_absolute_bias_ml + absolute_uncertainty_ml <= dose_error_ml`.
A calibration tested only at isolated endpoints does not establish the required
whole-range bound; its report must justify coverage. There is no dose extrapolation.

## Search and final verification

Measured pH and meter/electrode calibration are now also mandatory. See
[measured batch pH records](measured-batch-ph-records.md) for the full-interval
acceptance rule, timestamps, calibration buffers and preparation fingerprint.
Stock, dispenser and final-volume records alone no longer permit verification.

### Final-volume calibration

`stock_evidence.final_volume` is mandatory for verification. It contains an
`assignment` with `vessel_id` and `calibration_record_id`, and a `calibration`
object for that vessel and volume mark. Older evidence containing only stock assays
and dispenser calibrations is still assessed, but remains unverified with
`missing_final_volume_calibration`.

The calibration record uses the same source, method, date, temperature and bounded
uncertainty requirements as the other records. Its exact fields are:

| Field | Requirement |
|---|---|
| `record_id`, `vessel_id` | Match the assignment; record ID must be distinct from all stock records |
| `source`, `method` | Nonempty report reference and calibration/filling procedure |
| `measured_on`, `valid_until` | ISO dates containing the current UTC assessment date |
| `temperature_c` | Match the recipe's modeled temperature |
| `uncertainty_basis` | `total_bound_through_valid_until` |
| `nominal_volume_litres` | Exact requested final volume, 10 for the Steiner batch; no extrapolation |
| `measured_volume_litres` | Measured contained volume at that mark |
| `absolute_uncertainty_litres` | Nonnegative total volume error bound |
| `capacity_basis` | `to_contain`, rather than a to-deliver capacity |
| `application` | `final_solution_including_stocks` |

The gate requires:

`abs(measured_volume_litres - nominal_volume_litres) + absolute_uncertainty_litres <= volume_error_litres`

The lower measured-volume bound must be positive. For a 10 L batch with the
existing ±0.05 L allowance, 10.030 ±0.020 L passes; 10.031 ±0.020 L fails.
Both positive and negative volume biases count. The submitted bound must include
the relevant calibration, filling/meniscus, temperature, repeatability and drift
contributions applicable to the finished solution and the referenced procedure.
It must cover making up to the mark after adding all stock doses, not adding stocks
after measuring 10 L of water. These applicability statements require supporting
evidence; the software does not establish them from enum values alone.

`stock_verification.final_volume_check` reports its separate status, assigned IDs,
measured interval, total deviation and permitted bound. The whole record is included
in the immutable snapshot and canonical-data hash. Passing stock and dispenser
records cannot override a missing or failing final-volume check.

Without `stock_evidence`, numerical searching remains available, but results have
`verified: false` and `verification_status: unverified`. With evidence supplied,
the search excludes candidates failing the record gate, including candidates whose
rounded dose falls outside calibration coverage or the final-volume bound is unsupported.
The selected recipe is recalculated and all three types of records checked again
before return, together with the batch pH evidence. Failed or incomplete chemistry always
blocks verification, even if every record fits.

The gate snapshots records and records a SHA-256 digest of their canonical JSON.
This binds the result to the exact submitted data; it is not a digital signature or
proof of a certificate's authenticity. Existing expiry checks apply at evaluation
time. Saved results do not automatically renew: rerun before later use.

`verified` means the submitted-record and numerical gates passed. It does not certify
actual dispensing or filling, certificate authenticity, stock storage stability beyond
the submitted bounds, or precipitation-free operation. The final-volume calibration
supports the numerical volume bound; it does not prove that the actual batch was
filled correctly. No physical calibration records are fabricated or bundled.
Steiner's unresolved experimental pH discrepancy and the sampled nature of the
saturation/uncertainty checks remain visible.
