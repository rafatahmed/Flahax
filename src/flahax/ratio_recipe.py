# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Six-nutrient fixed-ratio recipes including explicit source water and
pH reagents.
"""

from .aqueous_model import solve
from .composition import ATOMIC, parse_formula
from .delivery_contracts import DeliveryError
from .inputs import number
from .root_finding import shrink_bracket
from .saturation_policy import assess_saturation
from .ratio_verification import verification_options, verify_rounded_recipe

RATIO_INPUT = "invalid_ratio_input"

NUTRIENTS = ("K", "Ca", "Mg", "NO3", "P", "SO4")
BASIS = ("K+", "Ca+2", "Mg+2", "NO3-", "PO4-3", "SO4-2")
CHARGES = (1, 2, 2, 1, 1, 2)
# Stoichiometric contributions per mole of each pure compound, in
# NUTRIENTS order.
SOURCES = (
    ("KH2PO4", (1, 0, 0, 0, 1, 0)),
    ("Ca(NO3)2.4H2O", (0, 1, 0, 2, 0, 0)),
    ("MgSO4.7H2O", (0, 0, 1, 0, 0, 1)),
    ("Mg(NO3)2.6H2O", (0, 0, 1, 2, 0, 0)),
    ("KNO3", (1, 0, 0, 1, 0, 0)),
    ("KOH", (1, 0, 0, 0, 0, 0)),
)


def _shares(values, name):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise DeliveryError("invalid_ratio_input", f"{name} requires three shares")
    values = [number(v, name, minimum=0.0, code=RATIO_INPUT) for v in values]
    largest = max(values)
    if largest == 0:
        raise DeliveryError("invalid_ratio_input", f"{name} must have a positive total")
    scaled = [v / largest for v in values]
    return [v / sum(scaled) for v in scaled]


def plan_ratio_recipe(
    *,
    cation_shares,
    anion_shares,
    ph,
    counted_mmol_l,
    volume_litres,
    water,
    water_mass_kg,
    ph_range=None,
    selected_phases=None,
    mass_decimals=5,
    saturation_margin=0.0,
    uncertainty=None,
    stock_dosing=None,
    stock_evidence=None,
    batch_stability=None,
    ph_reagents=None,
    products=None,
    maximum_concentrations=None,
    nutrient_ceiling_reserve=0.0,
):
    """Return a full-precision pure-salt recipe and its modeled
    chemistry.

    Ratios use charge equivalents and total phosphate reported as H2PO4.
    Strength sums six analytical mmol/L quantities. Explicit final water
    mass converts concentrations to mol/kg for the supported 25 C
    aqueous model. The allocation supports SOURCES plus explicitly
    permitted HNO3. Water nutrients and both pH reagents count toward
    the final analytical targets.
    """
    from .ratio_products import validate_limits

    analysis_mode = isinstance(uncertainty, dict) and uncertainty.get("mode") in (
        "water_product",
        "water_product_elemental",
    )
    limits = validate_limits(maximum_concentrations)
    reserve = number(
        nutrient_ceiling_reserve, "nutrient_ceiling_reserve", minimum=0.0, code=RATIO_INPUT
    )
    if reserve >= 1 or (reserve and not limits):
        raise DeliveryError(
            "invalid_nutrient_reserve",
            "Nutrient reserve must be below 1 and a positive reserve requires declared ceilings",
        )
    reserve_report = {
        "fraction": reserve,
        "declared_maximum_concentrations": dict(limits),
        "effective_maximum_concentrations": {k: v * (1 - reserve) for k, v in limits.items()},
        "qualification": "An explicit operating reserve applied to complete rounded and uncertain "
        "inventories, in addition to preparation uncertainty. Not a validated crop safety limit.",
    }
    limits = dict(reserve_report["effective_maximum_concentrations"])
    if (
        "N_NH4" in limits
        and isinstance(water, dict)
        and (
            not isinstance(water.get("totals_mol_kg"), dict)
            or "NH4+" not in water["totals_mol_kg"]
        )
    ):
        raise DeliveryError(
            "missing_water_ammonium",
            "An ammonium limit requires explicit source-water NH4+, including a justified zero",
        )
    if products is not None:
        if ph_reagents is not None:
            raise DeliveryError(
                "ambiguous_ratio_reagents",
                "Declare pH reagents in products or ph_reagents, not both",
            )
        if not analysis_mode and (uncertainty is not None or stock_dosing is not None):
            raise DeliveryError(
                "unsupported_ratio_product_uncertainty",
                "Commercial-product uncertainty and stock verification are not yet supported",
            )
    allowed_reagents = ["KOH"] if ph_reagents is None else ph_reagents
    if (
        not isinstance(allowed_reagents, (list, tuple))
        or not allowed_reagents
        or any(not isinstance(r, str) or r not in ("KOH", "HNO3") for r in allowed_reagents)
        or len(set(allowed_reagents)) != len(allowed_reagents)
    ):
        raise DeliveryError("invalid_ph_reagents", "Select unique KOH and/or HNO3 reagents")
    if (
        water != "demineralized"
        and not analysis_mode
        and (uncertainty is not None or stock_dosing is not None)
    ):
        raise DeliveryError(
            "unsupported_ratio_water_uncertainty",
            "Real-water uncertainty and stock verification are not yet supported",
        )
    if "HNO3" in allowed_reagents and (uncertainty is not None or stock_dosing is not None):
        raise DeliveryError(
            "unsupported_ratio_reagent_uncertainty",
            "Nitric-acid uncertainty and stock verification are not yet supported",
        )
    if batch_stability is not None and stock_dosing is None:
        raise DeliveryError(
            "missing_stock_dosing", "Batch stability requires stock preparation evidence"
        )
    if stock_evidence is not None and stock_dosing is None:
        raise DeliveryError("missing_stock_dosing", "Stock evidence requires stock dosing")
    if stock_dosing is not None and not analysis_mode:
        from .ratio_stocks import validate_stocks

        validate_stocks(stock_dosing, [formula for formula, _ in SOURCES])
        if uncertainty is None:
            raise DeliveryError("missing_uncertainty", "Stock dosing requires uncertainty bounds")
    if uncertainty is not None:
        from .ratio_uncertainty import validate_uncertainty

        if analysis_mode:
            from .ratio_analysis_uncertainty import validate_analysis_uncertainty

            validate_analysis_uncertainty(uncertainty, volume_litres, products, water)
            if stock_dosing is not None:
                from .ratio_product_stocks import validate_product_stocks
                from .ratio_products import product_sources

                validate_product_stocks(stock_dosing, product_sources(products), uncertainty)
                if stock_evidence is not None or batch_stability is not None:
                    raise DeliveryError(
                        "unsupported_product_stock_evidence",
                        "Product stocks support numerical assessment only; "
                        "lab testing is deferred",
                    )
        else:
            validate_uncertainty(uncertainty, volume_litres, stock_mode=stock_dosing is not None)
        if ph_range is None:
            raise DeliveryError("missing_ph_range", "Uncertainty checks require ph_range")
    cations = _shares(cation_shares, "cation_shares")
    anions = _shares(anion_shares, "anion_shares")
    ph = number(ph, "ph", minimum=0.0, code=RATIO_INPUT)
    if ph > 14:
        raise DeliveryError("invalid_ratio_input", "ph must be between 0 and 14")
    saturation_margin = number(
        saturation_margin, "saturation_margin", minimum=0.0, code=RATIO_INPUT
    )
    if ph_range is None and (
        selected_phases is not None or mass_decimals != 5 or saturation_margin != 0
    ):
        raise DeliveryError("missing_ph_range", "Rounding verification requires ph_range")
    phases = (
        verification_options(ph, ph_range, selected_phases, mass_decimals)
        if ph_range is not None
        else None
    )
    strength = number(counted_mmol_l, "counted_mmol_l", positive=True, code=RATIO_INPUT)
    volume = number(volume_litres, "volume_litres", positive=True, code=RATIO_INPUT)
    water_mass = number(water_mass_kg, "water_mass_kg", positive=True, code=RATIO_INPUT)
    from .ratio_water import account_water

    water_report = account_water(water, volume, water_mass)
    water_amounts = [water_report["nutrients_mmol_l"][n] for n in NUTRIENTS]
    reference_charge = water_report["reference_charge_mol_kg"]
    from .ratio_products import (
        plan_products,
        water_totals,
        elemental_from_totals,
        limit_assessment,
    )

    water_elements = elemental_from_totals(
        water_totals(water_report, volume, water_mass), volume, water_mass
    )
    if not limit_assessment(water_elements, limits)["passed"]:
        raise DeliveryError(
            "ratio_limit_exceeded", "Source water exceeds a stated nutrient maximum"
        )
    if products is not None:
        result = plan_products(
            products, cations, anions, ph, strength, volume, water_mass, water_report, limits
        )
        result["nutrient_ceiling_reserve"] = reserve_report
        return _finish_recipe(
            result,
            ph_range,
            phases,
            mass_decimals,
            saturation_margin,
            uncertainty,
            stock_dosing,
            stock_evidence,
            batch_stability,
        )
    concentration_factor = volume / water_mass / 1000
    weights = cations + anions
    cation_count = sum(v / z for v, z in zip(cations, CHARGES[:3]))
    anion_count = sum(v / z for v, z in zip(anions, CHARGES[3:]))

    def amounts(cation_total):
        anion_total = max(0.0, (strength - cation_count * cation_total) / anion_count)
        group_totals = [cation_total] * 3 + [anion_total] * 3
        return [v * total / z for v, total, z in zip(weights, group_totals, CHARGES)]

    def aqueous_totals(values):
        return dict(
            water_report["background_totals_mol_kg"],
            **{key: v * concentration_factor for key, v in zip(BASIS, values)},
        )

    def state(values):
        return solve(aqueous_totals(values), ph)

    def charge(cation_total):
        return state(amounts(cation_total)).charge_balance - reference_charge

    low, high = 0.0, strength / cation_count
    low_charge, high_charge = charge(low), charge(high)
    if low_charge * high_charge > 0:
        raise DeliveryError(
            "ratio_infeasible", "Ratios and strength cannot balance charge at this pH"
        )
    low, high = shrink_bracket(charge, low, low_charge, high, high_charge, width=1e-11)
    target = amounts((low + high) / 2)
    additions = [t - w for t, w in zip(target, water_amounts)]
    if any(v < -1e-10 for v in additions):
        raise DeliveryError(
            "ratio_water_exceeds_target",
            "Source water already exceeds a final nutrient target; reduce source water "
            "or change targets",
        )
    potassium, calcium, magnesium, nitrate, phosphate, sulfate = additions
    magnesium_nitrate = magnesium - sulfate
    available_nitrate = nitrate - 2 * (calcium + magnesium_nitrate)
    available_potassium = potassium - phosphate
    potassium_nitrate = min(available_nitrate, available_potassium)
    koh = max(0.0, available_potassium - available_nitrate)
    acid = max(0.0, available_nitrate - available_potassium)
    if (koh > 1e-10 and "KOH" not in allowed_reagents) or (
        acid > 1e-10 and "HNO3" not in allowed_reagents
    ):
        raise DeliveryError(
            "ratio_allocation_infeasible",
            "Required pH reagent is not permitted; explicitly select KOH and/or HNO3",
        )
    sources = SOURCES + ((("HNO3", (0, 0, 0, 1, 0, 0)),) if "HNO3" in allowed_reagents else ())
    doses = [phosphate, calcium, sulfate, magnesium_nitrate, potassium_nitrate, koh]
    if "HNO3" in allowed_reagents:
        doses.append(acid)
    if any(v < -1e-10 for v in doses):
        raise DeliveryError(
            "ratio_allocation_infeasible",
            "The specified ratios and pH require a source outside the supported "
            "salt/reagent allocation",
        )
    ingredients = []
    achieved = list(water_amounts)
    accounting = {k: dict.fromkeys(NUTRIENTS, 0.0) for k in ("salts_mmol_l", "ph_reagents_mmol_l")}
    accounting["water_mmol_l"] = dict(zip(NUTRIENTS, water_amounts))
    for (formula, stoichiometry), dose in zip(sources, doses):
        dose = max(0.0, dose)
        molar_mass = sum(ATOMIC[e] * n for e, n in parse_formula(formula)["atoms"].items())
        contribution = [dose * n for n in stoichiometry]
        achieved = [a + b for a, b in zip(achieved, contribution)]
        category = "ph_reagents_mmol_l" if formula in ("KOH", "HNO3") else "salts_mmol_l"
        for nutrient, value in zip(NUTRIENTS, contribution):
            accounting[category][nutrient] += value
        ingredients.append(
            {
                "formula": formula,
                "grams": dose * volume * molar_mass / 1000,
                "contributions_mmol_l": dict(zip(NUTRIENTS, contribution)),
            }
        )
    chemistry = state(achieved)
    if abs(chemistry.charge_balance - reference_charge) > 1e-10:
        raise DeliveryError("ratio_verification_failed", "Ingredient charge verification failed")
    equivalents = [v * z for v, z in zip(achieved, CHARGES)]
    result = {
        "schema_version": "1",
        "target_ph": ph,
        "volume_litres": volume,
        "water_mass_kg": water_mass,
        "temperature_c": 25,
        "counted_mmol_l": sum(achieved),
        "analytical_mmol_l": dict(zip(NUTRIENTS, achieved)),
        "cation_percent": [100 * v / sum(equivalents[:3]) for v in equivalents[:3]],
        "anion_percent": [100 * v / sum(equivalents[3:]) for v in equivalents[3:]],
        "ingredients": ingredients,
        "water_accounting": water_report,
        "nutrient_accounting": accounting,
        "aqueous_totals_mol_kg": aqueous_totals(achieved),
        "charge_closure_error_mol_kg": chemistry.charge_balance - reference_charge,
        "charge_residual_mol_kg": chemistry.charge_balance,
        "saturation_indices": chemistry.saturation_indices,
        "saturation_assessment": assess_saturation(chemistry),
        "qualifications": [
            "Pure compounds, explicit water inventory, 25 C and closed inorganic "
            "carbon; gas exchange is omitted.",
            "Water sodium, chloride and carbon enter chemistry but not the six- "
            "nutrient count. Measured-water charge imbalance is preserved; water- "
            "analysis uncertainty is not evaluated.",
            "Masses are full precision. Recheck delivered quantities after rounding.",
            "Analytical ratios include water, salts, KOH potassium and any HNO3 "
            "nitrate. Dissolved species depend on"
            "speciation and precipitation.",
            "Solution 1a measured pH 5.33, 6.45, 6.58; model replay approximately "
            "5.06, 6.66, 6.66.",
            "PHREEQC agrees within 0.002 pH under matched conditions. The measured "
            "0.13 pH rise remains unresolved.",
            "Saturation results describe the mixture before solid allocation; "
            "physical nutrient retention requires measurement.",
        ],
    }
    result["maximum_concentrations"] = limits
    result["nutrient_ceiling_reserve"] = reserve_report
    result["elemental_mg_l"] = elemental_from_totals(
        result["aqueous_totals_mol_kg"], volume, water_mass
    )
    result["limit_assessment"] = limit_assessment(result["elemental_mg_l"], limits)
    if not result["limit_assessment"]["passed"]:
        raise DeliveryError("ratio_limit_exceeded", "Recipe exceeds a stated nutrient maximum")
    return _finish_recipe(
        result,
        ph_range,
        phases,
        mass_decimals,
        saturation_margin,
        uncertainty,
        stock_dosing,
        stock_evidence,
        batch_stability,
    )


def _finish_recipe(
    result,
    ph_range,
    phases,
    mass_decimals,
    saturation_margin,
    uncertainty,
    stock_dosing,
    stock_evidence,
    batch_stability,
):
    delivered_grams = None
    effective_bounds = None
    product_stocks = stock_dosing is not None and result.get("product_inventory")
    if stock_dosing is not None:
        if product_stocks:
            from .ratio_product_stocks import prepare_product_stocks

            result["stock_delivery"] = prepare_product_stocks(result, stock_dosing, uncertainty)
        else:
            from .ratio_stocks import prepare_stock_delivery

            result["stock_delivery"] = prepare_stock_delivery(
                result, stock_dosing, uncertainty["volume_error_litres"]
            )
        delivered_grams = [row["effective_grams"] for row in result["stock_delivery"]["stocks"]]
        effective_bounds = result["stock_delivery"]["effective_grams_bounds"]
    if phases is not None:
        result["rounded_verification"] = verify_rounded_recipe(
            result,
            ph_range,
            phases,
            mass_decimals,
            saturation_margin,
            delivered_grams=delivered_grams,
        )
    if product_stocks:
        for row, bounds in zip(result["rounded_verification"]["ingredients"], effective_bounds):
            row["stock_product_mass_bounds_g"] = [bounds[0], bounds[-1]]
    if uncertainty is not None:
        from .ratio_uncertainty import verify_uncertainty

        if uncertainty.get("mode") in ("water_product", "water_product_elemental"):
            from .ratio_analysis_uncertainty import verify_analysis_uncertainty

            result["uncertainty_verification"] = verify_analysis_uncertainty(result, uncertainty)
            if "qualification" in result["water_accounting"]:
                result["water_accounting"]["qualification"] = result["water_accounting"][
                    "qualification"
                ].replace(
                    "Water uncertainty is not evaluated.",
                    "Water uncertainty is assessed in uncertainty_verification "
                    "under explicit bounds.",
                )
            result["qualifications"] = [
                q.replace(
                    "product and water uncertainty are not evaluated",
                    "product and water uncertainty are evaluated under the separately disclosed "
                    "bounds and chemistry sampling",
                )
                for q in result["qualifications"]
            ]
        else:
            result["uncertainty_verification"] = verify_uncertainty(
                result, uncertainty, effective_bounds=effective_bounds
            )
    if product_stocks:
        result["verified"] = False
        result["stock_delivery"]["verification_scope"] = (
            "Numerical assessment only. Product-stock evidence integration and lab testing "
            "are deferred; no measured verification or stability claim."
        )
    if stock_dosing is not None and not product_stocks:
        from .stock_evidence import assess_stock_evidence

        result["stock_verification"] = assess_stock_evidence(result, stock_evidence)
        result["verified"] = result["stock_verification"]["verified"]
        result["stock_delivery"]["verification_scope"] = (
            "Numerical checks and all supplied preparation records passed; "
            "physical measurements and certificate authenticity were not independently verified."
            if result["verified"]
            else "Unverified: preparation accuracy requires supporting measurement records; "
            "see stock_verification for missing or failed evidence."
        )
        result["uncertainty_verification"]["verification_scope"] = result["stock_delivery"][
            "verification_scope"
        ]
    if result["water_accounting"]["source"] != "demineralized":
        result["verified"] = False
    result["stable"] = False
    if stock_dosing is not None and not product_stocks:
        from .batch_stability import assess_batch_stability

        result["stability_assessment"] = assess_batch_stability(result, batch_stability)
        result["stable"] = result["stability_assessment"]["stable"]
    from .steiner_context import recipe_historical_context

    result["historical_context"] = recipe_historical_context(result)
    result["qualifications"].extend(
        "Steiner (1961): " + warning["message"]
        for warning in result["historical_context"]["warnings"]
    )
    return result
