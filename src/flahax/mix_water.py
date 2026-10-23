# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Water analysis entry for ``flahax mix``: lab units to the ``read_water`` format.

Each ion is one prompt: Enter = not measured (omitted), ``0`` = measured zero,
``<DL`` = below the detection limit DL (as printed, e.g. ``<0.02``). A blank is
never guessed. The grower types the report as printed; FlahaX converts.
"""

import math

from .product_conversion import MOLAR_MASS

HCO3, CACO3 = 61.0168, 50.0435
# Lab name -> (water key, g/mol of the ion as reported, charge, g/mol of the water key).
# Phosphate in meq/L is taken as H2PO4- (charge 1); the prompt says so.
IONS = {
    'Ca': ('Ca', MOLAR_MASS['Ca'], 2, MOLAR_MASS['Ca']),
    'Mg': ('Mg', MOLAR_MASS['Mg'], 2, MOLAR_MASS['Mg']),
    'K': ('K', MOLAR_MASS['K'], 1, MOLAR_MASS['K']),
    'Na': ('Na', MOLAR_MASS['Na'], 1, MOLAR_MASS['Na']),
    'NH4': ('N_NH4', 18.0385, 1, 14.0067),
    'NO3': ('N_NO3', 62.0049, -1, 14.0067),
    'Cl': ('Cl', MOLAR_MASS['Cl'], -1, MOLAR_MASS['Cl']),
    'SO4': ('S', 96.06, -2, 32.06),
    'PO4': ('P', 94.9712, -1, 30.973762),
    'Alk': ('HCO3', HCO3, -1, HCO3),
}
MICROS = ('Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo')
WATER_IONS = tuple(IONS) + MICROS
UNITS = ('mg', 'meq', 'mmol')
UNIT_TEXT = {'mg': 'mg/L', 'meq': 'meq/L', 'mmol': 'mmol/L', 'umol': 'µmol/L'}
WATER_SCREEN_PERCENT = 5.0


def to_elements(values, units, alkalinity, micro='mg'):
    """Lab values (``WATER_IONS`` names) in ``units`` to the ``read_water`` keys in mg/L.

    Micronutrients are in ``micro`` (``mg`` of the element or ``umol``) whatever ``units`` is.
    """
    out = {}
    for ion, value in values.items():
        if ion in MICROS:
            out[ion] = float(value) * (MOLAR_MASS[ion] / 1000 if micro == 'umol' else 1)
            continue
        key, ion_mass, charge, key_mass = IONS[ion]
        if units == 'mg':
            factor = (
                HCO3 / CACO3 if ion == 'Alk' and alkalinity == 'CaCO3' else key_mass / ion_mass
            )
        elif units == 'mmol':
            factor = key_mass * (2 if ion == 'Alk' and alkalinity == 'CaCO3' else 1)
        else:  # meq: one meq of alkalinity is one meq of HCO3 however it is reported
            factor = key_mass / abs(charge)
        out[key] = float(value) * factor
    return out


def water_balance(mg):
    """(cations, anions meq/L, % apart, contributions by lab name) of ``read_water`` keys."""
    parts = {}
    for ion, (key, _, charge, key_mass) in IONS.items():
        if key in mg:
            parts[ion] = mg[key] / key_mass * charge
    cations = sum(v for v in parts.values() if v > 0)
    anions = -sum(v for v in parts.values() if v < 0)
    apart = 100 * abs(cations - anions) / (cations + anions) if cations + anions else 0.0
    return cations, anions, apart, parts


def lab_entry(answer):
    """``''`` -> (None, None); ``'0.4'`` -> (0.4, None); ``'<0.02'`` -> (None, 0.02). ValueError
    otherwise."""
    answer = answer.strip().replace(' ', '')
    if not answer:
        return None, None
    below = answer.startswith('<')
    value = float(answer[1:] if below else answer)
    if not math.isfinite(value) or value < 0 or (below and value == 0):
        raise ValueError(answer)
    return (None, value) if below else (value, None)


def ask_ion(p, label):
    """One laboratory value, asked again until it is a number, 0, ``<limit`` or blank (not
    measured).
    """
    while True:
        answer = p.ask(
            f'{label} (Enter = not measured, 0 = measured zero, <DL = below detection, e.g. '
            f'<0.02): '
        )
        try:
            return lab_entry(answer)
        except ValueError:
            p.say(f'  {answer.strip()!r}: type a number, 0, <limit, or Enter.')


def ask_analysis(p, store):
    """(saved name, ``read_water`` data) for a new analysis; asks again on a large imbalance if
    wished."""
    while True:
        name = p.new_name(store, 'waters', 'Name of this analysis (e.g. well 104)')
        units = UNITS[
            p.choose(
                'Units as printed on the report',
                ['mg/L of each ion (NO3, SO4, PO4 as the ion)', 'meq/L', 'mmol/L'],
            )
        ]
        alkalinity = ('HCO3', 'CaCO3')[p.choose('Alkalinity reported as', ['HCO3', 'CaCO3'])]
        micro = 'mg'
        if units != 'mg':
            micro = ('mg', 'umol')[
                p.choose('Micronutrients on your report in', ['mg/L', 'µmol/L'])
            ]
        ph = p.number('Measured pH', high=14, positive=True)
        values, below = {}, {}

        def label_of(ion):
            unit = UNIT_TEXT[micro if ion in MICROS else units]
            label = f'Alkalinity as {alkalinity}' if ion == 'Alk' else ion
            return label + (
                ', meq/L as H2PO4-' if ion == 'PO4' and units == 'meq' else f', {unit}'
            )

        def keep(ion, value, limit):
            values.pop(ion, None), below.pop(ion, None)
            if value is not None:
                values[ion] = value
            if limit is not None:
                below[ion] = limit

        for ion in WATER_IONS:
            label = label_of(ion)
            value, limit = ask_ion(p, label)
            if ion == 'Alk' and value is None and limit is None:
                p.say(
                    '  Without alkalinity the pH plan will be blocked: FlahaX needs the '
                    'carbonate in the water.'
                )
                if p.choose('Alkalinity', ['Enter it', 'Record it as measured zero'], None) == 0:
                    while value is None and limit is None:
                        value, limit = ask_ion(p, label)
                else:
                    value = 0.0
            keep(ion, value, limit)
        while True:
            mg = to_elements(values, units, alkalinity, micro)
            cations, anions, apart, parts = water_balance(mg)
            p.say(
                f'Charge balance: cations {cations:.2f} meq/L, anions {anions:.2f} meq/L, '
                f'{apart:.1f} % apart.'
            )
            if apart <= WATER_SCREEN_PERCENT:
                break
            big = sorted(parts, key=lambda ion: -abs(parts[ion]))[:3]
            p.say(
                f'Warning: cations and anions are {apart:.1f} % apart (screen '
                f'{WATER_SCREEN_PERCENT:g} %). '
                'Largest: '
                + ', '.join(f'{ion} {abs(parts[ion]):.2f} meq/L' for ion in big)
                + '. Check the units, and that NO3, SO4 and PO4 are the ion, not N, S or P.'
            )
            pick = p.choose(
                '', ['Correct a value', 'Continue with it', 'Start this analysis again']
            )
            if pick != 0:
                break
            shown = [
                f'{ion}: '
                + (
                    f'<{below[ion]:g}'
                    if ion in below
                    else 'not measured'
                    if ion not in values
                    else f'{values[ion]:g}'
                )
                for ion in WATER_IONS
            ]
            ion = WATER_IONS[p.choose('Which value?', shown)]
            keep(ion, *ask_ion(p, label_of(ion)))
        if apart > WATER_SCREEN_PERCENT and pick == 2:
            continue
        data = {'id': name, 'measured_ph': ph, 'mg_per_litre': mg}
        if below:
            data['below_detection'] = to_elements(below, units, alkalinity, micro)
        return name, data
