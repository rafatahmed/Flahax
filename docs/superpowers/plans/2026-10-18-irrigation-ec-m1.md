# Irrigation EC M1 (McCleskey 2012 on speciation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the M1 development preview: an experimental Python API that calculates irrigation EC25 from FlahaX speciation with McCleskey (2012) Eq. 8, returning `estimated`, `partial` or `not_supported` with full provenance.

**Architecture:** A shipped JSON file holds McCleskey Table 1 and a species mapping. One new module, `irrigation_ec.py`, has three layers: λ(I) from the coefficients, a totals-level calculation on an `AqueousResult` (status rules, coverage, envelope, audit), and thin entry points for catalogue doses, an `EquilibriumPhPlan` and the post-mix comparison. Speciation, pH and phases reuse `aqueous_model.solve`, `calculate_equilibrium_ph` and `catalogue_dose_totals` unchanged.

**Tech Stack:** Python 3.13, standard library only, `unittest`.

**Spec:** [docs/superpowers/specs/2026-10-18-irrigation-ec-mccleskey-design.md](../specs/2026-10-18-irrigation-ec-mccleskey-design.md)

## Global Constraints

- No new runtime dependency; pure Python.
- 25 °C only; any other temperature returns `not_supported` / `temperature_outside_reference`.
- Computational envelope: speciated I ≤ 0.1 mol/kgw (equality allowed). Solver rejection maps to `not_supported` / `ionic_strength_outside_domain`.
- Closed inorganic carbon only; otherwise `not_supported` / `unsupported_carbon_boundary`.
- McCleskey coefficients are transcribed from the paper, never from Horticalc. The paper PDF (`docs/sources/mccleskey_nordstrom_etal_2012.pdf`, SHA-256 `17002c4eeedef68ddb62048f3b1b0c77a96b03d5f9dc51b167fc05e9f145ce1f`) is local only and is never committed.
- Units recorded on every result: `conductivity_units = "mS kg cm-1 mol-1 x mol/kgw"`; no density conversion is applied.
- Any uncovered charged species above 1e-12 mol/kgw makes the result `partial`. No contribution bound in M1 (O2 is open).
- O5: assay charge residual ≤ 0.1 % of absolute equivalents is reported and does not block. Above it: `supplied` → `partial` (`unrecorded_counterions`); `calculated` → `not_supported` (`assay_charge_residual_too_large`).
- Fixed qualifier on every result: `"Accuracy on this fertilizer mixture has not yet been established."`
- M1 is Python API only: no CLI flag, no USER_GUIDE section, no grower-facing number. Docstrings say "experimental (M1)".
- Magsul's brochure anchor is never shown beside a calculation (no code here does; do not add any).
- Work on branch `feat/irrigation-ec-m1`. The working tree holds unrelated uncommitted files (publication drafts, audit folder, spec): stage only the files each task names.

## Review Focus

1. **Chelate products in `calculated` mode.** Iron EDTA's declared net charge (Fe³⁺ + EDTA⁴⁻ = −1, with no counterion in the catalogue) can push the assay residual over 0.1 %. Expect `not_supported` / `assay_charge_residual_too_large` with the percent reported, not a crash. Pinned in Task 3.
2. **Recipe of zero doses in declared pure water.** Expect `estimated` with the pure-water EC from H⁺/OH⁻ (about 5.5e-5 mS/cm), not an error or a divide-by-zero in the residual percent. Pinned in Task 3.
3. **`ph` given in `calculated` mode, or missing/NaN in `supplied` mode.** Expect `DeliveryError('invalid_ph_input')`, never a silent choice of mode. Pinned in Task 2.
4. **Plain dict passed as water** (for example `{}` meaning "RO"). Expect `DeliveryError('incomplete_water_analysis')` telling the user to declare pure water. Pinned in Task 3.
5. **Negative or non-finite measured EC in the post-mix comparison.** Expect `DeliveryError('invalid_value')`. Pinned in Task 5.

---

### Task 0: Branch

- [ ] **Step 1: Create the branch from the current checkout**

```bash
git switch -c feat/irrigation-ec-m1
```
Expected: `Switched to a new branch 'feat/irrigation-ec-m1'`, and `git status` still shows the pre-existing uncommitted files untouched.

---

### Task 1: McCleskey coefficient data, λ(I) and transcription verification

**Files:**
- Create: `src/flahax/data/conductivity_mccleskey2012.json`
- Create: `src/flahax/irrigation_ec.py` (loader and λ only in this task)
- Create: `tests/fixtures/conductivity/mccleskey2012_table1_independent.json`
- Test: `tests/test_irrigation_ec.py`

