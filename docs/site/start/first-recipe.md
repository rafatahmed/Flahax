# Your first recipe in Python

Select salts from the packaged catalogue for a crop formula, with 20 mg/L of calcium already in
the water:

```python
from flahax import load_library, recommend

result = recommend(
    load_library()["salts"],
    targets={"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54},
    water={"Ca": 20},
)

for salt in result["salts"]:
    print(f"{salt['name']}: {salt['gramsPerLitre']} g/L")
```

- `result["salts"]` lists each chosen salt with grams per litre of the final solution, the one the
  plant receives.
- `result["rows"]` gives each element's target, final concentration (mg/L) and percentage
  difference.
- Element keys are `N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu` and
  `Mo`; nitrogen is mg/L as N and sulfur as S.

**Next:** [Python API in practice](../developer/python-api.md) for inputs, results, tolerances and
limits, and the [Python API reference](../reference/api.md) for every public function.
