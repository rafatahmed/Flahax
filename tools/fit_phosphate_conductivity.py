#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Fit 25 C H2PO4- and HPO4-2 conductivity coefficients to Pethybridge et al. (2006) Table III.

Decision O1 (design spec section 13). Each Table III point is speciated with FlahaX at
calculated pH (closed carbon, no phases). The covered species use McCleskey (2012) Eq. 8;
uncovered minor species (KHPO4-, PO4-3, ...) are left out of the model conductivity and
their O2 bound share is reported. lambda0 and A of H2PO4- and HPO4-2 are fitted by weighted
linear least squares (weight 1/kappa^2, i.e. relative residuals) with B fixed at 1.5.

Prints the supplementary JSON block on stdout; --write stores it in the shipped coefficient
file; --residuals prints the per-point residual table instead.
Run with PYTHONPATH="src;." (PowerShell: $env:PYTHONPATH="src;.").
"""

import argparse
import json
import math
from pathlib import Path

from flahax.aqueous_model import linear
from flahax.calculated_ph import calculate_equilibrium_ph
from flahax.irrigation_ec import LAMBDA_MAX_PER_CHARGE, _charges, ionic_molal_conductivity

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/conductivity/pethybridge2006_table3.json'
DESTINATION = ROOT / 'src/flahax/data/conductivity_mccleskey2012.json'
# Density of pure water at 25 C, kg/dm3 (recorded constant): mmol/dm3 -> mol/kgw.
WATER_DENSITY_KG_DM3 = 0.997047
B_FIXED = 1.5
FITTED = ('H2PO4-', 'HPO4-2')
CROSS_CHECKS = {
    'CRC': {
        'H2PO4-': 36.0,
        'HPO4-2': 114.0,
        'reference': 'CRC Handbook 85th ed., Vanysek, Ionic Conductivity and Diffusion at '
        'Infinite Dilution (57 for 1/2 HPO4-2, 114 molar)',
    },
    'Pethybridge_Lee_Wheaton': {
        'H2PO4-': 33.33,
        'HPO4-2': 115.14,
        'reference': 'Pethybridge et al. (2006) Table IV, K salts '
        '(57.57 for 1/2 HPO4-2, 115.14 molar)',
    },
    'phreeqc_dat': {
        'H2PO4-': 31.8,
        'HPO4-2': 103.6,
        'reference': 'phreeqc.dat diffusion coefficients, z^2 F^2 D / RT',
    },
}
GAP_LIMIT_PERCENT = 15.0
KHPO4_NOTE = (
    'KHPO4- is not covered; the fitted HPO4-2 coefficients absorb part of its current, '
    'so when FlahaX bounds KHPO4- as uncovered in a mixture the upper end of the range '
    'counts that current twice - small (<= 1.7 % of kappa at the most concentrated fit '
    'point) and conservative.'
)


def points(fixture):
    """Yield (salt, c mmol/dm3, Lambda, totals mol/kgw, kappa_obs mS/cm) for every Table III
    row."""
    for c, molar in fixture['KH2PO4']:
        m = c / 1000 / WATER_DENSITY_KG_DM3
        yield 'KH2PO4', c, molar, {'K+': m, 'PO4-3': m}, molar * c / 1000
    for c, molar in fixture['K2HPO4_half']:
        # Half-formula units: salt molarity c/2, so K+ = c and PO4 = c/2.
        m = c / 1000 / WATER_DENSITY_KG_DM3
        yield 'K2HPO4_half', c, molar, {'K+': m, 'PO4-3': m / 2}, molar * c / 1000


def _speciate(totals):
    return calculate_equilibrium_ph(
        totals, complete_analysis=True, carbon_boundary='closed', phases=[]
    )


def _row(state):
    """Known (covered, non-fitted) kappa, design-row terms, uncovered bound and I for one state."""
    from flahax.irrigation_ec import load_conductivity_coefficients

    species_map = load_conductivity_coefficients()['species_map']
    charges = _charges()
    strength = state.ionic_strength
    root = math.sqrt(strength)
    damping = root / (1 + B_FIXED * root)
    known = bound = 0.0
    design = [0.0] * 4
    for name, molal in state.species.items():
        charge = charges.get(name, 0)
        if not charge or molal <= 1e-12:
            continue
        if name in FITTED:
            k = FITTED.index(name)
            design[2 * k] += molal
            design[2 * k + 1] -= molal * damping
        elif name in species_map:
            known += ionic_molal_conductivity(species_map[name], strength) * molal
        else:
            bound += abs(charge) * LAMBDA_MAX_PER_CHARGE * molal
    return known, design, bound, strength


def fit(fixture_path=FIXTURE):
    """Return (supplementary block, residual rows) from the Table III fixture."""
    fixture = json.loads(Path(fixture_path).read_text(encoding='utf-8'))
    rows = []
    for salt, c, molar, totals, kappa in points(fixture):
        known, design, bound, strength = _row(_speciate(totals))
        rows.append(
            {
                'salt': salt,
                'c_mmol_dm3': c,
                'Lambda': molar,
                'kappa_obs_ms_cm': kappa,
                'known': known,
                'design': design,
                'bound': bound,
                'ionic_strength': strength,
            }
        )
    # Weighted normal equations, weight 1/kappa^2: minimise sum((model - obs)/obs)^2.
    normal = [[0.0] * 4 for _ in range(4)]
    rhs = [0.0] * 4
    for r in rows:
        w = 1 / r['kappa_obs_ms_cm'] ** 2
        target = r['kappa_obs_ms_cm'] - r['known']
        for i in range(4):
            rhs[i] += w * r['design'][i] * target
            for j in range(4):
                normal[i][j] += w * r['design'][i] * r['design'][j]
    x = linear(normal, rhs)
    residuals = []
    for r in rows:
        model = r['known'] + sum(d * v for d, v in zip(r['design'], x))
        residuals.append(
            {
                'salt': r['salt'],
                'c_mmol_dm3': r['c_mmol_dm3'],
                'Lambda': r['Lambda'],
                'kappa_obs_ms_cm': r['kappa_obs_ms_cm'],
                'kappa_model_ms_cm': model,
                'residual_percent': 100 * (model - r['kappa_obs_ms_cm']) / r['kappa_obs_ms_cm'],
                'ionic_strength': r['ionic_strength'],
                'uncovered_bound_percent': 100 * r['bound'] / r['kappa_obs_ms_cm'],
            }
        )
    fitted = {
        ion: {'lambda0_25c': x[2 * k], 'A_25c': x[2 * k + 1], 'B': B_FIXED}
        for k, ion in enumerate(FITTED)
    }
    checks = {}
    for name, ref in CROSS_CHECKS.items():
        entry = {'reference': ref['reference']}
        for ion in FITTED:
            gap = 100 * (fitted[ion]['lambda0_25c'] - ref[ion]) / ref[ion]
            entry[ion] = {'lambda0': ref[ion], 'gap_percent': gap}
            if abs(gap) > GAP_LIMIT_PERCENT:
                entry[ion]['note'] = f'gap exceeds {GAP_LIMIT_PERCENT} %'
        checks[name] = entry
    rms = math.sqrt(sum(p['residual_percent'] ** 2 for p in residuals) / len(residuals))
    block = {
        **fitted,
        'units': 'mS kg cm-1 mol-1 (as McCleskey Table 1); 25 C only',
        'equation': 'lambda = lambda0_25c - A_25c * sqrt(I) / (1 + B * sqrt(I))',
        'source': {
            'citation': fixture['source']['citation'],
            'doi': fixture['source']['doi'],
            'table': 'III',
        },
        'fit': {
            'method': 'weighted linear least squares, weight 1/kappa^2, B fixed; FlahaX '
            'speciation at calculated pH; uncovered minor species excluded',
            'rms_percent': rms,
            'points': len(residuals),
            'max_abs_residual_percent': max(abs(p['residual_percent']) for p in residuals),
            'max_ionic_strength': max(p['ionic_strength'] for p in residuals),
            'max_uncovered_bound_percent': max(p['uncovered_bound_percent'] for p in residuals),
            'density_kg_dm3': WATER_DENSITY_KG_DM3,
            'note': KHPO4_NOTE,
        },
        'cross_checks': checks,
    }
    return block, residuals


def write(block, destination=DESTINATION):
    data = json.loads(destination.read_text(encoding='utf-8'))
    data['supplementary'] = block
    destination.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='store the block in the shipped file')
    parser.add_argument('--residuals', action='store_true', help='print the residual table')
    args = parser.parse_args()
    block, residuals = fit()
    if args.residuals:
        print('salt         c(mmol/dm3)  Lambda   kappa_obs  kappa_fit  resid%   I         bound%')
        for p in residuals:
            print(
                f"{p['salt']:<12} {p['c_mmol_dm3']:>10.4f}  {p['Lambda']:>7.2f}  "
                f"{p['kappa_obs_ms_cm']:>9.6f}  {p['kappa_model_ms_cm']:>9.6f}  "
                f"{p['residual_percent']:>+7.3f}  {p['ionic_strength']:.6f}  "
                f"{p['uncovered_bound_percent']:.4f}"
            )
        return
    print(json.dumps(block, indent=1, ensure_ascii=False))
    if args.write:
        write(block)


if __name__ == '__main__':
    main()