**Interfaces:**
- Produces: `load_conductivity_coefficients() -> dict` (cached); `COEFFICIENTS_SHA256: str` (SHA-256 of the shipped file bytes, computed at import); `ionic_molal_conductivity(ion: str, ionic_strength: float, temperature_c: float = 25.0) -> float` (mS·kg·cm⁻¹·mol⁻¹); `covered_species() -> frozenset[str]` (FlahaX species names with a coefficient).

**Data file layout** (keys fixed; the implementer fills values from Table 1, page 372 of the paper):

```json
{
  "schema": "1",
  "model_id": "mccleskey2012-eq8",
  "species_mapping_version": "1",
  "units": "mS kg cm-1 mol-1",
  "equation": "lambda = lambda0(T) - A(T) * sqrt(I) / (1 + B * sqrt(I)); lambda0, A = a*T^2 + b*T + c, T in C",
  "source": {"citation": "McCleskey, Nordstrom, Ryan, Ball (2012) Geochim. Cosmochim. Acta 77, 369-382, Table 1",
             "doi": "10.1016/j.gca.2011.10.031",
             "pdf_sha256": "17002c4eeedef68ddb62048f3b1b0c77a96b03d5f9dc51b167fc05e9f145ce1f"},
  "ions": {"K+": {"lambda0": [0.003046, 1.261, 40.70], "A": [0.00535, 0.9316, 22.59], "B": 1.5}},
  "species_map": {"K+": "K+"}
}
```

`ions` holds all 28 Table 1 rows, keyed by the paper's ion written in FlahaX notation (`K+`, `Na+`, `H+`, `Li+`, `Cs+`, `NH4+`, `Ca+2`, `Mg+2`, `Ba+2`, `Sr+2`, `SO4-2`, `Cl-`, `F-`, `Br-`, `CO3-2`, `HCO3-`, `NO3-`, `OH-`, `Al+3`, `Cu+2`, `Fe+2`, `Fe+3`, `Mn+2`, `Zn+2`, `KSO4-`, `NaSO4-`, `HSO4-`, `NaCO3-`). Signs are as printed (for example H⁺ `lambda0` a = −0.01414; Fe³⁺ `A` c = −22.18). `species_map` maps each FlahaX aqueous species name to a Table 1 key, and only for the 21 that exist in `chemistry_25c.json`: all of the above except Li⁺, Cs⁺, Ba²⁺, Sr²⁺, F⁻, Br⁻ and Al³⁺.

- [ ] **Step 1: Create the independent fixture.** A different agent from the one writing the shipped JSON types `tests/fixtures/conductivity/mccleskey2012_table1_independent.json` from the paper PDF: same `ions` structure, no other keys, with a `"typed_by"` note. Neither agent copies from the other's file.

- [ ] **Step 2: Write failing tests** in `tests/test_irrigation_ec.py`, class `CoefficientTests`:

```python
def test_shipped_table_matches_independent_transcription(self):
    shipped = load_conductivity_coefficients()['ions']
    fixture = json.loads((FIXTURES / 'mccleskey2012_table1_independent.json').read_text())['ions']
    self.assertEqual(set(shipped), set(fixture))
    self.assertEqual(len(shipped), 28)
    for ion in shipped:
        self.assertEqual(shipped[ion], fixture[ion], ion)

def test_species_map_targets_exist_and_cover_flahax_species(self):
    data = load_conductivity_coefficients()
    names = {r['name'] for r in chemistry()['aqueous']}
    self.assertEqual(len(data['species_map']), 21)
    for species, ion in data['species_map'].items():
        self.assertIn(species, names); self.assertIn(ion, data['ions'])

def test_eq8_at_25c_by_hand(self):
    # K+: l0 = 0.003046*625 + 1.261*25 + 40.70 = 74.12875; A = 49.22375; B = 1.5
    self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.0), 74.12875, places=9)
    self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.01), 74.12875 - 49.22375*0.1/1.15, places=9)
    # Cl-: l0 = 76.800625; A = 49.51375
    self.assertAlmostEqual(ionic_molal_conductivity('Cl-', 0.01), 76.800625 - 49.51375*0.1/1.15, places=9)

def test_coefficient_file_is_pinned(self):
    raw = files('flahax').joinpath('data/conductivity_mccleskey2012.json').read_bytes()
    self.assertEqual(COEFFICIENTS_SHA256, hashlib.sha256(raw).hexdigest())

def test_lambda_rejects_unknown_ion_and_bad_strength(self):
    for args in (('Li2+', .01), ('K+', -1.), ('K+', float('nan'))):
        with self.subTest(args=args), self.assertRaises(DeliveryError):
            ionic_molal_conductivity(*args)
```

