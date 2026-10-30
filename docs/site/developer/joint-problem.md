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
or alkalinity correction. Whoever supplies the data must establish the water/proton inventory;
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


## Qualification evidence and lower bounds

`tools.qualify_joint_fit.qualify_starts` records every supplied start and independently
recomputes nutrient totals and objective values using rational arithmetic on the
actual binary input coefficients. A failed start remains in the report even when
another start succeeds. A solver success flag cannot substitute for these checks.
The utility returns `accepted=False` and does not change production planning.

For nonnegative source coefficients, the unavoidable water-only objective bound is

```text
L_water = sum_(target_i > 0) (max(0, water_i - target_i) / target_i)^2
```

This is a lower bound on the original objective, not a relaxed target. Charge,
phase and other constraints can make the actual optimum larger. The report exposes
the achieved objective and gap to this bound; neither multistart agreement nor a
small gap is reported as a proof of global optimality. Exact zero-target and maximum
violations are checked separately using rational nutrient totals.

The numerical qualification gate requires all supplied starts to meet the explicit
caller criteria. An incomplete search, invalid start or independent accounting
failure produces `qualification_incomplete`. This utility deliberately does not
assign physical suitability, approve production thresholds, or replace the public
workflow. Full-corpus qualification and production integration remain incomplete
until their evidence and the numerical-policy review gate are satisfied.


`relaxed_objective_bound` also constructs a nutrient-only nonnegative least-squares
relaxation. A numerical NNLS residual proposes a dual vector; rational arithmetic
then shifts it until every dual inequality is satisfied exactly. The verified dual
objective supplies the bound. The NNLS primal objective alone is never called a
lower bound. Charge, phase and upper constraints are omitted, so the bound remains
valid for the more restrictive joint problem. A positive bound proves that an
exact-target gate is unattainable; it does not prove that no useful best-fit recipe
exists. Such cases require independently qualified constrained-optimum stopping
criteria, not larger target allowances.


## Nonzero best-fit results

A crop's unchanged targets can have a strictly positive minimum nutrient loss.
`objective_gap_tolerance`, when explicitly supplied to `solve_joint_problem`,
bounds **loss minus a verified lower bound**, in the same dimensionless squared
relative-error units as L. It does not replace `loss_tolerance` or permit a hard
limit violation. `bounded_best_fit` requires a rational dual certificate, exact
linear feasibility, charge closure and fresh final evaluation. The certificate
includes its rational dual vector and upper-bound multipliers for independent
verification. Charge and phase equations are omitted only from the lower-bound
relaxation; the emitted candidate must still satisfy the actual equations.

An optional second route reports `stationary_point`. Callers must supply both
`stationarity_tolerance` (relative first-order KKT residual) and
`active_bound_tolerance` (bound distance in dose-scaled variables). Finite-difference charge sensitivities must pass their step-size agreement checks;
the optional equilibrium-equation method has the separate verification described below. A nonnegative multiplier fit
checks the nutrient gradient, free charge multiplier, active bounds and
complementarity. A fresh final evaluation must match the checked point and pass
charge and exact linear feasibility. This is a numerical first-order result;
it is **not** a proof of a local minimum, a global optimum, or physical suitability.
All three candidate statuses retain `accepted=False` and `globalOptimalityProven=False`.

For these opt-in modes, the trial subproblem treats linearized charge as an equality.
A bracketed scalar dual search computes its step; an L1 merit penalty larger than
the recovered multiplier governs backtracking. Failure to bracket or resolve the
subproblem is a failed local step, never an infeasibility certificate. Charge
finite differences are checked separately from nutrient derivatives, refined by
halving within the supplied search budget, and Richardson-extrapolated. Diagnostics
identify unresolved source columns and the actual difference steps. No inventory
permission, target, chemical coefficient or hard limit is changed by these methods.

`verify_objective_certificate` checks the exact dual inequalities without running
an optimizer. `verify_stationarity` separately recomputes exact nutrient gradients
and charge derivatives at smaller steps. Qualification retains failures and
labels the solver result; first-order verification does not upgrade it to an
optimality proof. Production planning does not adopt any of these numerical
thresholds automatically. Existing calls that omit the optional controls continue
to use the exact-target stopping contract.

