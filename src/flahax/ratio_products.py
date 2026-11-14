"""Commercial-material inventories and a local fixed-ratio allocation."""

from copy import deepcopy
import math

from .aqueous_model import solve
from .composition import validate_profile, InputError
from .delivery_contracts import DeliveryError
from .engine import nnls
from .nutrient_acceptance import assess_incidental
from .product_conversion import material_inventory, component_nutrient_masses, MOLAR_MASS
from .ratio_water import BASIS, NUTRIENTS
from .saturation_policy import assess_saturation

LABELS = ("K", "Ca", "Mg", "N_NO3", "P", "S")
VALENCES = (1, 2, 2, 1, 1, 2)


def validate_limits(limits):
    """Explicit Na/Cl maxima in elemental mg/L, with no crop-specific defaults."""
    if limits is None:
        return {}
    if not isinstance(limits, dict) or set(limits) - {"Na", "Cl"}:
        raise DeliveryError("invalid_ratio_limits", "Only Na and Cl maxima in mg/L are supported")
    return _checked_profile(limits, "maximum_concentrations")


def _checked_profile(values, name):
    if not isinstance(values, dict) or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values.values()
    ):
        raise DeliveryError("invalid_ratio_input", f"{name} requires finite numeric values")
    try:
        return validate_profile(values, name)
    except InputError as exc:
        raise DeliveryError("invalid_ratio_input", str(exc)) from exc


def limit_assessment(elemental, limits):
    """Use the existing direct ceiling comparison on the analytical inventory."""
    rows = [{"symbol": n, "target": None, "final": elemental.get(n, 0.0)} for n in ("Na", "Cl")]
    result = assess_incidental(rows, limits)
    result["passed"] = not result["limitViolations"]
    result["maximum_concentrations_mg_l"] = dict(limits)
    return result


def water_totals(report, volume, mass):
    """Reconstruct the final-solvent-basis inventory of the source water alone."""
    result = dict(report["background_totals_mol_kg"])
    result.update(
        {b: report["nutrients_mmol_l"][n] * volume / mass / 1000 for n, b in zip(NUTRIENTS, BASIS)}
    )
    return result


def elemental_from_totals(totals, volume, mass):
    """Convert chemistry mol/kg to elemental mg/L on the declared batch basis."""
    return {k: v * mass / volume * 1000 for k, v in component_nutrient_masses(totals).items()}


def _sources(products):
    if not isinstance(products, list) or not products:
        raise DeliveryError("invalid_ratio_products", "Supply a nonempty list of product records")
    sources = []
    names = set()
    for entry in products:
        if not isinstance(entry, dict) or set(entry) != {"product", "role", "solvent_fraction"}:
            raise DeliveryError(
                "invalid_ratio_products", "Each entry requires product, role and solvent_fraction"
            )
        product = entry["product"]
        if (
            not isinstance(product, dict)
            or not isinstance(product.get("name"), str)
            or not product["name"].strip()
        ):
            raise DeliveryError("invalid_ratio_products", "Every product requires a nonempty name")
        if product["name"] in names:
            raise DeliveryError("invalid_ratio_products", "Product names must be unique")
        names.add(product["name"])
        if entry["role"] not in ("fertilizer", "ph_reagent"):
            raise DeliveryError(
                "invalid_ratio_products", "Product role must be fertilizer or ph_reagent"
            )
        assay = _checked_profile(product.get("elements"), "product elemental assay")
        solvent = entry["solvent_fraction"]
        if (
            isinstance(solvent, bool)
            or not isinstance(solvent, (int, float))
            or not math.isfinite(solvent)
            or not 0 <= solvent <= 1
        ):
            raise DeliveryError(
                "invalid_ratio_products", "Declare a solvent mass fraction between zero and one"
            )
        if sum(assay.values()) / 100 + solvent > 1 + 1e-12:
            raise DeliveryError(
                "invalid_ratio_products",
                "Declared elemental assay and solvent exceed product mass",
            )
        inv = material_inventory(product)
        if inv["components_moles_per_gram"] is None:
            raise DeliveryError(inv["limitation_code"], inv["limitation"])
        sources.append(dict(deepcopy(entry), name=product["name"], inventory=inv))
    return sources


