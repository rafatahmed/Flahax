# Fixed-ratio allocation reliability matrix

The N1 regression matrix uses the public `plan_ratio_recipe` interface. Run:

```console
python -m unittest tests.test_ratio_allocation_reliability
```

The matrix contains twelve distinct cases: four feasible strengths (1.0, 1.1,
1.2 and 1.26 mmol/L), four independently infeasible inventories, and four boundary
or degenerate cases. The redundant calcium-nitrate case is feasible, making five
feasible cases and seven infeasible cases in total. Every feasible case runs six
distinct product orderings: original, reversed, two rotations and two seeded
shuffles. The full suite therefore performs 37 public recipe evaluations.

Each feasible evaluation retains the 5% nutrient reserve, all nine ceilings,
128 preparation scenarios, original weighing/assay/water/volume/density/solvent
bounds and adaptive saturation checks over pH 6.28-6.32. This is an intentionally
expensive integration test; it does not mock chemistry or omit uncertainty.
Named boundary cases tighten a ceiling or alter a target/source availability.
They do not relax the reference recipe's acceptance policy.

## Independent allocation evidence

`tests/ratio_allocation_cases.py` builds a separate nominal allocation witness:
four independent equivalent-ratio equations plus the six-nutrient count determine
a one-parameter dose family. A pivoted Gaussian elimination and scalar charge
bisection find a nonnegative witness. Neither FlahaX's allocator, its nonnegative
least-squares routine nor its root-finding routine is used by this oracle.

The oracle shares material interpretation and the aqueous chemistry model. It
therefore supplies an independent allocation method, not independent
thermodynamics or independent uncertainty-envelope proof. Full uncertainty
acceptance is separately exercised through the public recipe workflow. Independent
PHREEQC comparisons for uncertainty witnesses are a separate validation stage.

Infeasibility is established by necessary inventory constraints: a positive
required share with no nutrient supply and a positive companion ion, water above
a reserved ceiling, a zero share with positive water contribution, or source
water exceeding the entire requested count. The test checks those certificates;
a local allocation error alone is never treated as proof of infeasibility.

Valid allocations need not have identical ingredient masses when sources are
redundant. The tests require conserved inventory and passing final constraints.
The public API does not expose allocator initial guesses, so starting-point
sensitivity is not covered by this matrix. These cases do not establish global
feasibility, all possible product-order behavior, or physical recipe stability.

## Redundant-product correction

Issue #248 records a reproducible false negative: four of six orderings of the
redundant calcium-nitrate case failed before verification, while the other two
passed every check. The linear least-squares proposal was accurate, but separate
finite-difference steps gave chemically identical dose directions different charge
derivatives. This allowed artificial dose transfers and stalled the pH correction.

The allocator now computes one charge derivative per exactly identical component
vector, using the total dose in that direction for the step scale. Product columns,
assay constraints, solvent constraints, output records and all preparation
uncertainties remain separate. No acceptance tolerance was changed. Equivalent
chemistry is not treated as equivalent supplier evidence.