- [ ] **Step 3: Run and confirm failure**

Run: `PYTHONPATH=src python -m unittest tests.test_irrigation_ec -v`
Expected: FAIL / ImportError for `flahax.irrigation_ec`.

- [ ] **Step 4: Implement** the data file and, in `src/flahax/irrigation_ec.py`, `load_conductivity_coefficients`, `COEFFICIENTS_SHA256`, `ionic_molal_conductivity` and `covered_species`. Use the module docstring style of `calculated_ec.py`, labelled experimental (M1). `ionic_molal_conductivity` looks up a Table 1 key directly (not via the species map) and raises `DeliveryError('unknown_ion', ...)` or `DeliveryError('invalid_value', ...)`. `covered_species()` returns the keys of `species_map`.

- [ ] **Step 5: Run and confirm pass.** Same command. Expected: 5 tests OK.

- [ ] **Step 6: Commit**

```bash
git add src/flahax/data/conductivity_mccleskey2012.json src/flahax/irrigation_ec.py tests/fixtures/conductivity/mccleskey2012_table1_independent.json tests/test_irrigation_ec.py
git commit -m "Add McCleskey 2012 Table 1 coefficients with independent transcription check"
```

---

### Task 2: EC from analytical totals (status rules, coverage, envelope, audit)

**Files:**
- Modify: `src/flahax/irrigation_ec.py`
- Test: `tests/test_irrigation_ec.py` (class `TotalsTests`)

**Interfaces:**
- Consumes: Task 1 functions; `aqueous_model.solve`, `calculated_ph.calculate_equilibrium_ph`, `aqueous_model.chemistry`.
- Produces:
  - `QUALIFIER: str` (the fixed sentence).
  - `MODEL_VERSION = "irrigation-ec-mccleskey2012-m1-experimental"`.
  - Frozen dataclass `IrrigationECResult` with fields: `status: str`, `ec25_ms_cm: float | None`, `known_species_subtotal_ms_cm: float | None`, `contributions_ms_cm: dict`, `transport_numbers: dict`, `missing_species: tuple` (dicts with `name`, `charge`, `molal`), `unrecorded_counterions_eq_per_kgw: float | None`, `assay_charge_residual: dict` (`eq_per_kgw`, `percent`), `reason: str | None`, `ph: float | None`, `ionic_strength: float | None`, `precipitated_molal: dict`, `warnings: tuple`, `audit: dict`, `qualifier: str = QUALIFIER`.
  - `calculate_ec_from_totals(totals_molal: Mapping[str, float], *, solution_id: str, ph_mode: str, ph: float | None = None, phase_policy: str, phases: Sequence[str] = (), carbon_boundary: str = 'closed', temperature_c: float = 25.0, assay_charge_residual_eq_per_kgw: float = 0.0, audit_inputs: Mapping | None = None) -> IrrigationECResult`.
  - Private `_ec_from_state(state: AqueousResult, *, ph_mode, phase_policy, phases, assay_residual_eq, audit_inputs) -> IrrigationECResult`, reused by Task 4.

