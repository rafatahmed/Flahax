# Joint fertilizer and reagent problem

This contract evaluates one fixed fertilizer/reagent vector. It is groundwork for
the joint optimizer, not a replacement for the existing sequential planner.
`make_joint_problem` compiles supplied fertilizer records and one sourced reagent
into immutable `JointProblem` and `JointSource` records. Unknown product IDs and
duplicate fertilizer/reagent identities are rejected; no catalogue stock is added.
The caller selects an eligible inventory and explicit reagent. The adapter rejects
pH reagent records used as fertilizer variables. It does not grant stock or chemical
permission merely because a product has coefficients.

## Variables, basis and objective

For fertilizer doses x_j and reagent product dose q in g/L final solution, with
nutrient fractions a_ij and b_i in g/g product:

```text
C_i [mg/L] = water_i + 1000 sum_j(a_ij x_j) + 1000 b_i q
L = sum_(target_i > 0) ((C_i - target_i) / target_i)^2
batch product mass [g] = dose [g/L] * V [L]
T_k [mol/kg solvent] = water_component_k + (V/W) sum_s(component_ks * dose_s)
```

V is final litres, W is **final** kg solvent, and component coefficients are mol/g
of the actual product, including the reagent assay. The compiler converts active
reagent fraction once using its molar mass. Nitrogen forms remain separate. Product
carrier/hydrate solvent is not inferred. `JointSource.solvent_fraction` declares
solvent g/g product; `make_joint_problem` requires an explicit reagent solvent
fraction, while its fertilizer records declare none. Use explicit sources when
fertilizer solvent is known. Source-water component totals must already use the
same final-solvent basis. Source-water mg/L remains a separate measured input.

Neither a missing density nor an unknown composition becomes zero. With no density,
reagent volume is None and a requested volume cap is rejected. Mass limits still
apply. The total declared product solvent cannot exceed W; W is not increased a
second time when reagent solvent is added.

## Constraints and residuals

All doses are finite and nonnegative, including exact zero. Explicit zero targets
and maxima are hard constraints outside the objective. Target/maximum contradictions,
reagent mass/volume caps and final solvent/volume violations are reported explicitly.
There is no hidden positive dose floor or initial-direction rejection in this
fixed-candidate contract. A failed initial recipe therefore cannot prove every
joint allocation impossible. Positive-target fit acceptance remains a separate
qualified policy; the evaluator does not introduce a tolerance.

For complete declared components, the existing pinned aqueous model solves mass
action and component conservation at the fixed target pH and explicit selected
phases. Its returned equilibrium object retains component residuals, species,
precipitated amounts, saturation indices, numerical diagnostics and model limitations.
The charge/proton closure residual is:

```text
R_charge = equilibrium.charge_balance - reference_charge_mol_per_kg
```

The reference charge is a mandatory explicit input on the same W basis, never
inferred from a nutrient subtotal. Protons/hydroxide are implicit in the reagent's
conserved-component representation. Do not separately add a second acid equivalent
or alkalinity correction. The data owner must establish the water/proton inventory;
a declared empty water-component map means known absence, not unknown chemistry.

`nutrientComponentDifference` discloses differences between analytical nutrient
accounting and component-derived amounts; it is None when chemistry is missing.
It is diagnostic, not a tolerance waiver.
Analytical nutrient totals do not silently become dissolved nutrient claims when
solids occur. Model-domain and phase-policy acceptance must be evaluated separately.

## Evaluate a candidate

```python
from flahax import JointProblem, JointSource

problem = JointProblem(
    fertilizers=(), reagent=JointSource("none", {}, {}),
    targets={"K": 0}, water={}, water_components={},
    final_volume_litres=100, solvent_mass_kg=100,
    target_ph=7, reference_charge_mol_per_kg=0,
    maximum_reagent_mass_g=0,
)
result = problem.evaluate({}, 0)
assert result["loss"] == 0
assert result["violations"] == []
```

`requires_joint_acceptance` means evaluated, **not accepted**. `missing_chemistry`
means water components or a positively dosed source lacks component data. A missing
source at exactly zero dose does not contaminate known chemistry. Nonconvergence
and invalid numerical/model inputs propagate as explicit errors; they are never
replaced with a successful undosed recipe. The inputs are snapshotted and immutable.

## Relationship to current planning paths

- `ph_adjustment` supplies the inventory compiler and the existing per-reagent
  sequential search. The new evaluator does not yet replace that search.
- `acid_selection` evaluates fixed-recipe acid candidates; its molal doses map to
  q by dose_molal * W * molar_mass / active_fraction / V.
- `equilibrium_delivery` converts molal reagent into batch mass/volume. Its existing
  nitrate-N assay convention must be converted to product mass fractions, not
  confused with active acid fraction.
- `ph_planning` uses measured titration demand in meq/L. That observation cannot
  silently substitute for complete analytical water or an equilibrium proton equation;
  it remains a separate measured constraint until an explicit adapter is qualified.

Production integration and acceptance qualification follow in later work. No new chemical constants, phase
policy, empirical tolerance or physical validation claim is introduced here.


## Safeguarded joint numerical search

`solve_joint_problem` searches fertilizer doses and the selected reagent dose together.
It takes a `JointProblem`, an initial fertilizer dose mapping and reagent dose in
g/L, and requires every numerical control explicitly:

- `dose_steps`: positive g/L scales for every supplied product ID;
- `charge_scale`: positive mol/kg scale for the charge term in the search merit;
- `charge_tolerance`: positive mol/kg final charge residual bound;
- `loss_tolerance`: nonnegative bound on the original nutrient loss L;
- `sensitivity_tolerance`: positive relative agreement criterion for derivatives
  evaluated at h and h/2;
- `trust_radius`: positive infinity-norm step bound in dose-scaled coordinates;
- `max_iterations` and `max_backtracks`: positive integer search budgets.

These inputs are numerical controls, not newly qualified production acceptance
thresholds. Test settings are verification settings for their stated witnesses.
The search merit is L + (R_charge / charge_scale)^2. A merit decrease alone never
qualifies a result: both final residual bounds must pass independently.

Nonnegativity, explicit zero targets, nutrient maxima, reagent mass/volume and
solvent inventory define linear feasible steps. Trial roundoff violations are
rejected. Finite differences are checked for agreement before rank-aware NNLS
proposes a local step. Backtracking and coordinate/cap-tangent exchanges provide
fallbacks when a local step is unusable. Product exchanges always reevaluate the
full immutable problem; they do not reuse a previous recipe's chemistry.

`numerical_candidate` means a fresh final evaluation satisfies the supplied
numerical criteria and hard constraints. It always includes `accepted=False`:
model applicability, dissolved versus analytical nutrients, phase policy and
production acceptance are separate obligations. `search_incomplete` means the
initial evaluation failed, final verification failed, or the search budget ended
without meeting the criteria. It is not proof of infeasibility. Diagnostics expose
rejected trials, failed sensitivities, linear-solver records and evaluation counts.
Invalid input controls raise `DeliveryError`; scaling overflow is an explicit
numerical error. Missing chemistry and failed trial solves cannot produce success.

This local search does not certify global optimality or enumerate additional
reagents. It does not yet replace the sequential planner. Use only the permitted
inventory supplied in the problem; permission and production integration remain
with the calling workflow.
