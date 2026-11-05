# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Source-water speciation from a laboratory's measured pH, not charge balance alone.

A routine water analysis carries a charge-balance error of a few percent.
Solving pH from charge balance turns that error into pH: on a brackish well a
0.5% change in chloride moves the calculated pH by about 0.5 units. Here the
measured pH is the boundary condition instead. Inorganic carbon comes from the
analysis or from titrated alkalinity. The analysis is taken as measured: its
charge imbalance is reported and carried as a residual charge, and no ion is
added, removed or adjusted to close it (decision G11).

Two inventories, two uses (#84). ``analytical_totals`` is the laboratory analysis
as entered: nutrient targets and concentration limits are always checked on it.
``totals`` is the same analysis plus the inorganic carbon taken from a titrated
alkalinity, an input to chemistry only (pH, speciation, saturation, EC, reagent demand).
"""

from dataclasses import dataclass, replace
import math
from collections.abc import Mapping, Sequence

from .aqueous_model import AqueousResult, chemistry, solve
from .calculated_ph import calculate_equilibrium_ph
from .delivery_contracts import DeliveryError
from .delivery_quantities import SolventBasis
from .product_conversion import NUTRIENT_BASES as NUTRIENT_BASES
from .product_conversion import component_nutrient_masses
from .root_finding import shrink_bracket

# Numerical closure, not an analytical screen: a composition whose charge residual at the measured
# pH is within this fraction of its total ionic charge (0.0001 %) is reported as balanced.
CLOSURE_TOLERANCE = 1e-6
UNITS = 'mol/kg water'


def nutrient_mg_per_litre(totals, water_mass_kg=1.0, final_volume_litres=1.0):
    """Elemental mg/L from mol/kg water; defaults explicitly represent a 1 kg/1 L basis."""
    solvent = SolventBasis(final_volume_litres, water_mass_kg)
    ppm = {}
    for basis in NUTRIENT_BASES:
        if totals.get(basis) is None:
            continue
        # Validate each input before combining Fe(II)/Fe(III), so a negative
        # component cannot be hidden by a positive component of the same nutrient.
        amount = solvent.molality_to_mg_per_litre(totals[basis], 1.0)
        for nutrient, value in component_nutrient_masses({basis: amount}).items():
            ppm[nutrient] = ppm.get(nutrient, 0.0) + value
    return ppm


@dataclass(frozen=True)
class BalancedWaterAnalysis:
    """A water analysis closed at its measured pH: the laboratory record and the model, kept apart.

    ``analytical_totals`` are the analysis as entered (mol/kg water) and decide every
    nutrient target and concentration limit. ``totals`` are the charge-balanced model
    used for chemistry. ``measured_ph`` and ``alkalinity_eq_per_kg`` are source
    measurements; ``state`` is the computed state of this (possibly diluted) water.
    ``dilution_fraction`` is the share of the source water in ion-free water.
    ``residual_charge_eq`` (eq/kg water) is the charge of the measured water at its measured
    pH that no ion accounts for; the pH solves that follow reproduce it (decision G11).
    """

    totals: dict
    measured_ph: float
    state: AqueousResult
    balance_ion: str | None
    analysed_balance_ion_molal: float
    balance_adjustment_molal: float
    imbalance_percent: float
    inorganic_carbon_molal: float
    carbon_source: str
    analytical_totals: dict = None
    alkalinity_eq_per_kg: float | None = None
    analysis_id: str | None = None
    dilution_fraction: float = 1.0
    phases: tuple = ()
    units: str = UNITS
    # 'unchanged' (balanced within CLOSURE_TOLERANCE) or 'imbalance_reported' (accepted as
    # measured, the residual charge carried).
    reconciliation: str = 'unchanged'
    residual_charge_eq: float = 0.0
    fixed: tuple = ()
    below_detection: dict = None  # component -> detection limit, mol/kg water
    balance_ion_uncertainty_percent: float | None = None

    def __post_init__(self):
        # Defensive copies: later edits to the caller's dicts cannot change this record.
        object.__setattr__(self, 'totals', dict(self.totals))
        object.__setattr__(self, 'analytical_totals', dict(self.analytical_totals or {}))
        object.__setattr__(self, 'phases', tuple(self.phases))
        object.__setattr__(self, 'fixed', tuple(self.fixed))
        object.__setattr__(self, 'below_detection', dict(self.below_detection or {}))

    def analytical_mg_per_litre(self):
        """Laboratory-basis nutrient mg/L, taking 1 kg of water per litre."""
        return nutrient_mg_per_litre(self.analytical_totals)

    def modelled_mg_per_litre(self):
        """Charge-balanced model nutrient mg/L, taking 1 kg of water per litre."""
        return nutrient_mg_per_litre(self.totals)

    def diluted(self, fraction):
        """This water blended with ion-free water: ``fraction`` of it per unit of blend.

        Both inventories scale. The blend's chemistry is recomputed from the scaled
        balanced totals (closed carbon), never carried over from the source; the
        source's measured pH stays as metadata. Blending two real waters needs both
        analyses and is not handled here.
        """
        if (
            isinstance(fraction, bool)
            or not isinstance(fraction, (int, float))
            or not math.isfinite(fraction)
            or not 0 < fraction <= 1
        ):
            raise DeliveryError('invalid_value', 'dilution fraction must be in (0, 1]')
        totals = {k: v * fraction for k, v in self.totals.items()}
        residual = self.residual_charge_eq * fraction
        state = calculate_equilibrium_ph(
            totals,
            carbon_boundary='closed',
            temperature_c=25,
            phases=list(self.phases),
            residual_charge=residual,
        )
        return replace(
            self,
            totals=totals,
            state=state,
            analytical_totals={k: v * fraction for k, v in self.analytical_totals.items()},
            residual_charge_eq=residual,
            inorganic_carbon_molal=self.inorganic_carbon_molal * fraction,
            alkalinity_eq_per_kg=None
            if self.alkalinity_eq_per_kg is None
            else self.alkalinity_eq_per_kg * fraction,
            below_detection={k: v * fraction for k, v in self.below_detection.items()},
            dilution_fraction=self.dilution_fraction * fraction,
        )


def carbonate_alkalinity(state):
    """Carbonate alkalinity (eq/kg water) of a solved state.

    Each carbon species counts 2 x carbon - H+ relative to H2CO3; OH- and H+
    count +1 and -1. Phosphate, borate and organic bases are not included.
    """
    total = 0.0
    for record in chemistry()['aqueous']:
        name = record['name']
        if name not in state.species:
            continue
        powers = record['powers']
        carbon = powers.get('CO3-2', 0.0)
        protons = powers.get('H+', 0.0)
        if carbon:
            total += state.species[name] * (2 * carbon - protons)
        elif set(powers) <= {'H+', 'H2O'}:
            total -= state.species[name] * protons
    return total


# Proton zero levels: H2CO3, H2PO4-, H3BO3, NH4+, SO4-2 and unhydrolysed
# major ions. See NOAA/OCADS co2rprt.html (Dickson total-alkalinity definition).
# This is a supported subset, not an assumption that omitted acid/base systems vanish.
ALKALINITY_PROTON_REFERENCE = {
    'CO3-2': 2,
    'PO4-3': 2,
    'H3BO3': 0,
    'NH4+': 0,
    'SO4-2': 0,
    'Ca+2': 0,
    'Mg+2': 0,
    'K+': 0,
    'Na+': 0,
    'Cl-': 0,
    'NO3-': 0,
    'H+': -1,
    'H2O': 0,
}


def total_alkalinity(state):
    """Supported inorganic proton balance in eq/kg solvent water.

    Includes carbonate, phosphate relative to H2PO4-, borate, ammonia, sulfate
    protonation, water and complexes of supported major ions. Active species
    with an unqualified proton reference (including organic ligands and trace
    metals) are rejected. No seawater constants or salinity assumptions are used.
    """
    records = {r['name']: r for r in chemistry()['aqueous']}
    total = 0.0
    for name, amount in state.species.items():
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount < 0
        ):
            raise DeliveryError(
                'invalid_alkalinity', 'species amounts must be finite nonnegative molalities'
            )
        if amount == 0:
            continue
        record = records.get(name)
        if record is None or set(record['powers']) - ALKALINITY_PROTON_REFERENCE.keys():
            raise DeliveryError(
                'unsupported_alkalinity', f'no qualified alkalinity proton reference for {name}'
            )
        equivalents = sum(ALKALINITY_PROTON_REFERENCE[b] * n for b, n in record['powers'].items())
        total += amount * equivalents
    return total


def _total_charge(state):
    charges = {r['name']: r['charge'] for r in chemistry()['aqueous']}
    return sum(abs(charges.get(name, 0)) * amount for name, amount in state.species.items())


def _imbalance_percent(state):
    positive = negative = 0.0
    charges = {r['name']: r['charge'] for r in chemistry()['aqueous']}
    for name, amount in state.species.items():
        charge = charges.get(name, 0)
        if charge > 0:
            positive += charge * amount
        elif charge < 0:
            negative -= charge * amount
    total = positive + negative
    return 0.0 if total == 0 else 100 * (positive - negative) / total


def _carbon_for_alkalinity(totals, ph, alkalinity, phases):
    """Infer missing inorganic carbon from supported total alkalinity at stated pH."""
    if 'CO3-2' in totals:
        raise DeliveryError(
            'ambiguous_carbon',
            'carbon is already reported, including zero; do not infer it from alkalinity',
        )
    last = [solve({k: v for k, v in totals.items() if k != 'CO3-2'}, ph, phases=phases)]

    def alk(carbon):
        last[0] = solve(
            totals | {'CO3-2': carbon}, ph, phases=phases, start=last[0]
        )  # warm start, #61
        return total_alkalinity(last[0])

    base = total_alkalinity(last[0])
    # Same eq/kg numerical closure scale used below for charge balance. This is
    # a solver equality check, not laboratory measurement uncertainty.
    if abs(alkalinity - base) <= 1e-12:
        return 0.0
    if alkalinity < base:
        raise DeliveryError(
            'alkalinity_out_of_range',
            'measured alkalinity is below the supported carbon-free alkalinity at the measured pH',
        )
    low, g_low, high = 0.0, base - alkalinity, 1e-6
    while (g_high := alk(high) - alkalinity) < 0:
        low, g_low = high, g_high
        high *= 4
        if high > 0.1:
            raise DeliveryError(
                'alkalinity_out_of_range',
                'alkalinity requires more carbon than the Davies domain allows',
            )
    low, high = shrink_bracket(
        lambda carbon: alk(carbon) - alkalinity, low, g_low, high, g_high, relative=1e-12
    )
    return (low + high) / 2


def balance_water_analysis(
    totals,
    *,
    measured_ph,
    alkalinity_eq_per_kg=None,
    phases=(),
    temperature_c=25.0,
    analysis_id=None,
    below_detection=None,
):
    """Speciate a water analysis at its measured pH, as measured.

    ``totals`` are analytical totals in mol/kg water. A component given as 0 is a
    measured zero and stays zero; an omitted component is not measured.
    ``below_detection`` maps components reported below detection to their
    detection limit (mol/kg); they enter the chemistry as 0, are recorded, and are
    never adjusted. Supply inorganic carbon either as ``totals['CO3-2']`` (0 for
    explicitly carbon-free water) or as ``alkalinity_eq_per_kg`` (titrated total
    alkalinity on the supported inorganic proton reference), never both, including
    an explicitly zero carbon inventory. Organic/trace-metal alkalinity without
    a qualified proton reference is rejected rather than attributed to carbonate.

    The composition is speciated at the measured pH and taken as measured. Its charge
    imbalance is returned as ``imbalance_percent`` and carried as ``residual_charge_eq``;
    no ion is adjusted to close it and no imbalance size rejects it (decision G11).
    The analysis itself is kept unchanged in ``analytical_totals`` (#84).
    """
    if not isinstance(totals, Mapping):
        raise DeliveryError('invalid_totals', 'analytical totals must be a mapping')
    for name, value in totals.items():
        if name not in chemistry()['bases']:
            raise DeliveryError('invalid_totals', f'unknown analytical component {name}')
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise DeliveryError(
                'invalid_totals', 'analytical totals must be finite nonnegative numbers'
            )
    if (
        isinstance(measured_ph, bool)
        or not isinstance(measured_ph, (int, float))
        or not math.isfinite(measured_ph)
        or not 0 <= measured_ph <= 14
    ):
        raise DeliveryError('out_of_range', 'measured_ph must be finite in [0,14]')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError(
            'temperature_out_of_range', 'water balancing requires the 25 C reaction set'
        )
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError(
            'invalid_type', 'supply an explicit phase sequence, or [] for aqueous-only'
        )
    phases = tuple(phases)
    totals = {k: float(v) for k, v in totals.items()}
    below_detection = dict(below_detection or {})
    for name, limit in below_detection.items():
        if (
            name not in chemistry()['bases']
            or isinstance(limit, bool)
            or not isinstance(limit, (int, float))
            or not math.isfinite(limit)
            or limit <= 0
        ):
            raise DeliveryError(
                'invalid_value',
                'below_detection maps analytical components to positive detection limits',
            )
        if totals.get(name, 0.0) != 0:
            raise DeliveryError(
                'contradictory_water_inputs',
                f'{name} is reported both as a value and below detection',
            )
        totals[name] = 0.0
    # Measured zeros and below-detection components are recorded as fixed: nothing adjusts them.
    fixed = tuple(sorted({k for k, v in totals.items() if v == 0} | set(below_detection)))
    carbon_given = totals.get('CO3-2', 0) > 0
    if alkalinity_eq_per_kg is not None:
        if 'CO3-2' in totals:
            raise DeliveryError(
                'ambiguous_carbon', 'supply inorganic carbon or alkalinity, not both'
            )
        if (
            isinstance(alkalinity_eq_per_kg, bool)
            or not isinstance(alkalinity_eq_per_kg, (int, float))
            or not math.isfinite(alkalinity_eq_per_kg)
        ):
            raise DeliveryError(
                'invalid_value', 'alkalinity_eq_per_kg must be finite (signed eq/kg water)'
            )
        carbon_source = 'alkalinity'
    elif carbon_given:
        carbon_source = 'inorganic_carbon'
    elif 'CO3-2' in totals:
        carbon_source = 'none'  # measured carbon-free, distinct from carbon not reported
    else:
        raise DeliveryError(
            'missing_carbon',
            'measured-pH balancing needs inorganic carbon or alkalinity '
            '(CO3-2 = 0 for water measured carbon-free)',
        )
    working = dict(totals)
    if carbon_source == 'alkalinity':
        working['CO3-2'] = _carbon_for_alkalinity(
            working, measured_ph, alkalinity_eq_per_kg, phases
        )
    state = solve(working, measured_ph, phases=phases)
    imbalance = _imbalance_percent(state)
    record = dict(
        analytical_totals=totals,
        alkalinity_eq_per_kg=alkalinity_eq_per_kg,
        analysis_id=analysis_id,
        phases=phases,
        fixed=fixed,
        below_detection=below_detection,
    )
    balanced = abs(state.charge_balance) <= CLOSURE_TOLERANCE * _total_charge(state)
    return BalancedWaterAnalysis(
        dict(working),
        float(measured_ph),
        state,
        None,
        0.0,
        0.0,
        imbalance,
        working.get('CO3-2', 0.0),
        carbon_source,
        reconciliation='unchanged' if balanced else 'imbalance_reported',
        residual_charge_eq=state.charge_balance,
        **record,
    )