**Rules the code implements (from the spec):**
- `ph_mode='calculated'`: `ph` must be `None`; call `calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=phases)`. `ph_mode='supplied'`: `ph` must be finite in [0, 14]; call `solve(totals, ph, phases=phases)`. Otherwise `DeliveryError('invalid_ph_input')`.
- `phase_policy='dissolved'` requires `phases == ()`. `'equilibrated'` requires a nonempty tuple. Otherwise `DeliveryError('invalid_phase_policy')`. For `dissolved`, every SI > 0 adds the warning `f"{phase} supersaturated (SI {si:.3f}); no kinetic interpretation"`.
- Order of checks: temperature ≠ 25 or carbon ≠ closed → `not_supported` before solving. A solver `DeliveryError` with code `activity_model_out_of_range` → `not_supported` / `ionic_strength_outside_domain`. Other solver errors propagate.
- Total equivalents `E = Σ|z|·m` over speciated charged species. Assay residual percent = `100 * assay_residual_eq / E` (0 when E = 0).
- Gate O5: if `|assay percent| > 0.1` → `calculated`: `not_supported` / `assay_charge_residual_too_large`; `supplied`: `partial` / `unrecorded_counterions`.
- `supplied` only: `excess = state.charge_balance - assay_residual_eq`; if `|excess| > max(1e-12, 0.001 * E)` → `partial` / `unrecorded_counterions`, with `unrecorded_counterions_eq_per_kgw = excess`.
- Contributions: for each charged species with m > 1e-12 mapped in `species_map`, `λ(I) * m`, with I = `state.ionic_strength`. An unmapped charged species with m > 1e-12 goes into `missing_species`. Any missing species → `partial` / `missing_species_contributions`. Neutral species are ignored.
- `estimated` sets `ec25_ms_cm = Σ contributions` and transport numbers (contribution / total). `partial` sets `ec25_ms_cm = None` and `known_species_subtotal_ms_cm = Σ contributions`. `not_supported` sets both to `None`.
- `audit` keys: `temperature_reference_c` (25), `ph_mode`, `ph`, `phase_policy`, `phases`, `carbon_boundary`, `solution_id`, `chemistrySha256` (as in `equilibrium_delivery.py:159`), `coefficientsSha256`, `equation` (`mccleskey2012-eq8`), `speciesMappingVersion`, `conductivity_units`, `unit_conversions` (list, empty here), `solver_iterations`, `charge_balance`, `model` (`MODEL_VERSION`), plus every item of `audit_inputs`.

- [ ] **Step 1: Write failing tests**

```python
def calc(self, totals, **kw):
    kw.setdefault('ph_mode', 'calculated'); kw.setdefault('phase_policy', 'dissolved')
    return calculate_ec_from_totals(totals, solution_id='t', **kw)

def test_kcl_001_is_estimated_by_hand_value(self):
    r = self.calc({'K+': .01, 'Cl-': .01})
    self.assertEqual(r.status, 'estimated')
    self.assertAlmostEqual(r.ec25_ms_cm, 1.42343, places=4)
    self.assertEqual(r.qualifier, QUALIFIER)
    self.assertEqual(r.audit['conductivity_units'], 'mS kg cm-1 mol-1 x mol/kgw')
    self.assertEqual(r.audit['coefficientsSha256'], COEFFICIENTS_SHA256)
    self.assertAlmostEqual(sum(r.transport_numbers.values()), 1.0, places=12)

def test_neutral_pair_carries_no_current(self):
    m = 1/246.47
    r = self.calc({'Mg+2': m, 'SO4-2': m})
    self.assertEqual(r.status, 'estimated')
    self.assertAlmostEqual(r.ec25_ms_cm, 0.725, delta=0.001)
    self.assertNotIn('MgSO4', r.contributions_ms_cm)

def test_phosphate_is_partial_and_named(self):
    m = 1/136.09
    r = self.calc({'K+': m, 'PO4-3': m})
    self.assertEqual((r.status, r.reason), ('partial', 'missing_species_contributions'))
    self.assertIsNone(r.ec25_ms_cm)
    self.assertIn({'name': 'H2PO4-', 'charge': -1}, [{k: s[k] for k in ('name', 'charge')} for s in r.missing_species])
    self.assertAlmostEqual(r.known_species_subtotal_ms_cm, 0.524, delta=0.002)

def test_ionic_strength_envelope(self):
    self.assertEqual(self.calc({'K+': .0995, 'Cl-': .0995}).status, 'estimated')
    r = self.calc({'K+': .12, 'Cl-': .12})
    self.assertEqual((r.status, r.reason, r.ec25_ms_cm), ('not_supported', 'ionic_strength_outside_domain', None))

def test_temperature_and_carbon_not_supported(self):
    self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, temperature_c=20).reason, 'temperature_outside_reference')
    self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, carbon_boundary='open').reason, 'unsupported_carbon_boundary')

def test_supplied_ph_with_unrecorded_acid_is_partial(self):
    self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, ph_mode='supplied', ph=7.0).status, 'estimated')
    r = self.calc({'K+': .01, 'Cl-': .01}, ph_mode='supplied', ph=4.0)
    self.assertEqual((r.status, r.reason), ('partial', 'unrecorded_counterions'))
    self.assertGreater(r.unrecorded_counterions_eq_per_kgw, 0)

def test_assay_residual_gate(self):
    tot = {'K+': .01, 'Cl-': .01}
    ok = self.calc(tot, assay_charge_residual_eq_per_kgw=1e-5)       # 0.05 %
    self.assertEqual(ok.status, 'estimated'); self.assertAlmostEqual(ok.assay_charge_residual['percent'], 0.05, places=3)
    self.assertEqual(self.calc(tot, assay_charge_residual_eq_per_kgw=1e-4).reason, 'assay_charge_residual_too_large')

def test_phase_policy_recorded_and_supersaturation_warned(self):
    tot = {'Ca+2': .004, 'SO4-2': .004, 'PO4-3': .001, 'K+': .003}
    r = self.calc(tot, ph_mode='supplied', ph=7.0)
    self.assertTrue(any('Hydroxylapatite' in w for w in r.warnings))
    e = self.calc(tot, ph_mode='supplied', ph=7.0, phase_policy='equilibrated', phases=('Hydroxylapatite',))
    self.assertEqual(e.audit['phases'], ('Hydroxylapatite',)); self.assertTrue(e.precipitated_molal)

def test_invalid_mode_inputs_raise(self):
    for kw in ({'ph': 7.0}, {'ph_mode': 'supplied'}, {'ph_mode': 'supplied', 'ph': float('nan')},
               {'ph_mode': 'guess'}, {'phase_policy': 'dissolved', 'phases': ('Gypsum',)},
               {'phase_policy': 'equilibrated'}):
        with self.subTest(kw=kw), self.assertRaises(DeliveryError):
            self.calc({'K+': .01, 'Cl-': .01}, **kw)
```

