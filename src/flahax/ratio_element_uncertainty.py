# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent declared element assays, preserving shared product
weighing errors.
"""

from copy import deepcopy
import itertools
import math

from .delivery_contracts import DeliveryError
from .product_conversion import MOLAR_MASS, material_inventory
from .ratio_products import LABELS


def _hypothetical_product(product):
    """Detach a single-identity hypothesis from its unmodified source
    document.
    """
    if product.get("grade") is None:
        return deepcopy(product)
    grade = product["grade"]
    if grade.get("composition") != "single":
        raise DeliveryError(
            "unsupported_elemental_grade",
            "Blend and declared-ion grades require a separate ingredient/assay uncertainty model",
        )
    from .materials import make_grade

    parsed = make_grade(grade)
    return dict(
        name=product["name"], identityId=parsed.identity_id, elements=deepcopy(product["elements"])
    )


def validate_element_factors(sources, factors):
    """Require complete explicit assay bounds and refuse unbounded
    derived nutrients.
    """
    names = {s["name"] for s in sources}
    if not isinstance(factors, dict) or set(factors) != names:
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "Declare elemental factors for every product, including pH reagents",
        )
    for source in sources:
        product = source["product"]
        entry = factors[source["name"]]
        from .ratio_blend_uncertainty import is_blend, validate_blend

        if is_blend(entry):
            validate_blend(source, entry)
            continue
        if product.get("grade") is not None:
            adapted = material_inventory(_hypothetical_product(product))
            original = source["inventory"]
            if adapted["status"] != "supported_components" or any(
                set(adapted[field]) != set(original[field])
                or any(
                    not math.isclose(value, original[field][key], rel_tol=1e-12, abs_tol=1e-15)
                    for key, value in adapted[field].items()
                )
                for field in ("nutrient_percent", "components_moles_per_gram")
            ):
                raise DeliveryError(
                    "unsupported_elemental_grade",
                    "Grade hypothesis does not preserve the nominal material inventory",
                )
        if not isinstance(entry, dict) or set(entry) != set(product["elements"]):
            raise DeliveryError(
                "invalid_analysis_uncertainty",
                "Declare factors for every and only stated element of each product",
            )
        for pair in entry.values():
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in pair
                )
                or not 0 < pair[0] <= pair[1]
            ):
                raise DeliveryError(
                    "invalid_analysis_uncertainty",
                    "Elemental factors require finite 0 < low <= high",
                )
        # Independent intervals include the all-high vertex. This
        # necessary mass bound does not establish stoichiometric
        # realizability of every vertex.
        upper_percent = sum(product["elements"][k] * pair[1] for k, pair in entry.items())
        if (
            not math.isfinite(upper_percent)
            or upper_percent / 100 + source["solvent_fraction"] > 1 + 1e-12
        ):
            raise DeliveryError(
                "invalid_elemental_mass_bounds",
                f"{source['name']}: upper elemental assays plus declared solvent "
                "exceed product mass",
            )
        missing = {
            k
            for k in (*LABELS, "Na", "Cl", "N_NH4")
            if k not in product["elements"]
            and source["inventory"]["nutrient_percent"].get(k, 0) > 0
        }
        if missing:
            raise DeliveryError(
                "unsupported_elemental_counterion_bounds",
                f"{source['name']}: derived {', '.join(sorted(missing))} needs explicit "
                "defensible bounds; it cannot be treated as fixed or zero",
            )


def product_vertices(row, options, dimension):
    """Return local mass/element vertices and their sampling-coordinate
    witnesses.
    """
    from .ratio_blend_uncertainty import is_blend, blend_vertices

    if is_blend(options["product_element_factors"][row["name"]]):
        return blend_vertices(row, options, dimension)
    name = row["name"]
    dose = row["grams"]
    from .ratio_product_stocks import product_mass_bounds

    masses = product_mass_bounds(row, options)
    dimension("mass." + name, *masses)
    factors = options["product_element_factors"][name]
    for key, value in row["product"]["elements"].items():
        if dose > 0 and value > 0:
            dimension("assay." + name + "." + key, *factors[key])
    relevant = [
        k for k in (*LABELS, "Na", "Cl", "N_NH4") if row["product"]["elements"].get(k, 0) > 0
    ]
    # Each product is one group, retaining a common dose for every
    # element. Other elements affect chemistry but not the six-ion/Na/Cl
    # objective vertices.
    vertices = []
    coordinates = []
    for mass_end in (0, 1):
        for ends in itertools.product((0, 1), repeat=len(relevant)):
            chosen = dict(zip(relevant, ends))
            vector = []
            for key in (*LABELS, "Na", "Cl", "N_NH4"):
                percent = row["product"]["elements"].get(key, 0)
                factor = factors[key][chosen.get(key, 0)] if key in factors else 1.0
                mg = percent * 10 * masses[mass_end] * factor
                vector.append(mg / MOLAR_MASS[key.split("_")[0]] if key in LABELS else mg)
            vertices.append(vector)
            coordinates.append(
                {
                    "mass." + name: mass_end,
                    **{"assay." + name + "." + key: end for key, end in chosen.items()},
                }
            )
    return ("product." + name, *vertices), coordinates, masses


def perturb_sources(sources, options, values):
    """Create hypothetical assay records without altering source
    documents or dose fitting.
    """
    changed = deepcopy(sources)
    doses = []
    for row in changed:
        name = row["name"]
        from .ratio_blend_uncertainty import is_blend, sampled_inventory

        entry = options["product_element_factors"][name]
        if is_blend(entry):
            row["_scenario_inventory"] = sampled_inventory(row, entry, values)
            doses.append(values.get("mass." + name, row["grams"]))
            continue
        row["product"] = _hypothetical_product(row["product"])
        for key, percent in row["product"]["elements"].items():
            low, high = options["product_element_factors"][name][key]
            factor = values.get("assay." + name + "." + key, (low + high) / 2)
            row["product"]["elements"][key] = percent * factor
        doses.append(values.get("mass." + name, row["grams"]))
    return changed, doses
