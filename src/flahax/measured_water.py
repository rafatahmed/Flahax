"""Source-water speciation from a laboratory's measured pH, not charge balance alone.

A routine water analysis carries a charge-balance error of a few percent.
Solving pH from charge balance turns that error into pH: on a brackish well a
0.5% change in chloride moves the calculated pH by about 0.5 units. Here the
measured pH is the boundary condition instead. Inorganic carbon comes from the
analysis or from titrated alkalinity, and the remaining charge is closed on
one named ion, as PHREEQC's ``charge`` option does. The imbalance and the
adjustment are returned, never applied silently.

Two inventories, two uses (#84). ``analytical_totals`` is the laboratory analysis
as entered: nutrient targets and concentration limits are always checked on it.
``totals`` is the charge-balanced model, an input to chemistry only (pH,
speciation, saturation, EC, reagent demand). Closing the charge on chloride or
sodium is a modelling assumption, not a corrected measurement.
"""
from dataclasses import dataclass, replace
import math
from collections.abc import Mapping, Sequence

from .aqueous_model import AqueousResult, chemistry, solve
from .calculated_ph import calculate_equilibrium_ph
from .delivery_contracts import DeliveryError
from .product_conversion import MOLAR_MASS
from .root_finding import shrink_bracket

BALANCE_IONS = {'Cl-': -1, 'Na+': 1}
DEFAULT_MAXIMUM_IMBALANCE_PERCENT = 5.
# Numerical closure, not an analytical screen: a composition whose charge residual at the measured pH
# is within this fraction of its total ionic charge (0.0001 %) is already balanced and left unchanged.
# Passing the 5 % screen above does not make an analysis balanced.
CLOSURE_TOLERANCE = 1e-6
UNITS = 'mol/kg water'
# Analytical basis -> nutrient symbol (mg/L of the element; N as N).
NUTRIENT_BASES = {'Ca+2': 'Ca', 'Mg+2': 'Mg', 'K+': 'K', 'Na+': 'Na', 'Cl-': 'Cl',
                  'NO3-': 'N_NO3', 'NH4+': 'N_NH4', 'PO4-3': 'P', 'SO4-2': 'S',
                  'Fe+3': 'Fe', 'Fe+2': 'Fe', 'Mn+2': 'Mn', 'Zn+2': 'Zn', 'Cu+2': 'Cu',
                  'H3BO3': 'B', 'MoO4-2': 'Mo', 'Ure': 'N_UREA'}


ASK_LAB = ('Ask your lab for chloride and sodium: FlahaX closes the analysis at its measured pH on chloride, '
           'so chloride must be measured and above zero.')


def nutrient_mg_per_litre(totals, water_mass_kg=1., final_volume_litres=1.):
    """Elemental mg/L in the final volume from water totals in mol/kg water."""
    ppm = {}
    for basis, ion in NUTRIENT_BASES.items():
        amount = totals.get(basis)
        if amount is None:
            continue
        value = amount * MOLAR_MASS[ion.split('_')[0]] * water_mass_kg * 1000 / final_volume_litres
        ppm[ion] = ppm.get(ion, 0) + value * (2 if basis == 'Ure' else 1)
    return ppm


@dataclass(frozen=True)
class BalancedWaterAnalysis:
    """A water analysis closed at its measured pH: the laboratory record and the model, kept apart.

    ``analytical_totals`` are the analysis as entered (mol/kg water) and decide every
    nutrient target and concentration limit. ``totals`` are the charge-balanced model
    used for chemistry. ``measured_ph`` and ``alkalinity_eq_per_kg`` are source
    measurements; ``state`` is the computed state of this (possibly diluted) water.
    ``dilution_fraction`` is the share of the source water in ion-free water.
    """
    totals: dict
    measured_ph: float
    state: AqueousResult
    balance_ion: str
    analysed_balance_ion_molal: float
    balance_adjustment_molal: float
    imbalance_percent: float
    inorganic_carbon_molal: float
    carbon_source: str
    analytical_totals: dict = None
    alkalinity_eq_per_kg: float | None = None
    analysis_id: str | None = None
    dilution_fraction: float = 1.
    phases: tuple = ()
    units: str = UNITS
    # 'unchanged' (closed within CLOSURE_TOLERANCE), 'reconciled' (within the stated uncertainty of
    # balance_ion) or 'assumed' (closed on balance_ion without a stated uncertainty: review).
    reconciliation: str = 'assumed'
    fixed: tuple = ()
    below_detection: dict = None        # component -> detection limit, mol/kg water
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
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) \
                or not 0 < fraction <= 1:
            raise DeliveryError('invalid_value', 'dilution fraction must be in (0, 1]')
        totals = {k: v * fraction for k, v in self.totals.items()}
        state = calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed',
                                         temperature_c=25, phases=list(self.phases))
        return replace(self, totals=totals, state=state,
                       analytical_totals={k: v * fraction for k, v in self.analytical_totals.items()},
                       analysed_balance_ion_molal=self.analysed_balance_ion_molal * fraction,
                       balance_adjustment_molal=self.balance_adjustment_molal * fraction,
                       inorganic_carbon_molal=self.inorganic_carbon_molal * fraction,
                       alkalinity_eq_per_kg=None if self.alkalinity_eq_per_kg is None
                       else self.alkalinity_eq_per_kg * fraction,
                       below_detection={k: v * fraction for k, v in self.below_detection.items()},
                       dilution_fraction=self.dilution_fraction * fraction)


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