The `invalid_ph_input` cases (Review Focus 3) are the first four.

- [ ] **Step 2: Run and confirm failure.** `PYTHONPATH=src python -m unittest tests.test_irrigation_ec.TotalsTests -v` → ImportError / AttributeError.
- [ ] **Step 3: Implement** `QUALIFIER`, `MODEL_VERSION`, `IrrigationECResult`, `calculate_ec_from_totals` and `_ec_from_state` per the rules above.
- [ ] **Step 4: Run and confirm pass.** Same command, all `TotalsTests` OK, and `CoefficientTests` still OK.
- [ ] **Step 5: Commit**

```bash
git add src/flahax/irrigation_ec.py tests/test_irrigation_ec.py
git commit -m "Calculate irrigation EC25 from speciated totals with partial and envelope rules"
```

---

### Task 3: Catalogue recipe entry point, water inputs and assay residual

**Files:**
- Modify: `src/flahax/irrigation_ec.py`
- Test: `tests/test_irrigation_ec.py` (class `CatalogueTests`)

**Interfaces:**
- Consumes: `calculate_ec_from_totals` (Task 2); `product_conversion.catalogue_dose_totals`; `catalogue_chemistry.chemistry_for_product`; `measured_water.BalancedWaterAnalysis`.
- Produces:
  - Frozen dataclass `DeclaredPureWater(water_id: str, kind: str = 'RO')`. `kind` is one of `'RO'` or `'distilled'`. `water_id` must be nonempty.
  - `assay_charge_residual(doses_g_per_kg_water: Mapping[str, float]) -> dict` returning `{'eq_per_kgw': float, 'percent': float}`.
  - `calculate_irrigation_ec(doses_g_per_kg_water: Mapping[str, float], *, recipe_id: str, water: BalancedWaterAnalysis | DeclaredPureWater, water_analysis_id: str | None = None, reagent_additions_molal: Mapping[str, float] | None = None, reagent_id: str | None = None, ph_mode: str, ph: float | None = None, phase_policy: str, phases: Sequence[str] = (), carbon_boundary: str = 'closed', temperature_c: float = 25.0) -> IrrigationECResult`.

