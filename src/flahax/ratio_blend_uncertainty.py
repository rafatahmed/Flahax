"""Ingredient-fraction bounds with correlated assays and derived counterions."""

from copy import deepcopy
import itertools
import math

from .delivery_contracts import DeliveryError
from .engine import load_library
from .materials import make_grade
from .product_conversion import material_inventory, component_nutrient_masses, MOLAR_MASS
from .ratio_products import LABELS


def is_blend(entry):
    """Identify the explicit ingredient-bounds selector."""
    return isinstance(entry, dict) and entry.get("source") == "blend_ingredients"


def ingredients(row):
    """Resolve the same catalogue ingredients consumed by material chemistry."""
    grade = make_grade(row["product"].get("grade"))
    if grade.composition != "disclosed" or not grade.components or grade.impurity_limits:
        raise DeliveryError(
            "unsupported_blend_bounds",
            "Require disclosed ingredients without unmodeled impurity limits",
        )
    catalogue = {p["name"]: p for p in load_library()["salts"]}
    from .materials import load_identities

    identities = load_identities()
    result = []
    for identity, fraction in grade.components:
        product = catalogue[identities[identity]["products"][0]]
        inventory = material_inventory(product)
        if inventory["status"] != "supported_components":
            raise DeliveryError("unsupported_blend_bounds", "Ingredient chemistry is unavailable")
        result.append((identity, fraction, inventory))
    return result


def inventory_at(row, parts, fractions):
    """Retain declared assays separately from component-derived nutrient quantities."""
    chemical, labels = {}, {}
    for identity, _, inv in parts:
        fraction = fractions[identity]
        for key, value in inv["components_moles_per_gram"].items():
            chemical[key] = chemical.get(key, 0) + fraction * value
        for key, value in inv["nutrient_percent"].items():
            labels[key] = labels.get(key, 0) + fraction * value
    component_percent = {k: v * 100 for k, v in component_nutrient_masses(chemical).items()}
    nutrients = dict(component_percent)
    nutrients.update({k: labels.get(k, 0) for k in row["product"]["elements"]})
    return dict(
        nutrient_percent=nutrients,
        components_moles_per_gram=chemical,
        component_nutrient_percent=component_percent,
        assay_component_difference_percent={
            k: v - component_percent.get(k, 0) for k, v in nutrients.items()
        },
        status="supported_components",
        limitation_code=None,
        limitation=(
            "Fixed catalogue ingredient assays; fractions vary jointly "
            "with all ingredient counterions."
        ),
    )


def validate_blend(row, entry):
    """Reject incomplete fraction boxes, mass excess and inconsistent nominal assays."""
    if set(entry) != {"source", "mass_fraction_bounds"}:
        raise DeliveryError("invalid_blend_bounds", "Supply source and mass_fraction_bounds only")
    parts = ingredients(row)
    bounds = entry["mass_fraction_bounds"]
    if not isinstance(bounds, dict) or set(bounds) != {i for i, _, _ in parts} or len(parts) > 8:
        raise DeliveryError(
            "invalid_blend_bounds", "Bound every disclosed ingredient; at most eight are supported"
        )
    for identity, nominal, _ in parts:
        pair = bounds[identity]
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in pair
            )
            or not 0 <= pair[0] <= nominal <= pair[1] <= 1
        ):
            raise DeliveryError(
                "invalid_blend_bounds",
                "Finite fraction bounds must contain nominal fractions within 0..1",
            )
    if sum(p[1] for p in bounds.values()) + row["solvent_fraction"] > 1 + 1e-12:
        raise DeliveryError(
            "invalid_blend_mass_bounds",
            "Upper ingredient fractions plus solvent exceed product mass",
        )
    predicted = inventory_at(row, parts, {i: f for i, f, _ in parts})
    for field in ("nutrient_percent", "components_moles_per_gram"):
        actual = row["inventory"][field]
        if any(
            not math.isclose(
                predicted[field].get(k, 0), actual.get(k, 0), rel_tol=1e-10, abs_tol=1e-14
            )
            for k in set(actual) | set(predicted[field])
        ):
            raise DeliveryError(
                "blend_assay_mismatch",
                "Nominal blend assays do not match the declared ingredient model",
            )


def blend_vertices(row, options, dimension):
    """Enumerate ingredient/dose vertices without separating correlated elements."""
    entry = options["product_element_factors"][row["name"]]
    parts = ingredients(row)
    name = row["name"]
    dose = row["grams"]
    error = options["weighing_error_g"] if dose > 0 else 0
    masses = (dose - error, dose + error)
    dimension("mass." + name, *masses)
    bounds = entry["mass_fraction_bounds"]
    for identity, _, _ in parts:
        if dose > 0:
            dimension("ingredient." + name + "." + identity, *bounds[identity])
    vectors, coordinates = [], []
    for mass_end in (0, 1):
        for ends in itertools.product((0, 1), repeat=len(parts)):
            fractions = {part[0]: bounds[part[0]][end] for part, end in zip(parts, ends)}
            inv = inventory_at(row, parts, fractions)
            percent = inv["nutrient_percent"]
            vector = [
                percent.get(k, 0) * 10 * masses[mass_end] / MOLAR_MASS[k.split("_")[0]]
                for k in LABELS
            ]
            vector += [percent.get(k, 0) * 10 * masses[mass_end] for k in ("Na", "Cl", "N_NH4")]
            vectors.append(vector)
            coordinates.append(
                {
                    "mass." + name: mass_end,
                    **{"ingredient." + name + "." + p[0]: end for p, end in zip(parts, ends)},
                }
            )
    return ("product." + name, *vectors), coordinates, masses


def sampled_inventory(row, entry, values):
    """Rebuild each scenario from its ingredient fractions, including inferred nutrients."""
    fractions = {
        i: values.get("ingredient." + row["name"] + "." + i, (p[0] + p[1]) / 2)
        for i, p in entry["mass_fraction_bounds"].items()
    }
    return inventory_at(row, ingredients(row), fractions)


def bound_evidence(row, entry):
    """Retain the ingredient inventory basis and identified inferred nutrients."""
    return dict(
        grade=deepcopy(row["product"]["grade"]),
        mass_fraction_bounds=deepcopy(entry["mass_fraction_bounds"]),
        ingredient_inventories={i: deepcopy(inv) for i, _, inv in ingredients(row)},
        inferred_nutrients=sorted(
            set(row["inventory"]["nutrient_percent"]) - set(row["product"]["elements"])
        ),
        qualification=(
            "Ingredient assays are fixed catalogue inputs. Fraction bounds correlate "
            "each ingredient's nutrients and counterions; this is not measured blend validation."
        ),
    )