def _total_charge(state):
    charges = {r['name']: r['charge'] for r in chemistry()['aqueous']}
    return sum(abs(charges.get(name, 0)) * amount for name, amount in state.species.items())


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
    last = [solve({k: v for k, v in totals.items() if k != 'CO3-2'}, ph, phases=phases)]

    def alk(carbon):
        last[0] = solve(totals | {'CO3-2': carbon}, ph, phases=phases, start=last[0])  # warm start, #61
        return carbonate_alkalinity(last[0])
    base = carbonate_alkalinity(last[0])
    if alkalinity <= base:
        raise DeliveryError('alkalinity_out_of_range',
                            'measured alkalinity is not above the carbon-free alkalinity at the measured pH')
    low, g_low, high = 0., base - alkalinity, 1e-6
    while (g_high := alk(high) - alkalinity) < 0:
        low, g_low = high, g_high
        high *= 4
        if high > .1:
            raise DeliveryError('alkalinity_out_of_range', 'alkalinity requires more carbon than the Davies domain allows')
    low, high = shrink_bracket(lambda carbon: alk(carbon) - alkalinity, low, g_low, high, g_high,
                               relative=1e-12)
    return (low + high) / 2


def balance_water_analysis(totals, *, measured_ph, alkalinity_eq_per_kg=None, balance_ion='Cl-',
                           maximum_imbalance_percent=DEFAULT_MAXIMUM_IMBALANCE_PERCENT,
                           phases=(), temperature_c=25., analysis_id=None, balance_ion_uncertainty_percent=None,
                           fixed=(), below_detection=None):
    """Close a complete water analysis at its measured pH.

    ``totals`` are analytical totals in mol/kg water. A component given as 0 is a
    measured zero and stays zero; an omitted component is not measured.
    ``below_detection`` maps components reported below detection to their
    detection limit (mol/kg); they enter the chemistry as 0, are recorded, and are
    never adjusted. Supply inorganic carbon either as ``totals['CO3-2']`` (0 for
    explicitly carbon-free water) or as ``alkalinity_eq_per_kg`` (titrated total
    alkalinity treated as carbonate alkalinity), never both.

    The composition is first speciated at the measured pH. If its charge closes
    within ``CLOSURE_TOLERANCE`` it is returned unchanged (``reconciliation`` is
    'unchanged') and no balance ion is needed. Otherwise an imbalance above
    ``maximum_imbalance_percent`` is rejected (fix the analysis, do not force it),
    and the rest is closed on ``balance_ion``, which must be measured, positive and
    not ``fixed``. With ``balance_ion_uncertainty_percent`` the adjustment must lie
    within that stated measurement uncertainty ('reconciled'); without it the
    closure is a modelling assumption ('assumed') that callers report for review.
    Nothing else is changed and no other ion is tried. The analysis itself is kept
    unchanged in ``analytical_totals`` (#84).
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
    below_detection = dict(below_detection or {})
    for name, limit in below_detection.items():
        if name not in chemistry()['bases'] or isinstance(limit, bool) or not isinstance(limit, (int, float)) \
                or not math.isfinite(limit) or limit <= 0:
            raise DeliveryError('invalid_value', 'below_detection maps analytical components to positive detection limits')
        if totals.get(name, 0.) != 0:
            raise DeliveryError('contradictory_water_inputs', f'{name} is reported both as a value and below detection')
        totals[name] = 0.
    # Measured zeros and below-detection components are held fixed, like any component named in ``fixed``.
    fixed = tuple(sorted(set(fixed) | {k for k, v in totals.items() if v == 0} | set(below_detection)))
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
    elif 'CO3-2' in totals:
        carbon_source = 'none'          # measured carbon-free, distinct from carbon not reported
    else:
        raise DeliveryError('missing_carbon', 'measured-pH balancing needs inorganic carbon or alkalinity '
                                              '(CO3-2 = 0 for water measured carbon-free)')
    if balance_ion_uncertainty_percent is not None and (
            isinstance(balance_ion_uncertainty_percent, bool)
            or not isinstance(balance_ion_uncertainty_percent, (int, float))
            or not math.isfinite(balance_ion_uncertainty_percent) or balance_ion_uncertainty_percent <= 0):
        raise DeliveryError('invalid_value', 'balance_ion_uncertainty_percent must be finite and positive')

    working = dict(totals)
    if carbon_source == 'alkalinity':
        working['CO3-2'] = _carbon_for_alkalinity(working, measured_ph, alkalinity_eq_per_kg, phases)
    state = solve(working, measured_ph, phases=phases)
    imbalance = _imbalance_percent(state)
    record = dict(analytical_totals=totals, alkalinity_eq_per_kg=alkalinity_eq_per_kg, analysis_id=analysis_id,
                  phases=phases, fixed=fixed, below_detection=below_detection,
                  balance_ion_uncertainty_percent=balance_ion_uncertainty_percent)
    if abs(state.charge_balance) <= CLOSURE_TOLERANCE * _total_charge(state):
        # Already balanced at the measured pH: nothing to reconcile, no balance ion needed.
        return BalancedWaterAnalysis(dict(working), float(measured_ph), state, None, 0., 0., imbalance,
                                     working.get('CO3-2', 0.), carbon_source, reconciliation='unchanged', **record)
    if abs(imbalance) > maximum_imbalance_percent:
        raise DeliveryError('charge_imbalance_exceeded',
                            f'analysis charge imbalance {imbalance:.2f}% at measured pH exceeds '
                            f'{maximum_imbalance_percent:g}%')
    if balance_ion not in BALANCE_IONS:
        raise DeliveryError('unsupported_balance_ion', f'balance_ion must be one of {sorted(BALANCE_IONS)}')
    analysed = totals.get(balance_ion, 0.)
    if balance_ion in fixed:
        raise DeliveryError('fixed_balance_ion',
                            f'the analysis is {imbalance:.2f}% out of balance and {balance_ion} is held fixed '
                            '(measured zero, below detection or named fixed); chemistry needs review or a further '
                            f'analysis. No other ion is adjusted automatically. {ASK_LAB}')
    if analysed <= 0:
        raise DeliveryError('missing_balance_ion', f'{balance_ion} must be present in the analysis to balance on it. {ASK_LAB}')
    charge = BALANCE_IONS[balance_ion]
    for _ in range(100):
        if abs(state.charge_balance) <= 1e-12:
            break
        working[balance_ion] -= state.charge_balance / charge
        if working[balance_ion] <= 0:
            raise DeliveryError('balance_ion_exhausted', f'{balance_ion} cannot absorb the charge imbalance. {ASK_LAB}')
        if carbon_source == 'alkalinity':
            working['CO3-2'] = _carbon_for_alkalinity(working, measured_ph, alkalinity_eq_per_kg, phases)
        state = solve(working, measured_ph, phases=phases, start=state)
    else:
        raise DeliveryError('nonconvergent', 'measured-pH charge balance did not close')
    adjustment = working[balance_ion] - analysed
    if balance_ion_uncertainty_percent is not None:
        if abs(adjustment) > balance_ion_uncertainty_percent / 100 * analysed:
            raise DeliveryError('reconciliation_out_of_bounds',
                                f'closing the charge needs {100 * adjustment / analysed:+.2f}% {balance_ion}, outside its '
                                f'stated ±{balance_ion_uncertainty_percent:g}% uncertainty; chemistry needs review or a '
                                'further analysis')
        reconciliation = 'reconciled'
    else:
        reconciliation = 'assumed'
    return BalancedWaterAnalysis(dict(working), float(measured_ph), state, balance_ion, analysed,
                                 adjustment, imbalance, working['CO3-2'], carbon_source,
                                 reconciliation=reconciliation, **record)