For an opt-in joint subproblem step, a bounded second-order charge correction can
restore the nonlinear equality before merit comparison. It prefers the reagent
coordinate when feasible and otherwise tries feasible fertilizer coordinates.
Each correction evaluates the actual blend, respects the original hard limits
and total trust-region radius, and must reduce the absolute charge residual.
Failed corrections do not certify feasibility. Coordinate fallback searches do
not run this nested correction. The caller's iteration budgets bound both paths.

Near an already charge-feasible point, floating loss accumulation and an absolute
charge penalty can hide a genuine improvement. The opt-in comparison therefore
uses the exact rational nutrient objective plus the signed equality-multiplier
term while both points meet the original charge tolerance. Outside that region,
the L1 merit remains in force. The multiplier comes from the actual linear trial,
and the linear equality search retains its closest result across the supplied
bisection budget. This changes step selection, not final residual, stationarity,
or hard-limit acceptance criteria. A Decimal bisection oracle for a constrained
quartic supplies an independent near-optimum regression.

Nutrient Jacobian columns are calculated directly from declared nutrient fractions,
final-volume dose units and target weights. Their accuracy does not depend on
charge probe size. The nonlinear charge row uses the selected sensitivity method.

The feasible-step filter may also explore a model-descent step when both endpoints
meet the caller's charge tolerance and its signed-merit increase is no greater
than `2 * abs(charge_multiplier) * charge_tolerance / charge_scale`. This is an
explicit search allowance across that feasible band, not a scientific error bound
or an acceptance certificate. Diagnostics count these as `feasibleModelSteps`.
A result still needs the unchanged independent objective-gap or stationarity
checks, exact hard constraints and fresh final charge verification.


## Implicit equilibrium sensitivities

An explicit `sensitivity_method="equilibrium"` differentiates the selected aqueous
mass-action equations, component balances, ionic strength and water activity at
fixed pH. It uses one exact rational adjoint solve to retain very small free-species
contributions in strongly chelated mixtures. The identity `q^T J^-1 B = z^T B`,
with `J^T z = q`, computes every product derivative without solving separately
for each product. Dose derivatives include the declared
final-volume/solvent-mass conversion. An absent component uses its one-sided
free-activity limit. This mode supports complete, phase-free chemistry only;
selected phases, clipping boundaries and singular systems remain unresolved.
At an active water-activity floor the water derivative is zero, consistent with
the existing model. That mathematical branch does not establish physical
applicability of a concentrated recipe.

Trial equilibrium states may reuse a prior state as an iteration seed. Final
verification always solves from a cold start and recomputes stationarity at that
fresh state. A warm-start certificate cannot stand in for this check. The
qualification utility independently differentiates species using complex steps
and solves the resulting balances with Decimal Gauss-Jordan elimination at two
precisions. It rechecks the KKT claim using those independent derivatives and
rejects a mismatched method or invalid multiplier witness.

The implicit method uses positive-curvature coordinate Newton proposals and
periodically compares them with a full coupled step (once per source-count
iterations when local steps keep improving). Both use the existing hard-constraint and charge
checks. Composition-scaled trial widths keep local probes within the current
component inventory scale; they do not impose new product limits. When a tiny
positive dose causes clipping, an exact zero-boundary trial is permitted only
within the caller's active-bound distance, with a fresh equilibrium, no increase
in exact nutrient loss, charge closure, exact linear feasibility and a resolved
one-sided derivative. Failure leaves the search incomplete.

These are opt-in search and verification methods. They do not adopt default
acceptance tolerances for the public fertilizer workflow or prove an optimum.


For correlated nutrient sources, `curvature_block=True` may be supplied with
`"equilibrium"` sensitivities. A two-source tangent probe estimates a symmetric
curvature matrix; a block proposal requires positive diagonal curvature and a
positive determinant. Every actual trial still undergoes the original nonlinear
charge and hard-limit checks. Unresolved, indefinite or rejected block proposals
fall back to the coordinate proposal. This option defaults to false and does not
change the final stationarity threshold. A separate Decimal cubic-root witness
checks a correlated-source nonlinear optimum.


