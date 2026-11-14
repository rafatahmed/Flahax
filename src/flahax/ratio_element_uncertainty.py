"""Independent declared element assays, preserving shared product weighing errors."""

from copy import deepcopy
import itertools
import math

from .delivery_contracts import DeliveryError
from .product_conversion import MOLAR_MASS
from .ratio_products import LABELS


def validate_element_factors(sources, factors):
    """Require complete explicit assay bounds and refuse unbounded derived nutrients."""
    names = {s["name"] for s in sources}
    if not isinstance(factors, dict) or set(factors) != names:
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "Declare elemental factors for every product, including pH reagents",
        )
    for source in sources:
        product = source["product"]
        entry = factors[source["name"]]
        if product.get("grade") is not None:
            raise DeliveryError(
                "unsupported_elemental_grade",
                "Nested grade/blend records need a separate consistent assay/ingredient "
                "uncertainty model; supply an explicit supported material record",
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
                or not 0 < pair[0] <= pair[1] <= 1
            ):
                raise DeliveryError(
                    "invalid_analysis_uncertainty",
                    "Elemental factors require 0 < low <= high <= 1",
                )
        missing = {
            k
            for k in (*LABELS, "Na", "Cl")
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
    """Return local mass/element vertices and their sampling-coordinate witnesses."""
    name = row["name"]
    dose = row["grams"]
    error = options["weighing_error_g"] if dose > 0 else 0
    masses = (dose - error, dose + error)
    dimension("mass." + name, *masses)
    factors = options["product_element_factors"][name]
    for key, value in row["product"]["elements"].items():
        if dose > 0 and value > 0:
            dimension("assay." + name + "." + key, *factors[key])
    relevant = [k for k in (*LABELS, "Na", "Cl") if row["product"]["elements"].get(k, 0) > 0]
    # Each product is one group, retaining a common dose for every element.
    # Other elements affect chemistry but not the six-ion/Na/Cl objective vertices.
    vertices = []
    coordinates = []
    for mass_end in (0, 1):
        for ends in itertools.product((0, 1), repeat=len(relevant)):
            chosen = dict(zip(relevant, ends))
            vector = []
            for key in (*LABELS, "Na", "Cl"):
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
    """Create hypothetical assay records without altering source documents or dose fitting."""
    changed = deepcopy(sources)
    doses = []
    for row in changed:
        name = row["name"]
        for key, percent in row["product"]["elements"].items():
            low, high = options["product_element_factors"][name][key]
            factor = values.get("assay." + name + "." + key, (low + high) / 2)
            row["product"]["elements"][key] = percent * factor
        doses.append(values.get("mass." + name, row["grams"]))
    return changed, doses
