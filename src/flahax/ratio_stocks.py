# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Separate assayed-stock specifications and rounded volumetric delivery."""

import math

from .delivery_contracts import DeliveryError


def validate_stocks(options, formulae):
    """Reject ambiguous stock concentrations, dose precision and error bounds."""
    required = {
        "concentrations_g_l",
        "concentration_relative_error",
        "dose_error_ml",
        "dose_decimals",
    }
    if not isinstance(options, dict) or set(options) != required:
        raise DeliveryError("invalid_stock_dosing", "Supply all four stock dosing fields")
    concentrations = options["concentrations_g_l"]
    if not isinstance(concentrations, dict) or set(concentrations) != set(formulae):
        raise DeliveryError(
            "invalid_stock_dosing", "Specify concentration g/L for every declared stock"
        )
    for key, value, positive in [(k, v, True) for k, v in concentrations.items()] + [
        (k, options[k], False) for k in ("concentration_relative_error", "dose_error_ml")
    ]:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise DeliveryError("invalid_stock_dosing", f"{key} must be finite and numeric")
        if value < 0 or (positive and value == 0):
            raise DeliveryError("invalid_stock_dosing", f"Invalid stock value for {key}")
    if options["concentration_relative_error"] >= 1:
        raise DeliveryError("invalid_stock_dosing", "Concentration uncertainty must be below 100%")
    if type(options["dose_decimals"]) is not int or not 0 <= options["dose_decimals"] <= 6:
        raise DeliveryError("invalid_stock_dosing", "dose_decimals must be an integer from 0 to 6")


def prepare_stock_delivery(recipe, options, volume_error):
    """Convert ideal compound masses to rounded stock doses and effective bounds."""
    rows, bounds = [], []
    error = options["dose_error_ml"]
    relative = options["concentration_relative_error"]
    for ingredient in recipe["ingredients"]:
        formula = ingredient["formula"]
        concentration = options["concentrations_g_l"][formula]
        dose = round(1000 * ingredient["grams"] / concentration, options["dose_decimals"])
        # An omitted dose has no dispensing event. Positive doses must exceed error.
        dose_error = error if ingredient["grams"] > 0 else 0
        if dose < dose_error:
            raise DeliveryError(
                "ratio_stock_dose_infeasible", "Stock dose is smaller than its error"
            )
        interval = sorted(
            {
                (dose - dose_error) * concentration * (1 - relative) / 1000,
                (dose + dose_error) * concentration * (1 + relative) / 1000,
            }
        )
        bounds.append(interval)
        rows.append(
            {
                "formula": formula,
                "concentration_g_l": concentration,
                "dose_ml": dose,
                "dose_error_ml": dose_error,
                "effective_grams": dose * concentration / 1000,
                "effective_grams_bounds": interval,
            }
        )
    maximum_volume = sum(row["dose_ml"] + row["dose_error_ml"] for row in rows)
    if maximum_volume >= 1000 * (recipe["volume_litres"] - volume_error):
        raise DeliveryError("ratio_stock_volume_infeasible", "Stock doses leave no dilution water")
    return {
        "stocks": rows,
        "effective_grams_bounds": bounds,
        "total_dose_ml": sum(row["dose_ml"] for row in rows),
        "specification": dict(options),
        "verification_scope": "Numerical assessment under declared stock and dosing bounds; "
        "no measured stock assays or dispenser calibration records have been supplied.",
        "concentration_basis": "Active compound/hydrate equivalent mass per litre. "
        "Stock concentration bounds replace raw reagent weighing/purity uncertainty; they must "
        "include assay, preparation and stability errors, not just analytical repeatability.",
        "preparation": "Six separate single-compound stocks. Add doses to dilution water and "
        "make up to final batch volume, including all stock volumes. Stock storage stability "
        "and reactive contaminants are outside this calculation.",
    }
