# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit source-water inventories for six-nutrient ratio planning."""

import math

from .delivery_contracts import DeliveryError
from .measured_water import balance_water_analysis

BASIS = ("K+", "Ca+2", "Mg+2", "NO3-", "PO4-3", "SO4-2")
NUTRIENTS = ("K", "Ca", "Mg", "NO3", "P", "SO4")


def account_water(water, volume, final_water_mass):
    """Preserve measured ions and carry measured charge, without reconciliation."""
    if water == "demineralized":
        return {
            "source": "demineralized",
            "nutrients_mmol_l": dict.fromkeys(NUTRIENTS, 0.0),
            "background_totals_mol_kg": {},
            "reference_charge_mol_kg": 0.0,
        }
    required = {
        "analysis_id",
        "totals_mol_kg",
        "measured_ph",
        "temperature_c",
        "source_water_mass_kg",
    }
    if not isinstance(water, dict) or not required <= water.keys():
        raise DeliveryError(
            "invalid_ratio_water",
            "Supply an identified water analysis, measured pH, temperature and source water mass",
        )
    if water.keys() - required - {"alkalinity_eq_per_kg"}:
        raise DeliveryError("invalid_ratio_water", "Unknown water-analysis fields")
    if not isinstance(water["analysis_id"], str) or not water["analysis_id"].strip():
        raise DeliveryError("invalid_ratio_water", "Water analysis_id must be nonempty")
    mass = water["source_water_mass_kg"]
    if (
        isinstance(mass, bool)
        or not isinstance(mass, (float, int))
        or not math.isfinite(mass)
        or not 0 < mass <= final_water_mass
    ):
        raise DeliveryError(
            "invalid_ratio_water",
            "Source water mass must be positive and no greater than final water mass",
        )
    totals = water["totals_mol_kg"]
    needed = set(BASIS) | {"Na+", "Cl-"}
    if (
        not isinstance(totals, dict)
        or not needed <= totals.keys()
        or totals.keys() - needed - {"CO3-2", "NH4+"}
    ):
        raise DeliveryError(
            "invalid_ratio_water",
            "Explicit six nutrient, sodium and chloride totals (including zeros) are "
            "required; inorganic carbon and ammonium may be added",
        )
    measured = balance_water_analysis(
        totals,
        measured_ph=water["measured_ph"],
        temperature_c=water["temperature_c"],
        analysis_id=water["analysis_id"],
        alkalinity_eq_per_kg=water.get("alkalinity_eq_per_kg"),
    )
    return {
        "source": "measured_analysis",
        "analysis_id": measured.analysis_id,
        "source_water_mass_kg": mass,
        "measured_ph": measured.measured_ph,
        "temperature_c": water["temperature_c"],
        "analytical_totals_mol_kg": dict(measured.analytical_totals),
        "chemistry_totals_mol_kg": dict(measured.totals),
        "carbon_source": measured.carbon_source,
        "alkalinity_eq_per_kg": measured.alkalinity_eq_per_kg,
        "imbalance_percent": measured.imbalance_percent,
        "reconciliation": measured.reconciliation,
        "reference_charge_mol_kg": measured.residual_charge_eq * mass / final_water_mass,
        "nutrients_mmol_l": {
            n: totals[b] * mass * 1000 / volume for n, b in zip(NUTRIENTS, BASIS)
        },
        "background_totals_mol_kg": {
            b: v * mass / final_water_mass for b, v in measured.totals.items() if b not in BASIS
        },
        "qualification": "Measured ions are unchanged. Their measured-pH charge "
        "imbalance is carried, not corrected. Sodium, chloride and carbon enter "
        "chemistry but not the six-nutrient count. Water uncertainty is not evaluated.",
    }