Charge-pivot and paired-source selection use the caller's existing
`active_bound_tolerance`. A positive dose within that lower-bound distance is
not treated as a freely adjustable charge pivot. This prevents microscopic
positive reagent doses from limiting every tangent step to negligible movement.
The quantity remains in the material inventory: this search decision neither
rounds it to zero nor changes final feasibility or stationarity criteria. An
independent constrained-circle optimum verifies this boundary behavior.


A warm-start candidate that loses charge closure during final cold verification
may receive a bounded correction evaluated only with cold equilibrium solves.
The correction prefers interior source coordinates, respects the original hard
constraints and trust radius, and must reduce the absolute charge residual.
The caller's backtracking budget bounds this correction. Diagnostics record
`finalColdCorrections`. All final nutrient rows, objective bounds and stationarity
checks use the corrected quantities and cold state. If those checks fail, the
result remains `search_incomplete`; no tolerance is widened. A retained full-
catalogue melon/water regression independently checks this failure and correction.

When a reagent bound prevents charge restoration, the explicit equilibrium
path also tests bounded fertilizer-coordinate corrections. Each trial must
satisfy the original hard limits and decrease the actual nonlinear charge
residual. Among corrections that at least halve that residual, the solver
chooses the lowest nutrient loss; otherwise it chooses the greatest charge
reduction. These are feasibility-restoration steps, not optimum certificates.
The original charge tolerance and independent final verification still apply.


## Public joint workflow

`plan_fertilizer_workflow(..., ph_adjustment={..., "joint": config})` routes every
offered reagent through the qualified joint solver. Initial recipe pH does not
exclude a reagent in this mode. Supply all of these `config` fields:

- `solvent_mass_kg`: final solvent inventory, equal to `equilibrium.water_mass_kg`.
- `reagent_solvent_fractions`: reagent ID to explicitly declared solvent mass fraction.
- `maximum_reagent_mass_g`: reagent ID to hard product-mass cap. The existing
  `maximum_reagent_volume_litres` is also enforced.
- `controls`: the explicit `solve_joint_problem` keyword controls, or a mapping
  from reagent ID to its controls. Each dose-step map names exactly that
  candidate's fertilizer IDs and reagent ID.

Optional `starting_points` maps reagent IDs to records containing
`fertilizer_doses` (product g/L) and `reagent_dose` (product g/L). These are search
seeds, not accepted recipes. Every candidate receives the same final cold charge,
hard-limit and independent calculated-pH checks. Without a supplied start, the
existing nutrient recipe and zero reagent initialize the search. Budget exhaustion
is unresolved search, not proof of infeasibility.

The public adapter rebuilds nutrient rows, unmet-target diagnoses, product IDs,
material inventory and requirement conflicts from the actual quantities. Reagent
nutrients enter once as supply; reagent mass, volume and molality use the declared
final-volume/solvent basis. The ordinary nutrient and saturation gates remain in
force. A stationary or best-fit result can require review or be rejected. The
candidate's `joint_result` records numerical status, quantities, controls and
charge residual; it never asserts global optimality or dosing authorization.

Legacy calls retain sequential fitting when a reagent in the initial required
direction is offered. When none is offered and phase-free water chemistry is
available, a bounded zero-reagent joint search may recover a nutrient-feasible
fertilizer allocation. Its reagent mass is fixed to zero, so the calculation does
not infer solvent content from an unspecified assay remainder. Failed recovery
remains explicit in `joint_result`; it is not a global direction impossibility.

The adopted legacy recovery policy uses 1e-4 g/L dose scales, 0.001 mol/kg charge
scaling, 2e-12 mol/kg charge closure, 1e-16 squared relative nutrient loss, 0.01
relative derivative agreement, a scaled trust radius of 10000, 20 iterations and
20 backtracks. It enables neither best-fit nor stationarity stopping. These are
bounded search/verification settings, not physical tolerances. The existing
0.001 pH final gate and nutrient acceptance thresholds are unchanged. This automatic recovery policy was approved on 2026-10-27 after numerical-policy
review; explicit joint mode uses caller-supplied settings.