def reconstruct_products(sources, grams, water, volume, mass):
    """Sum declared analytical assays separately from conserved chemistry components."""
    totals = water_totals(water, volume, mass)
    audit = {
        "water": elemental_from_totals(totals, volume, mass),
        "fertilizers": {},
        "ph_reagents": {},
    }
    ingredients = []
    solvent = 0.0
    for source, dose in zip(sources, grams):
        inv = material_inventory(source["product"])
        if inv["components_moles_per_gram"] is None:
            raise DeliveryError(inv["limitation_code"], inv["limitation"])
        amounts = {k: dose / volume * v * 10 for k, v in inv["nutrient_percent"].items()}
        category = "fertilizers" if source["role"] == "fertilizer" else "ph_reagents"
        for k, v in amounts.items():
            audit[category][k] = audit[category].get(k, 0) + v
        for b, v in inv["components_moles_per_gram"].items():
            totals[b] = totals.get(b, 0) + dose / mass * v
        solvent += dose * source["solvent_fraction"] / 1000
        ingredients.append(
            dict(
                name=source["product"]["name"],
                grams=dose,
                product=deepcopy(source["product"]),
                role=source["role"],
                solvent_fraction=source["solvent_fraction"],
                inventory=inv,
                contributions_mmol_l={
                    n: amounts.get(k, 0) / MOLAR_MASS[k.split("_")[0]]
                    for n, k in zip(NUTRIENTS, LABELS)
                },
            )
        )
    elemental = {
        k: sum(part.get(k, 0) for part in audit.values())
        for k in set().union(*(part.keys() for part in audit.values()))
    }
    six = {n: elemental.get(k, 0) / MOLAR_MASS[k.split("_")[0]] for n, k in zip(NUTRIENTS, LABELS)}
    nutrient_audit = {
        name: {
            n: audit[category].get(k, 0) / MOLAR_MASS[k.split("_")[0]]
            for n, k in zip(NUTRIENTS, LABELS)
        }
        for name, category in (
            ("water_mmol_l", "water"),
            ("salts_mmol_l", "fertilizers"),
            ("ph_reagents_mmol_l", "ph_reagents"),
        )
    }
    chemical = elemental_from_totals(totals, volume, mass)
    return dict(
        ingredients=ingredients,
        aqueous_totals_mol_kg=totals,
        elemental_mg_l=elemental,
        elemental_accounting_mg_l=audit,
        analytical_mmol_l=six,
        nutrient_accounting=nutrient_audit,
        analytical_minus_chemistry_mg_l={k: v - chemical.get(k, 0) for k, v in elemental.items()},
        declared_product_solvent_kg=solvent,
        solvent_inventory_passed=solvent + water.get("source_water_mass_kg", 0) <= mass,
    )


