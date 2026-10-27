(delivery-planning-contracts-p0)=
# Input schemas and validation

`flahax.delivery_contracts` provides input validation and provenance for stock-tank, pH, and dosing planning. It validates data and records provenance. It does **not** calculate a stock recipe, pH dose, or pump command, and it does not connect to hardware.

## Current supported mode

Schema version `0.1` supports **batch** planning records only. `proportional` injection is rejected with error code `unsupported_mode`; this schema does not implement a proportional-injection calibration or flow model.

## Public API

This standalone synthetic envelope demonstrates record validation only. Empty planning lists
do not qualify a recipe, stock mixture or delivery plan.

```python
from flahax import make_audit_record, validate_delivery_request

request = {
    "schemaVersion": "0.1", "mode": "batch",
    "waterAnalysis": {
        "schemaVersion": "0.1", "id": "synthetic-water",
        "source": "Teaching example, not laboratory evidence", "revision": "1",
        "recordedAt": "2026-10-27T00:00:00Z",
        "ions": {}, "temperatureC": 25, "pH": 7, "alkalinityMgLAsCaCO3": 0,
    },
    "products": [], "compatibilityRules": [], "solubilityLimits": [],
    "titrationCurves": [], "pumpCalibrations": [],
}
validated = validate_delivery_request(request)
audit = make_audit_record(validated, model_version="delivery-contracts-0.1")
assert validated["mode"] == "batch"
```

`validate_delivery_request` returns a normalized copy of the input. `make_audit_record` revalidates the request and returns deterministic record identifiers and the supplied model version. Neither function writes files, databases, or external systems.

## Request shape

Every versioned record has:

```text
schemaVersion: "0.1"
id: stable record identifier
source: origin of the measurement or rule
revision: source-record revision
recordedAt: ISO 8601 timestamp
```

The top-level request is:

```text
{
  schemaVersion: "0.1",
  mode: "batch",
  waterAnalysis: {...},
  products: [...],
  compatibilityRules: [...],
  solubilityLimits: [...],
  titrationCurves: [...],
  pumpCalibrations: [...]
}
```

The records deliberately preserve their own source/revision metadata. A plan cannot later claim to have been based on an unspecified water test, product assay, compatibility rule, or pump calibration.

## Contract rules

- Water analysis requires ion values and temperature. pH and alkalinity may be recorded when available; the measured-curve pH planner requires alkalinity; the separate equilibrium adapter requires complete analytical totals and measured initial pH.
- Product assays are elemental percentages, not ppm. They reject total `N`, unknown ions, values outside 0-100%, and sums above 100.5%. Acid/base records may also carry sourced `densityKgPerL` and `normalityMeqPerL`; the measured-curve pH planner requires both.
- Compatibility rules currently represent sourced hard `separate` constraints across two or more product IDs.
- Solubility limits require a product ID, maximum g/L, and minimum/maximum temperature range.
- Titration curves require at least two strictly increasing acid/base demand points in meq/L. They are measurements for one water/reagent pair, not a generic pH formula.
- Pump calibration records require non-zero flow, flow variation, and a valid volume range. They are evidence only; input validation cannot command a pump.

## Errors

Invalid records raise `DeliveryError`, a subclass of `InputError`, with a stable `code` attribute. Current codes include:

| Code | Meaning |
|---|---|
| `unsupported_schema` | Record does not use schema version `0.1` |
| `unsupported_mode` | Requested operating mode is not yet supported |
| `missing_field` | A required record component is absent |
| `invalid_type` | Value has the wrong data type |
| `invalid_value` | Value is syntactically or structurally invalid |
| `out_of_range` | Numeric value is finite but outside an allowed bound |
| `unknown_ion` | Assay uses an ion outside the FlahaX ion schema |
| `ambiguous_unit` | Input uses total nitrogen rather than nitrate/ammonium form |

(p0-acceptance-evidence)=
## Validation coverage

The test suite includes a valid batch fixture, deterministic audit replay, rejected unsupported mode, rejected total nitrogen assay, rejected incomplete calibration data, and rejected non-monotonic titration data. The contracts are intentionally strict: a later calculation must receive explicit data or fail with an actionable error.
