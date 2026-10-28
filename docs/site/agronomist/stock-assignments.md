# Condition-qualified stock assignments

## Prepare an equipment-constrained plan

`group_tanks(salts, products, rules=(), max_tanks=None)` searches for a minimum
separation layout. It includes the magnesium/phosphate prohibition and applies
sulfate/phosphate screens to micronutrients without a small-dose waiver. Element
classes are conservative: an absence of a graph conflict is not solubility evidence.
Versioned caller rules add hard separations. Their bans are conservatively retained
outside temperature bounds rather than inverted into permission.

Set `max_tanks` to the available count. An impossible graph raises `too_many_tanks`;
a search-budget interruption raises `stock_search_limit`, not a claim of
infeasibility. Reagent-role products stay on their own channel. The report defaults
to two available tanks; a three-tank requirement blocks preparation and remains
visible. `available_tanks` changes this report equipment count, not chemistry.
For actual capacities and arbitrary tank IDs, use `plan_stocks` with `StockTank`
objects, injection ratio, final recipe volume, source limits and rules.

The frozen calcium / magnesium-sulfate / phosphate example previously put the
last two products together to fit two tanks. Its graph is a triangle: all three
pairs conflict, so its minimum is three tanks. The independent graph oracle proves
this count without changing the original input or any solubility number.

## Separate a layout from mixture qualification

`plan_stocks` checks capacity, per-product limits and separations, then evaluates
candidate layouts in increasing tank count and tank-ID order. With no mixture
model it returns the first structural layout with `status='requires_review'` and
`mixture_approved=False`. It does not turn single-product limits into common-ion
or mixed-stock validation. No built-in dilute-solution model is silently extended
to concentrated stocks.

Provide a callable `mixture_model(tank_plan, temperature)` to evaluate each used
tank. Each compatible result must contain:

- `status='compatible'`, `reviewed=True`, nonempty `model_id`, `source`, `revision`
  and `review_id`;
- exact `product_ids` identifying the reviewed grades, and exact
  `evaluated_concentrations_g_per_l` keyed by those IDs;
- `basis='g_per_l_stock_solution'`, `temperature_min_c`, `temperature_max_c`,
  `ionic_strength`, `ionic_strength_max`, `total_concentration_max_g_per_l`;
- `mass_balance_verified=True` from the model's reviewed balance check.

The bounds must cover the evaluated stock. Missing review or a domain mismatch
returns unsupported qualification. Malformed model results raise a diagnostic.
The model may return `incompatible` or `not_supported` with a reason; neither
approves a mixture. The callback owns composition-specific applicability,
thermodynamics, grade identity and balance tolerances. Metadata is a caller
assertion, not independently authenticated evidence. No physical thresholds or
new constants are supplied by this interface.

Known mixture rejection triggers search of alternatives, including separated
stocks. Unknown model support remains unknown. `max_assignments` bounds the work;
a returned fallback has `search_complete=False` on exhaustion. `assignments_evaluated`
and per-tank `mixture_assessments` expose what was evaluated. A fallback is never
approved. If every candidate is rejected, the planner reports `no_stock_assignment`.

## Review downstream use

The fertilizer workflow labels unqualified stock layouts `requires_review`.
Delivery state transitions refuse `validated` without mixture qualification, even
when pH and pump records exist. Equipment changes, operator acknowledgement and
single-product screening cannot remove this gate. Reported structural alternatives
are not preparation instructions.

Tests compare all 64 four-vertex graphs with an independent exhaustive coloring
oracle, verify exact product mass conservation after splitting, and use a clearly
synthetic common-ion rejection witness to exercise alternative search. That witness
is not experimental validation or a physical common-ion model. Physical validation
remains a separate later stage; unsupported stock domains stay explicitly unsupported.