**Rules:**
- `water` must be a `BalancedWaterAnalysis` (then `water_analysis_id` is required and nonempty) or a `DeclaredPureWater` (then `water_analysis_id` must be `None`). Anything else, including a dict, raises `DeliveryError('incomplete_water_analysis', 'supply a balanced complete analysis or DeclaredPureWater')`.
- Totals = water totals (none for pure water) + `catalogue_dose_totals(doses)` + `reagent_additions_molal` (base names from `chemistry()['bases']`, finite and nonnegative; `reagent_id` required iff additions are given). Reagents are acids whose protons are implicit, so they are excluded from the assay residual.
- **Assay residual algorithm** (the spec's definition; pH-independent). For each product, convert its dose alone with `catalogue_dose_totals({name: dose})` and sum z·m with these charges: Ca⁺², Mg⁺², Fe⁺², Mn⁺², Zn⁺², Cu⁺² = +2; Fe⁺³ = +3; K⁺, Na⁺, NH₄⁺ = +1; NO₃⁻, Cl⁻ = −1; SO₄⁻², MoO₄⁻², CO₃⁻² = −2; Edta⁻⁴, Edd⁻⁴ = −4; Dtp⁻⁵ = −5; Citrate⁻³ = −3; H₃BO₃, Ure = 0. PO₄⁻³ takes the charge of the product's declared phosphate component in `chemistry_for_product(name).components`: `H2PO4-` = −1, `HPO4-2` = −2, `H3PO4` = 0. `percent = 100 * Σ z·m / Σ |z|·m` (0 when the denominator is 0). The returned `eq_per_kgw` is passed to `calculate_ec_from_totals`. Note that Task 2 rescales the percent against speciated equivalents; record the declared-form percent in `audit['assay_charge_residual_declared_percent']`.
- Audit adds `recipe_id`, `water_kind` (`balanced_analysis` or `declared_pure:<kind>`), `water_id`, `reagent_id`, `doses_g_per_kg_water` and `catalogueSha256`.

- [ ] **Step 1: Write failing tests**

```python
PURE = DeclaredPureWater('ro-test')

def test_mg_nitrate_assay_residual(self):
    self.assertAlmostEqual(assay_charge_residual({'Mg Nitrate': 1.0})['percent'], 0.5532, places=3)

def test_residual_gate_by_mode(self):
    c = calculate_irrigation_ec({'Mg Nitrate': 1.0}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
    self.assertEqual((c.status, c.reason), ('not_supported', 'assay_charge_residual_too_large'))
    s = calculate_irrigation_ec({'Mg Nitrate': 1.0}, recipe_id='r', water=PURE, ph_mode='supplied', ph=6.0, phase_policy='dissolved')
    self.assertEqual((s.status, s.reason), ('partial', 'unrecorded_counterions'))

def test_chelate_residual_reported_not_crash(self):           # Review Focus 1
    r = calculate_irrigation_ec({'Iron EDTA': 0.05, 'Potassium Nitrate': 0.5}, recipe_id='r', water=PURE,
                                ph_mode='calculated', phase_policy='dissolved')
    self.assertEqual(r.status, 'not_supported'); self.assertEqual(r.reason, 'assay_charge_residual_too_large')
    self.assertLess(r.audit['assay_charge_residual_declared_percent'], -0.1)

def test_zero_doses_in_pure_water(self):                        # Review Focus 2
    r = calculate_irrigation_ec({}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
    self.assertEqual(r.status, 'estimated'); self.assertAlmostEqual(r.ec25_ms_cm, 5.48e-5, delta=2e-6)

def test_water_input_contract(self):                            # Review Focus 4
    for water, wid in (({}, None), ({'K+': .001}, None), (PURE, 'x')):
        with self.subTest(water=water), self.assertRaises(DeliveryError):
            calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=water, water_analysis_id=wid,
                                    ph_mode='calculated', phase_policy='dissolved')
    with self.assertRaises(DeliveryError):
        DeclaredPureWater('')

def test_balanced_water_and_reagent_recorded(self):
    bw = balance_water_analysis({'Na+': .002, 'Cl-': .002}, measured_ph=7.0, alkalinity_eq_per_kg=1e-4)
    r = calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=bw, water_analysis_id='lab-1',
                                reagent_additions_molal={'NO3-': 1e-4}, reagent_id='nitric',
                                ph_mode='calculated', phase_policy='dissolved')
    self.assertEqual(r.status, 'estimated')
    self.assertEqual((r.audit['water_id'], r.audit['reagent_id'], r.audit['water_kind']), ('lab-1', 'nitric', 'balanced_analysis'))
    self.assertLess(r.ph, 7.0)

def test_unknown_product_and_bad_dose_raise(self):
    for doses in ({'Unobtainium': 1.}, {'Potassium Nitrate': -1.}, {'Potassium Nitrate': float('nan')}):
        with self.subTest(doses=doses), self.assertRaises(DeliveryError):
            calculate_irrigation_ec(doses, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
```

- [ ] **Step 2: Run and confirm failure.** `PYTHONPATH=src python -m unittest tests.test_irrigation_ec.CatalogueTests -v`.
- [ ] **Step 3: Implement** `DeclaredPureWater`, `assay_charge_residual` and `calculate_irrigation_ec` per the rules. Balanced waters carry closed carbon (`CO3-2`), so `test_balanced_water_and_reagent_recorded` also exercises HCO₃⁻ and CO₃²⁻ coverage.
- [ ] **Step 4: Run and confirm pass.** All classes in `tests.test_irrigation_ec` OK.
- [ ] **Step 5: Commit**

```bash
git add src/flahax/irrigation_ec.py tests/test_irrigation_ec.py
git commit -m "Add catalogue entry point, declared pure water and assay charge residual for irrigation EC"
```

---

### Task 4: EC from an `EquilibriumPhPlan`

**Files:**
- Modify: `src/flahax/irrigation_ec.py`
- Test: `tests/test_irrigation_ec.py` (class `PlanTests`)

**Interfaces:**
- Consumes: `_ec_from_state` (Task 2), `assay_charge_residual` (Task 3), `equilibrium_delivery.EquilibriumPhPlan`.
- Produces: `calculate_irrigation_ec_from_plan(plan: EquilibriumPhPlan, *, phase_policy: str = 'dissolved') -> IrrigationECResult`.

**Rules:** Use `plan.equilibrium.target` as the state, treated as `supplied` at `plan.target_ph` (spec section 5). Do not re-solve. Doses are `{salt.name: salt.mass.value / plan.water_mass_kg}`, summed per name. `phases` come from `plan.audit` if the plan records them, otherwise `()`. A nonempty phase list with `phase_policy='dissolved'` raises `DeliveryError('invalid_phase_policy')`. Audit adds `recipe_id` (the plan recipe's identity, or `plan.audit` input hash if present), `water_id = plan.water_analysis_id`, `reagent_id = plan.reagent_id` and `reagent_molal = plan.equilibrium.nitric_acid_molal`. Run the same temperature, carbon and residual gates as Task 2.

- [ ] **Step 1: Write failing tests**

```python
@classmethod
def setUpClass(cls):
    from tests.test_equilibrium_delivery import arguments
    cls.plan = plan_equilibrium_delivery(**arguments())

def test_plan_target_state_is_used_without_resolving(self):
    r = calculate_irrigation_ec_from_plan(self.plan)
    self.assertEqual(r.status, 'estimated')
    self.assertEqual(r.ph, self.plan.target_ph)
    self.assertEqual(r.audit['ph_mode'], 'supplied')
    self.assertEqual((r.audit['water_id'], r.audit['reagent_id']), ('synthetic-complete-water-v1', 'nitric'))
    self.assertAlmostEqual(r.ionic_strength, self.plan.equilibrium.target.ionic_strength, places=15)
    self.assertGreater(r.ec25_ms_cm, 0)
```

- [ ] **Step 2: Run and confirm failure.** `PYTHONPATH="src;." python -m unittest tests.test_irrigation_ec.PlanTests -v` (on POSIX use `src:.`).
- [ ] **Step 3: Implement** `calculate_irrigation_ec_from_plan`.
- [ ] **Step 4: Run and confirm pass.** Same command OK.
- [ ] **Step 5: Commit**

```bash
git add src/flahax/irrigation_ec.py tests/test_irrigation_ec.py
git commit -m "Calculate irrigation EC on an EquilibriumPhPlan target state"
```

---

### Task 5: Post-mix comparison

**Files:**
- Modify: `src/flahax/irrigation_ec.py`
- Test: `tests/test_irrigation_ec.py` (class `ComparisonTests`)

**Interfaces:**
- Produces: `compare_measured_ec(prediction: IrrigationECResult, *, measured_ec25_ms_cm: float, meter_reference_temperature_c: float) -> dict` with exactly the keys `predicted_ec25_ms_cm`, `measured_ec25_ms_cm`, `difference_ms_cm` (measured − predicted), `relative_difference_percent` (100 × difference / predicted), `audit` (the prediction's audit) and `qualifier`.

**Rules:** A non-`estimated` prediction raises `DeliveryError('incomplete_prediction')`. A meter reference other than 25 raises `DeliveryError('temperature_reference_mismatch')`. A non-finite, negative or boolean measured value raises `DeliveryError('invalid_value')`. There are no verdict, tolerance or suggestion keys.

- [ ] **Step 1: Write failing tests**

```python
def test_difference_only_no_verdict(self):
    p = calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id='kcl', ph_mode='calculated', phase_policy='dissolved')
    c = compare_measured_ec(p, measured_ec25_ms_cm=1.413, meter_reference_temperature_c=25)
    self.assertEqual(set(c), {'predicted_ec25_ms_cm', 'measured_ec25_ms_cm', 'difference_ms_cm',
                              'relative_difference_percent', 'audit', 'qualifier'})
    self.assertAlmostEqual(c['difference_ms_cm'], 1.413 - p.ec25_ms_cm, places=12)

def test_refusals(self):                                         # Review Focus 5
    p = calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id='kcl', ph_mode='calculated', phase_policy='dissolved')
    partial = calculate_ec_from_totals({'K+': .007, 'PO4-3': .007}, solution_id='mkp', ph_mode='calculated', phase_policy='dissolved')
    cases = [(partial, 1.0, 25), (p, 1.0, 20), (p, -1.0, 25), (p, float('nan'), 25), (p, True, 25)]
    for pred, measured, ref in cases:
        with self.subTest(measured=measured, ref=ref), self.assertRaises(DeliveryError):
            compare_measured_ec(pred, measured_ec25_ms_cm=measured, meter_reference_temperature_c=ref)
```

- [ ] **Step 2: Run and confirm failure.** `PYTHONPATH=src python -m unittest tests.test_irrigation_ec.ComparisonTests -v`.
- [ ] **Step 3: Implement** `compare_measured_ec`.
- [ ] **Step 4: Run and confirm pass.**
- [ ] **Step 5: Commit**

```bash
git add src/flahax/irrigation_ec.py tests/test_irrigation_ec.py
git commit -m "Add post-mix EC comparison without verdicts"
```

---

### Task 6: Public exports, API reference, docs and full verification

**Files:**
- Modify: `src/flahax/__init__.py` (append an `__all__ +=` block after line 141, following the existing pattern)
- Regenerate: `src/flahax/data/API_REFERENCE.md` via `tools/generate_api_reference.py`
- Modify: `docs/conductivity.md` (new section "Calculated irrigation EC (experimental, M1)")
- Modify: `docs/development-status.md` (one new row in the capability table)
- Modify: `CHANGELOG.md` (an Unreleased entry)
- Modify: `docs/audit/2026-10-17-flahax-vs-horticalc/review.md` (an "Owner sign-off" line for the Table 1 transcription)

**Interfaces:**
- Exports: `IrrigationECResult`, `DeclaredPureWater`, `calculate_irrigation_ec`, `calculate_irrigation_ec_from_plan`, `calculate_ec_from_totals`, `compare_measured_ec`, `assay_charge_residual`.

- [ ] **Step 1: Add the exports** with an import line and an `__all__ +=` line like line 139–141.
- [ ] **Step 2: Regenerate the API reference.** `PYTHONPATH=src python tools/generate_api_reference.py`, then `PYTHONPATH=src python tools/generate_api_reference.py --check`. Expected: the check exits 0.
- [ ] **Step 3: Write the docs.**
  - **conductivity.md:**
    - States the purpose ("estimate before mixing, compare after") and that the feature is experimental M1, Python only.
    - Gives the status table (`estimated` / `partial` / `not_supported`), the 25 °C and I ≤ 0.1 mol/kgw envelope, the units sentence, the O5 rule, and that phosphate recipes are `partial` until M2.
    - Includes one runnable example using `calculate_ec_from_totals` on 0.01 mol/kgw KCl, with the qualifier.
    - Links the spec.
  - **development-status.md:** add the row "Calculated irrigation EC (McCleskey 2012 on speciation) | `irrigation_ec.py`, transcription and rule tests | Experimental M1; phosphate and chelate species partial; no measured accuracy".
  - **CHANGELOG:** add "Add experimental irrigation EC25 from speciation (McCleskey 2012 Eq. 8) with explicit partial results, envelope checks and provenance; no accuracy claim."
  - **Review sign-off line:** "Table 1 transcription: owner sign-off pending" (the owner replaces it after checking against the PDF).
- [ ] **Step 4: Run the full repository checks**

```bash
PYTHONPATH=src python tools/generate_api_reference.py --check
PYTHONPATH=src python -m unittest tests.test_release_hygiene
PYTHONPATH="src;." python -m unittest discover -s tests -t .
python -m compileall -q src tools examples
git diff --check
```
Expected: every command exits 0, all tests OK, and the new test file is included in the discover count.

- [ ] **Step 5: Commit**

```bash
git add src/flahax/__init__.py src/flahax/data/API_REFERENCE.md docs/conductivity.md docs/development-status.md CHANGELOG.md docs/audit/2026-10-17-flahax-vs-horticalc/review.md
git commit -m "Export experimental irrigation EC API and document M1 scope"
```

M1 exit (spec section 9) is met when Task 6 Step 4 passes and the owner has signed off the Table 1 transcription.
