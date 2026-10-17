"""Source-water speciation from a laboratory's measured pH, not charge balance alone.

A routine water analysis carries a charge-balance error of a few percent.
Solving pH from charge balance turns that error into pH: on a brackish well a
0.5% change in chloride moves the calculated pH by about 0.5 units. Here the
measured pH is the boundary condition instead. Inorganic carbon comes from the
analysis or from titrated alkalinity, and the remaining charge is closed on
one named ion, as PHREEQC's ``charge`` option does. The imbalance and the
adjustment are returned, never applied silently.
"""
from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

from .aqueous_model import AqueousResult, chemistry, solve
from .delivery_contracts import DeliveryError

BALANCE_IONS = {'Cl-': -1, 'Na+': 1}
DEFAULT_MAXIMUM_IMBALANCE_PERCENT = 5.


@dataclass(frozen=True)
class BalancedWaterAnalysis:
    """Analytical totals (mol/kg water) closed at the measured pH, with their audit."""
    totals: dict
    measured_ph: float
    state: AqueousResult
    balance_ion: str
    analysed_balance_ion_molal: float
    balance_adjustment_molal: float
    imbalance_percent: float
    inorganic_carbon_molal: float
    carbon_source: str


def carbonate_alkalinity(state):
    """Carbonate alkalinity (eq/kg water) of a solved state.

    Each carbon species counts 2 x carbon - H+ relative to H2CO3; OH- and H+
    count +1 and -1. Phosphate, borate and organic bases are not included.
    """
    total = 0.
    for record in chemistry()['aqueous']:
        name = record['name']
        if name not in state.species:
            continue
        powers = record['powers']
        carbon = powers.get('CO3-2', 0.)
        protons = powers.get('H+', 0.)
        if carbon:
            total += state.species[name] * (2 * carbon - protons)
        elif set(powers) <= {'H+', 'H2O'}:
            total -= state.species[name] * protons
    return total


def _imbalance_percent(state):
    positive = negative = 0.
    charges = {r['name']: r['charge'] for r in chemistry()['aqueous']}
    for name, amount in state.species.items():
        charge = charges.get(name, 0)
        if charge > 0:
            positive += charge * amount
        elif charge < 0:
            negative -= charge * amount
    total = positive + negative
    return 0. if total == 0 else 100 * (positive - negative) / total


def _carbon_for_alkalinity(totals, ph, alkalinity, phases):
    """Total inorganic carbon whose speciation at pH gives the alkalinity."""
    def alk(carbon):
        return carbonate_alkalinity(solve(totals | {'CO3-2': carbon}, ph, phases=phases))
    base = carbonate_alkalinity(solve({k: v for k, v in totals.items() if k != 'CO3-2'}, ph, phases=phases))
    if alkalinity <= base:
        raise DeliveryError('alkalinity_out_of_range',
                            'measured alkalinity is not above the carbon-free alkalinity at the measured pH')
    low, high = 0., 1e-6
    while alk(high) < alkalinity:
        high *= 4
        if high > .1:
            raise DeliveryError('alkalinity_out_of_range', 'alkalinity requires more carbon than the Davies domain allows')
    for _ in range(200):
        middle = (low + high) / 2
        if alk(middle) < alkalinity:
            low = middle
        else:
            high = middle
        if high - low <= 1e-12 * high:
            break
    return (low + high) / 2


