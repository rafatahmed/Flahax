# Materials identity audit, 2026-10-18: maintainer review

The audit itself is [data/materials-audit.csv](data/materials-audit.csv), kept
as received. It compares each of the 28 catalogue products with a named
reference material: identity, formula, molecular weight, CAS number,
hydration, assay basis and impurity limits. It also recomputes the
theoretical nutrient analysis from the catalogue formula. Reference
products (Sigma-Aldrich, Merck, Haifa, Yara, Nouryon, Thermo) are
**comparators for chemical identity**, not the materials FlahaX users buy.

## Position

Catalogue size does not measure chemical coverage or model accuracy.
FlahaX's chemistry approach uses explicit chemical identities and
composition assumptions. Its raw-material catalogue should distinguish
chemical identity from supplier grade and batch assay, with traceable
specifications and impurity information. Multiple commercial products may
represent the same underlying chemical source.

A factory blend has a declared nutrient analysis, but its exact
ingredients, proportions, counterions or additives may be incomplete or
undisclosed. Some manufacturers do disclose ingredients, so this varies by
product. Equilibrium chemistry needs that composition. A declared analysis
alone supports a mass balance, but not speciation, precipitation or pH.

## Results

| Status | Products |
|---|---|
| Identity consistent | 15 |
| Chelate identity incomplete | 6: Copper EDTA, Iron DTPA, Iron EDDHA, Iron EDTA, Mn EDTA, Zn EDTA |
| Metadata correction | 2: Iron II Sulfate ("Hepahydrate" → heptahydrate), Urea (formula text) |
| Unresolved blend | 1: CH - micro |
| Commercial profile needs provenance | 1: Calcium Nitrate (ag grade) |
| Formula/assay conflict | 1: Mg Nitrate |
| Concentration/assay conflict | 1: Phosphoric Acid (75%) |
| Hydration must be explicit | 1: Potassium Citrate |

**No product has a supplier grade or batch assay** (`actual_FlahaX_supplier_grade_lot`
is "not specified" for all 28). Every catalogue analysis is a declared or
theoretical figure, not a purchased-material certificate.

## Independent confirmation from the irrigation EC work

The irrigation EC module (M1, 2026-10-18) computes each product's assay
charge residual from its declared ion forms. It was written without
reference to this audit. Run on 1 g/kgw of each product:

| Audit status | Charge residual |
|---|---|
| Identity consistent (15) | all within ±0.025 % |
| Mg Nitrate, formula/assay conflict | +0.553 %: the N:Mg ratio is not that of Mg(NO₃)₂ |
| Calcium Nitrate, commercial profile | −0.068 %: a consistent commercial analysis, not the ideal double salt |
| Chelates (6), identity incomplete | −14 % to −33 %: no sodium or other counterion is declared, so each chelate carries net negative charge |
| CH - micro, unresolved blend | −12.8 % |
| Borax | +100 % (see below) |

The two methods agree. Every product the audit marks consistent passes the
0.1 % charge rule; every identity problem the audit names shows up as a
charge residual. This is why calculated-mode EC rejects recipes that
contain chelates or Mg Nitrate.

## Findings the audit adds or sharpens

1. **Phosphoric Acid (75%) overstates P by about 33 %.** The catalogue
   lists 31.61 % P, the pure-acid value. A 75 % w/w solution is about
   23.71 % P. This was already noted in
   [water-to-delivery.md](../../../guide/water-to-delivery.md) but remains in the
   data. It changes recipe doses, not only labels.
2. **Chelates lack counterions and grade definitions.** Catalogue metal
   percentages are grade assays, not identities. For example, dry NaFeEDTA
   is about 15.2 % Fe, so 13 % Fe needs a declared hydration and sodium
   content. Fe-EDDHA total Fe and o,o-bound Fe differ (Rexolin Q48: 6 %
   versus 4.8 %).
3. **Mg Nitrate's formula and analysis disagree.** The formula is anhydrous
   but the analysis looks hydrated, and the N:Mg ratio fits neither exactly.
4. **Borax's declared chemistry is incomplete (found here, not in the
   CSV).** The audit rates borax "identity consistent" on mass. FlahaX
   declares it as Na⁺ plus B(OH)₃, which leaves the sodium with no anion.
   In water, borax gives 2 Na⁺ + 2 B(OH)₄⁻ + 2 B(OH)₃. The ion forms
   need correcting.
5. **CH - micro is a project assumption**, not an identified product. It
   should not be presented as a raw material.

## Consequences

- Supplier grade and batch assay become explicit, separate inputs. The
  catalogue entry keeps chemical identity; a grade or lot record carries
  the measured or certified assay, hydration, counterions and impurity
  limits, with its source document.
- Material-level corrections (findings 1–4) change numbers and need their
  own reviewed change with regression evidence. None is made by this review.
- Resolved by the traceable-catalogue change (branch `feat/traceable-catalogue`): identity,
  grade and lot layers ([materials](../../../guide/materials.md)); Mg Nitrate D1, phosphoric acid 75 %,
  chelate sodium D2 and the borax declared form.

## Source

Audit file received 2026-10-18, accessed dates per row. Reference URLs are
in the CSV; manufacturer documents are not stored in the repository.
