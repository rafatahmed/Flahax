# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Closed-batch mass balance with explicit solvent and quantity intervals."""

from copy import deepcopy
import itertools
import math

from .delivery_contracts import DeliveryError
from .ratio_water import BASIS, account_water
from .product_conversion import MOLAR_MASS, component_nutrient_masses


def validate_physical(options, sources, water):
    """Validate complete absolute intervals; never infer density from chemistry."""
    p = options.get("physical_preparation")
    keys = {
        "solution_density_kg_l",
        "source_water_mass_kg",
        "source_water_solvent_fraction",
        "product_solvent_fractions",
    }
    if options["mode"] != "water_product_elemental" or not isinstance(water, dict):
        raise DeliveryError(
            "unsupported_physical_uncertainty",
            "Use elemental mode and an explicit source-water analysis",
        )
    if not isinstance(p, dict) or set(p) != keys:
        raise DeliveryError(
            "invalid_physical_uncertainty", "Supply complete physical preparation intervals"
        )
    account_water(water, 1.0, water.get("source_water_mass_kg", 0))
    fractions = p["product_solvent_fractions"]
    if not isinstance(fractions, dict) or set(fractions) != {s["name"] for s in sources}:
        raise DeliveryError("invalid_physical_uncertainty", "Bound every product solvent fraction")
    for key, pair, product_fraction in [
        *((k, p[k], False) for k in keys if k != "product_solvent_fractions"),
        *((k, v, True) for k, v in fractions.items()),
    ]:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in pair
            )
            or not 0 <= pair[0] <= pair[1]
        ):
            raise DeliveryError(
                "invalid_physical_uncertainty", "Require finite ordered nonnegative bounds"
            )
        if (
            not product_fraction
            and key
            in ("solution_density_kg_l", "source_water_mass_kg", "source_water_solvent_fraction")
            and pair[0] <= 0
        ):
            raise DeliveryError(
                "invalid_physical_uncertainty",
                "Density and source-water mass/solvent must be positive",
            )
        if (product_fraction or key == "source_water_solvent_fraction") and pair[1] > 1:
            raise DeliveryError(
                "invalid_physical_uncertainty", "Solvent fractions cannot exceed one"
            )
    if (
        not p["source_water_mass_kg"][0]
        <= water["source_water_mass_kg"]
        <= p["source_water_mass_kg"][1]
    ):
        raise DeliveryError(
            "invalid_physical_uncertainty", "Source-water bounds must include the nominal quantity"
        )
    # A necessary lower bound using known nutrient elements only, not a complete
    # dissolved-solids estimate (oxygen, hydrogen and unknown solutes are omitted).
    elemental_mass = sum(component_nutrient_masses(water["totals_mol_kg"]).values()) / 1000
    max_elements = elemental_mass * (1 + options["water_relative_error"])
    if max_elements > 1 / p["source_water_solvent_fraction"][1] - 1 + 1e-12:
        raise DeliveryError(
            "invalid_source_solvent_bounds",
            "Source non-solvent mass cannot be less than its known elemental inventory",
        )
    worst = deepcopy(sources)
    for s in worst:
        lo, hi = fractions[s["name"]]
        if not lo <= s["solvent_fraction"] <= hi:
            raise DeliveryError(
                "invalid_physical_uncertainty", "Solvent bounds must include each nominal fraction"
            )
        s["solvent_fraction"] = hi
    from .ratio_element_uncertainty import validate_element_factors

    validate_element_factors(worst, options["product_element_factors"])


def water_vertices(water, options, dimension):
    """Keep one source-water quantity shared by all water constituent assays."""
    masses = options["physical_preparation"]["source_water_mass_kg"]
    dimension("source_water.mass", *masses)
    keys = [k for k in (*BASIS, "Na+", "Cl-", "NH4+") if water["totals_mol_kg"].get(k, 0) > 0]
    vectors, coordinates = [], []
    for m_end in (0, 1):
        for ends in itertools.product((0, 1), repeat=len(keys)):
            vector = [0.0] * 9
            coords = {"source_water.mass": m_end}
            for k, end in zip(keys, ends):
                v = water["totals_mol_kg"][k] * (
                    1 + options["water_relative_error"] * (2 * end - 1)
                )
                i = BASIS.index(k) if k in BASIS else {"Na+": 6, "Cl-": 7, "NH4+": 8}[k]
                vector[i] = (
                    v
                    * masses[m_end]
                    * 1000
                    * (1 if i < 6 else MOLAR_MASS[{6: "Na", 7: "Cl", 8: "N"}[i]])
                )
                coords["water." + k] = end
            vectors.append(vector)
            coordinates.append(coords)
    return ("source_water", *vectors), coordinates


def mass_bounds(recipe, options, dimension):
    """Bound solvent and pure make-up mass for the fixed rounded product doses."""
    p = options["physical_preparation"]
    dimension("solution.density", *p["solution_density_kg_l"])
    dimension("source_water.solvent_fraction", *p["source_water_solvent_fraction"])
    total_low = p["solution_density_kg_l"][0] * (
        recipe["volume_litres"] - options["volume_error_litres"]
    )
    total_high = p["solution_density_kg_l"][1] * (
        recipe["volume_litres"] + options["volume_error_litres"]
    )
    src_low, src_high = p["source_water_mass_kg"]
    sf_low, sf_high = p["source_water_solvent_fraction"]
    non_low, non_high = src_low * (1 / sf_high - 1), src_high * (1 / sf_low - 1)
    maximum_products = 0
    for row in recipe["rounded_verification"]["ingredients"]:
        low, high = p["product_solvent_fractions"][row["name"]]
        from .ratio_product_stocks import product_mass_bounds

        mass_low, mass_high = product_mass_bounds(row, options)
        dimension("solvent." + row["name"], low, high)
        non_low += mass_low * (1 - high) / 1000
        non_high += mass_high * (1 - low) / 1000
        maximum_products += mass_high / 1000
    if "stock_delivery" in recipe:
        maximum_products = recipe["stock_delivery"]["maximum_stock_mass_kg"]
    return [
        total_low - non_high,
        total_high - non_low,
    ], total_low - src_high / sf_low - maximum_products


def scenario_mass(sources, doses, options, values, volume):
    """Conserve total mass, separating solvent from declared non-solvent material."""
    p = options["physical_preparation"]

    def value(key, pair):
        return values.get(key, (pair[0] + pair[1]) / 2)

    source_mass = value("source_water.mass", p["source_water_mass_kg"])
    source_fraction = value("source_water.solvent_fraction", p["source_water_solvent_fraction"])
    total = value("solution.density", p["solution_density_kg_l"]) * volume
    non_solvent = source_mass * (1 / source_fraction - 1)
    for row, dose in zip(sources, doses):
        row["solvent_fraction"] = value(
            "solvent." + row["name"], p["product_solvent_fractions"][row["name"]]
        )
        non_solvent += dose * (1 - row["solvent_fraction"]) / 1000
    return total - non_solvent, source_mass