def balance_water_analysis(totals, *, measured_ph, alkalinity_eq_per_kg=None, balance_ion='Cl-',
                           maximum_imbalance_percent=DEFAULT_MAXIMUM_IMBALANCE_PERCENT,
                           phases=(), temperature_c=25.):
    """Close a complete water analysis at its measured pH.

    ``totals`` are analytical totals in mol/kg water. Supply inorganic carbon
    either as ``totals['CO3-2']`` or as ``alkalinity_eq_per_kg`` (titrated total
    alkalinity treated as carbonate alkalinity), never both. The charge left at
    the measured pH is closed by changing ``balance_ion``. An imbalance above
    ``maximum_imbalance_percent`` is rejected: fix the analysis, do not force it.
    """
    if not isinstance(totals, Mapping):
        raise DeliveryError('invalid_totals', 'analytical totals must be a mapping')
    for name, value in totals.items():
        if name not in chemistry()['bases']:
            raise DeliveryError('invalid_totals', f'unknown analytical component {name}')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise DeliveryError('invalid_totals', 'analytical totals must be finite nonnegative numbers')
    if isinstance(measured_ph, bool) or not isinstance(measured_ph, (int, float)) or not math.isfinite(measured_ph) \
            or not 0 <= measured_ph <= 14:
        raise DeliveryError('out_of_range', 'measured_ph must be finite in [0,14]')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError('temperature_out_of_range', 'water balancing requires the 25 C reaction set')
    if balance_ion not in BALANCE_IONS:
        raise DeliveryError('unsupported_balance_ion', f'balance_ion must be one of {sorted(BALANCE_IONS)}')
    if isinstance(maximum_imbalance_percent, bool) or not isinstance(maximum_imbalance_percent, (int, float)) \
            or not math.isfinite(maximum_imbalance_percent) or maximum_imbalance_percent <= 0:
        raise DeliveryError('invalid_value', 'maximum_imbalance_percent must be finite and positive')
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError('invalid_type', 'supply an explicit phase sequence, or [] for aqueous-only')
    phases = tuple(phases)
    totals = {k: float(v) for k, v in totals.items()}
    carbon_given = totals.get('CO3-2', 0) > 0
    if alkalinity_eq_per_kg is not None:
        if carbon_given:
            raise DeliveryError('ambiguous_carbon', 'supply inorganic carbon or alkalinity, not both')
        if isinstance(alkalinity_eq_per_kg, bool) or not isinstance(alkalinity_eq_per_kg, (int, float)) \
                or not math.isfinite(alkalinity_eq_per_kg) or alkalinity_eq_per_kg <= 0:
            raise DeliveryError('invalid_value', 'alkalinity_eq_per_kg must be finite and positive')
        carbon_source = 'alkalinity'
    elif carbon_given:
        carbon_source = 'inorganic_carbon'
    else:
        raise DeliveryError('missing_carbon', 'measured-pH balancing needs inorganic carbon or alkalinity')
    analysed = totals.get(balance_ion, 0.)
    if analysed <= 0:
        raise DeliveryError('missing_balance_ion', f'{balance_ion} must be present in the analysis to balance on it')

    working = dict(totals)
    if carbon_source == 'alkalinity':
        working['CO3-2'] = _carbon_for_alkalinity(working, measured_ph, alkalinity_eq_per_kg, phases)
    state = solve(working, measured_ph, phases=phases)
    imbalance = _imbalance_percent(state)
    if abs(imbalance) > maximum_imbalance_percent:
        raise DeliveryError('charge_imbalance_exceeded',
                            f'analysis charge imbalance {imbalance:.2f}% at measured pH exceeds '
                            f'{maximum_imbalance_percent:g}%')
    charge = BALANCE_IONS[balance_ion]
    for _ in range(100):
        if abs(state.charge_balance) <= 1e-12:
            break
        working[balance_ion] -= state.charge_balance / charge
        if working[balance_ion] <= 0:
            raise DeliveryError('balance_ion_exhausted', f'{balance_ion} cannot absorb the charge imbalance')
        if carbon_source == 'alkalinity':
            working['CO3-2'] = _carbon_for_alkalinity(working, measured_ph, alkalinity_eq_per_kg, phases)
        state = solve(working, measured_ph, phases=phases)
    else:
        raise DeliveryError('nonconvergent', 'measured-pH charge balance did not close')
    return BalancedWaterAnalysis(dict(working), float(measured_ph), state, balance_ion, analysed,
                                 working[balance_ion] - analysed, imbalance, working['CO3-2'], carbon_source)
