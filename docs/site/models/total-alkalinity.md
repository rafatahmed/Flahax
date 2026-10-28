# Total alkalinity and carbon inference

Total alkalinity is a proton inventory, not a carbon measurement. The supported
reference follows the inorganic terms in the
[NOAA/OCADS description of the Dickson definition](https://www.ncei.noaa.gov/access/ocean-carbon-acidification-data-system/oceans/co2rprt.html).
This defines bookkeeping; it does not import seawater constants or establish field accuracy.

For free species the supported expression is:

```
HCO3 + 2 CO3 + borate + OH + HPO4 + 2 PO4 + NH3 - H - HSO4 - H3PO4
```

Quantities are mol/kg solvent and the result is equivalents/kg solvent. Phosphate
is referenced to H2PO4-, boron to H3BO3, ammonia to NH4+, carbonate to H2CO3 and
sulfate to SO4. Complexes of supported major ions inherit these proton counts
from their reaction stoichiometry; hydroxide and proton contributions remain
explicit. `carbonate_alkalinity` remains a separate carbonate-only helper.

`total_alkalinity` supports the current model's Ca, Mg, K, Na, chloride, nitrate,
ammonium, sulfate, carbonate, phosphate and borate species. Active organic ligands,
trace-metal species or other components without a qualified reference cause an
`unsupported_alkalinity` error. Silicate, sulfide, fluoride and unknown organic
alkalinity are not silently assumed negligible. Supply a complete analysis in the
supported domain; this is not a universal titration interpretation.

## Enter a titration

```json
{
  "id": "measured-titration",
  "measured_ph": 7.5,
  "mg_per_litre": {"Ca": 40.078, "Cl": 35.45},
  "alkalinity_meq_per_litre": 1.0
}
```

These are illustrative inputs, not a certified balanced sample. The concentration
basis follows [solvent-mass accounting](concentration-basis.md). Interactive entry
converts alkalinity reported as HCO3 or CaCO3 into equivalents, preserving that it
was a titration. Below-detection alkalinity is an interval and is rejected for
point-value inference; it is not silently assigned zero carbon.

Legacy `mg_per_litre.HCO3` still supplies an equivalent total-inorganic-carbon
inventory. Reports disclose this approximation; it is neither measured
bicarbonate speciation nor total alkalinity. Do not use that field for a titration.
Do not supply both carbon and total alkalinity, even when either is zero.

## Infer only missing carbon

At fixed measured pH, the solver includes supported noncarbonate alkalinity before
solving for missing carbon. A carbon-free phosphate or borate inventory can already
explain the titration and must not acquire invented carbonate. Signed alkalinity
is accepted when consistent with the supported chemistry; a target below the
carbon-free value is rejected. Equality within 1e-12 eq/kg uses the existing
charge-closure numerical scale. This is not a laboratory uncertainty allowance.

Measured zero carbon, below-detection carbon and explicitly fixed carbon cannot
be adjusted. Titrated alkalinity is held fixed during balance-ion reconciliation;
if no suitable measured balance ion exists, the calculation requires further input.
The legacy fallback for positive, nonfixed directly supplied carbon remains a
reported model adjustment, with the original analytical inventory retained.
Laboratory nutrient limits always use that analytical inventory, never the model's
adjusted values. Physical titration validation remains a separate later stage.
