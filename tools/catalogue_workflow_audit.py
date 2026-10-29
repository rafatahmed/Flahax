# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
"""Diagnostic minimax audit; does not change production targets or acceptance limits.

Run with PYTHONPATH=src and SciPy installed. Chemistry is assessed at natural pH,
without reagents. Review-only saturation never automatically enables a solid.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from flahax import calculate_equilibrium_ph, catalogue_dose_totals
from flahax.material_chemistry import material_chemistry
from flahax.materials import ResolvedMaterial
from flahax.saturation_policy import assess_saturation
from flahax.irrigation_ec import calculate_irrigation_ec, DeclaredPureWater
from flahax.stock_solubility import check_stock_solubility
from flahax.tank_grouping import group_tanks

N_FORMS = ('N_NO3', 'N_NH4', 'N_UREA')


def fit(products, original):
    targets = {'totalN': sum(original.get(k, 0) for k in N_FORMS)}
    targets.update({k: v for k, v in original.items()
                    if k not in ('N_NO3', 'N_UREA') and v > 0})
    keys = list(targets)
    goal = np.array(list(targets.values()), dtype=float)

    def rate(product, key):
        e = product['elements']
        return 10 * (sum(e.get(k, 0) for k in N_FORMS)
                     if key == 'totalN' else e.get(key, 0))

    matrix = np.array([[rate(p, k) for p in products] for k in keys])
    relative = matrix / goal[:, None]
    rows = np.vstack([np.column_stack([relative, -np.ones(len(keys))]),
                      np.column_stack([-relative, -np.ones(len(keys))])])
    bounds = np.r_[np.ones(len(keys)), -np.ones(len(keys))]
    cap = None
    if original.get('N_NH4', 0) == 0:
        cap = min(.1 * targets['totalN'], 1.5 * 14.0067)
        rows = np.vstack([rows, np.r_[[rate(p, 'N_NH4') for p in products], 0]])
        bounds = np.r_[bounds, cap]
    for k, v in original.items():
        if v == 0 and k not in N_FORMS:
            rows = np.vstack([rows, np.r_[[rate(p, k) for p in products], 0]])
            bounds = np.r_[bounds, 0]
    objective = np.r_[np.zeros(len(products)), 1]
    solved = linprog(objective, A_ub=rows, b_ub=bounds, bounds=(0, None))
    if not solved.success:
        raise ValueError(solved.message)
    alternate = linprog(objective, A_ub=rows, b_ub=bounds,
                        bounds=(0, None), method='highs-ipm')
    assert alternate.success and abs(alternate.fun - solved.fun) < 1e-7
    # Minimum total product mass breaks equally optimal nutrient-fit ties.
    chosen = linprog(np.r_[np.ones(len(products)), 0], A_ub=rows, b_ub=bounds,
                     bounds=[(0, None)] * len(products) + [(0, solved.fun + 1e-9)])
    assert chosen.success
    doses = chosen.x[:-1]
    actual = matrix @ doses
    error = (actual / goal - 1) * 100
    assert max(abs(error)) <= solved.fun * 100 + 1e-5
    return {
        'minimum_error_pct': float(solved.fun * 100),
        'nutrient_pass': bool(solved.fun <= .01 + 1e-9),
        'ammonium_ceiling_mg_l': cap,
        'nutrients': [dict(nutrient=k, target=float(t), actual=float(a), error_pct=float(e))
                      for k, t, a, e in zip(keys, goal, actual, error)],
        'salts': [dict(id=p['id'], name=p['name'], gramsPerLitre=float(g))
                  for p, g in zip(products, doses) if g > 1e-10],
    }


def phase_screen(totals):
    # Never turn reported supersaturation into automatic solid allocation.
    # The runtime policy owns missing-evidence blocking and review decisions.
    state = calculate_equilibrium_ph(totals, complete_analysis=True,
                                     carbon_boundary='closed', phases=[])
    assessment = assess_saturation(state)
    return {'ph': state.ph, 'ionic_strength': state.ionic_strength,
            'charge_balance': state.charge_balance,
            'saturation_indices': state.saturation_indices,
            'precipitated': state.precipitated, 'assessment': assessment}


def inspect_recipe(recipe, products):
    doses = {s['name']: s['gramsPerLitre'] for s in recipe['salts']}
    result = dict(recipe)
    try:
        result['chemistry'] = phase_screen(catalogue_dose_totals(doses, products=products))
        records = {p['name']: p for p in products}
        materials = {name: ResolvedMaterial(
            name=name, identity_id=records[name].get('identityId'), record=records[name],
            basis={k: 'declared_catalogue' for k in records[name]['elements']},
            band_minimum={k: None for k in records[name]['elements']},
            band_maximum={k: None for k in records[name]['elements']},
            composition='single', provenance={'sourceStatus': 'owner_supplied',
                'analysisReview': records[name].get('analysisReview')}) for name in doses}
        result['ec'] = asdict(calculate_irrigation_ec(
            doses, recipe_id='catalogue-audit', water=DeclaredPureWater('ideal-pure'),
            ph_mode='calculated', phase_policy='dissolved', phases=[], materials=materials))
    except Exception as exc:
        result['chemistry_error'] = {'code': getattr(exc, 'code', type(exc).__name__),
                                     'message': str(exc)}
    try:
        grouping = group_tanks(recipe['salts'], products)
        result['two_tank_fit'] = len(grouping.tanks) <= 2
        result['minimum_tank_count'] = len(grouping.tanks)
        result['grouping'] = asdict(grouping)
        result['stock_solubility'] = [asdict(r) for r in
                                      check_stock_solubility(grouping.tanks, 100, 25)]
        result['stock_kg_per_100_l'] = {
            t.name: {p.name: p.grams_per_litre * 10 for p in t.products}
            for t in grouping.tanks}
    except Exception as exc:
        result['stock_error'] = {'code': getattr(exc, 'code', type(exc).__name__),
                                 'message': str(exc)}
    return result


def audit(library, edta_only=False):
    products = [s for s in library['salts'] if s.get('role') != 'ph_reagent']
    if edta_only:
        products = [s for s in products if not {'Fe', 'Mn', 'Zn', 'Cu'} & set(s['elements'])
                    or s['name'] in {'Iron EDTA', 'Mn EDTA', 'Zn EDTA', 'Copper EDTA'}]
    supported, excluded = [], []
    for product in products:
        try:
            material_chemistry(product)
            supported.append(product)
        except Exception as exc:
            excluded.append({'name': product['name'], 'reason': str(exc)})
    results = []
    for formula in library['formulas']:
        primary = inspect_recipe(fit(products, formula['targets']), products)
        row = {'crop': formula['name'], 'all_available': primary}
        if 'chemistry_error' in primary:
            row['chemistry_supported_alternative'] = inspect_recipe(
                fit(supported, formula['targets']), supported)
        results.append(row)
        print(formula['name'], round(primary['minimum_error_pct'], 5),
              primary.get('chemistry_error', {}).get('code', 'chemistry calculated'), flush=True)
    return {'edta_only': edta_only, 'chemistry_exclusions_for_alternatives': excluded,
            'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path,
                        default=Path('src/flahax/data/library.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--edta-only', action='store_true')
    args = parser.parse_args()
    raw = args.catalogue.read_bytes()
    result = audit(json.loads(raw), args.edta_only)
    result['catalogue_sha256'] = hashlib.sha256(raw).hexdigest()
    result['assumptions'] = (
        'Pure ion-free water; closed carbon; 25 C; 1 L feed approximated as 1 kg water. '
        '100 L finished stocks A/B, each diluted 1:100; no pH reagent or pH/EC bounds. '
        'Total-N target replaces separate nitrate target; positive ammonium targets retained. '
        'Minimax relative nutrient error, then minimum total fertilizer mass. '
        'Stock checks are individual-product data checks, not mixed-stock validation. '
        'Phase screening is dissolved-only with existing review/block policy. '
        'Chemistry-supported alternatives are separate recipes, never substituted silently.')
    import subprocess
    result['runtime_revision'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    result['chemistry_sha256'] = hashlib.sha256(
        Path('src/flahax/data/chemistry_25c.json').read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