def plan_products(products, cations, anions, ph, strength, volume, mass, water, limits):
    """Find a nonnegative local candidate; independently reconstruct and qualify it."""
    sources = _sources(products)
    initial = water_totals(water, volume, mass)
    water_elements = elemental_from_totals(initial, volume, mass)
    if not limit_assessment(water_elements, limits)["passed"]:
        raise DeliveryError(
            "ratio_limit_exceeded", "Source water exceeds a sodium/chloride maximum"
        )
    # Explicit zero headroom cannot be supplied by any nonnegative product dose.
    keep = [
        i
        for i, s in enumerate(sources)
        if not any(
            water_elements.get(k, 0) >= cap and s["inventory"]["nutrient_percent"].get(k, 0) > 0
            for k, cap in limits.items()
        )
    ]
    active = [sources[i] for i in keep]
    if not active:
        raise DeliveryError(
            "ratio_product_fit_failed", "No products remain within the stated limits"
        )
    coefficients = [
        [
            s["inventory"]["nutrient_percent"].get(k, 0) * 10 / MOLAR_MASS[k.split("_")[0]]
            for s in active
        ]
        for k in LABELS
    ]
    background = [water["nutrients_mmol_l"][n] for n in NUTRIENTS]
    matrix = []
    rhs = []
    for offset, shares in ((0, cations), (3, anions)):
        for j, share in enumerate(shares):
            group = [
                sum(coefficients[offset + i][p] * VALENCES[offset + i] for i in range(3))
                for p in range(len(active))
            ]
            matrix.append(
                [
                    (coefficients[offset + j][p] * VALENCES[offset + j] - share * group[p])
                    / strength
                    for p in range(len(active))
                ]
            )
            rhs.append(
                -(
                    background[offset + j] * VALENCES[offset + j]
                    - share * sum(background[offset + i] * VALENCES[offset + i] for i in range(3))
                )
                / strength
            )
    matrix.append([sum(row[p] for row in coefficients) / strength for p in range(len(active))])
    rhs.append((strength - sum(background)) / strength)
    bounds = []
    for k, cap in limits.items():
        remaining = cap - water_elements.get(k, 0)
        bounds.append(
            (
                [s["inventory"]["nutrient_percent"].get(k, 0) * 10 for s in active],
                remaining * (1 - 1e-10),
                max(cap, 1),
            )
        )
    available = mass - water.get("source_water_mass_kg", 0)
    bounds.append(
        ([s["solvent_fraction"] * volume / 1000 for s in active], available, max(mass, 1))
    )
    n = len(active)
    slack = len(bounds)
    matrix = [row + [0.0] * slack for row in matrix]
    for j, (row, bound, scale) in enumerate(bounds):
        matrix.append([v / scale for v in row] + [float(j == i) for i in range(slack)])
        rhs.append(bound / scale)
    factor = volume / mass
    charge_scale = mass / volume * 1000 / strength

    def state(point):
        totals = dict(initial)
        for s, dose in zip(active, point):
            for b, v in s["inventory"]["components_moles_per_gram"].items():
                totals[b] = totals.get(b, 0) + dose * v * factor
        return solve(totals, ph)

    def errors(point):
        linear = [sum(v * x for v, x in zip(row, point)) - b for row, b in zip(matrix, rhs)]
        charge = (state(point).charge_balance - water["reference_charge_mol_kg"]) * charge_scale
        return linear, charge

    point = [0.0] * (n + slack)
    for iteration in range(60):
        linear, charge = errors(point)
        merit = sum(v * v for v in linear) + charge * charge
        if max(map(abs, linear), default=0) < 1e-10 and abs(charge) < min(
            1e-10, 1e-10 * charge_scale
        ):
            break
        derivative = []
        for j in range(n):
            step = 1e-5 * max(1, point[j])
            trial = list(point)
            trial[j] += step
            derivative.append((errors(trial)[1] - charge) / step)
        derivative += [0.0] * slack
        proposal = nnls(
            matrix + [derivative], rhs + [sum(a * x for a, x in zip(derivative, point)) - charge]
        )
        for power in range(24):
            trial = [x + (y - x) * 2 ** (-power) for x, y in zip(point, proposal)]
            try:
                lin, ch = errors(trial)
            except DeliveryError:
                continue
            if sum(v * v for v in lin) + ch * ch < merit:
                point = trial
                break
        else:
            raise DeliveryError(
                "ratio_product_fit_failed",
                "Local commercial-product fit did not close ratios, concentration, pH "
                "and constraints; global infeasibility is not established",
            )
    else:
        raise DeliveryError(
            "ratio_product_fit_failed", "Commercial-product fit exhausted its iteration budget"
        )
    grams = [0.0] * len(sources)
    for i, dose in zip(keep, point[:n]):
        grams[i] = dose * volume
    result = reconstruct_products(sources, grams, water, volume, mass)
    chemistry = solve(result["aqueous_totals_mol_kg"], ph)
    achieved = [result["analytical_mmol_l"][k] for k in NUTRIENTS]
    eq = [v * z for v, z in zip(achieved, VALENCES)]
    result.update(
        schema_version="1",
        target_ph=ph,
        volume_litres=volume,
        water_mass_kg=mass,
        temperature_c=25,
        counted_mmol_l=sum(achieved),
        cation_percent=[100 * v / sum(eq[:3]) for v in eq[:3]],
        anion_percent=[100 * v / sum(eq[3:]) for v in eq[3:]],
        water_accounting=water,
        product_inventory=True,
        maximum_concentrations=limits,
        limit_assessment=limit_assessment(result["elemental_mg_l"], limits),
        charge_residual_mol_kg=chemistry.charge_balance,
        charge_closure_error_mol_kg=chemistry.charge_balance - water["reference_charge_mol_kg"],
        saturation_indices=chemistry.saturation_indices,
        saturation_assessment=assess_saturation(chemistry),
        verified=False,
        allocation_evidence={
            "iterations": iteration + 1,
            "method": "local linearization using existing nonnegative least squares",
            "global_feasibility_proved": False,
        },
        qualifications=[
            "Commercial assays determine nutrient ratios and limits; chemistry uses "
            "supported material components. Assay/chemistry differences are reported "
            "explicitly.",
            "All supplied products are explicitly permitted. Additional nutrients and "
            "counterions enter full chemistry but not Steiner's six-nutrient count.",
            "25 C, closed inorganic carbon, no gas exchange or solid allocation; "
            "product and water uncertainty are not evaluated.",
            "Source-water charge imbalance is preserved. Supplied product solvent is "
            "included in the final water inventory, not added on top of it.",
            "Steiner solution 1a measured pH 5.33, 6.45 and 6.58; model replay "
            "approximately 5.06, 6.66 and 6.66. The experimental +0.13 pH rise remains "
            "unresolved.",
        ],
    )
    if not result["limit_assessment"]["passed"] or not result["solvent_inventory_passed"]:
        raise DeliveryError(
            "ratio_product_fit_failed",
            "Reconstructed product recipe exceeds a hard limit or solvent inventory",
        )
    ratio_errors = [
        abs(a - 100 * b)
        for a, b in zip(result["cation_percent"] + result["anion_percent"], cations + anions)
    ]
    if (
        max(ratio_errors) > 1e-7
        or abs(result["counted_mmol_l"] - strength) > 1e-8 * max(1, strength)
        or abs(result["charge_closure_error_mol_kg"]) > 1e-10
    ):
        raise DeliveryError(
            "ratio_verification_failed", "Independent commercial recipe reconstruction failed"
        )
    return result
