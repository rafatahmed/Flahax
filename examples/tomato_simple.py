#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Simple tomato example: one formula, RO water, one 1000 L batch.

Run from the repository root:  python -m examples.tomato_simple
"""

from flahax import (
    DeclaredPureWater,
    VolumeLitres,
    calculate_irrigation_ec,
    final_solution_recipe,
    load_library,
    recommend,
)

from .common import ec_summary

FORMULA = 'Tomato (Howard Resh)'  # shipped in the FlahaX catalogue
BATCH_LITRES = 1000


def run():
    library = load_library()
    targets = next(f['targets'] for f in library['formulas'] if f['name'] == FORMULA)

    # 1. Choose products and doses for the targets; RO water brings no nutrients.
    # Explicit illustrative allowance, not a default agronomic recommendation.
    result = recommend(library['salts'], targets, water={}, max_ammonium_fraction=0.10)

    # 2. Scale the recipe to a batch.
    batch = final_solution_recipe(result, VolumeLitres(BATCH_LITRES))

    # 3. Estimate the feed's EC at 25 C (experimental; g per kg water ~ g per litre here).
    doses = {s['name']: s['gramsPerLitre'] for s in result['salts']}
    ec = calculate_irrigation_ec(
        doses,
        recipe_id='tomato-simple',
        water=DeclaredPureWater('RO water'),
        ph_mode='calculated',
        phase_policy='dissolved',
    )

    identities = {s['name']: s['provenance']['identityId'] for s in result['salts']}
    return dict(
        formula=FORMULA,
        targets=targets,
        batch_litres=BATCH_LITRES,
        feasible=result['feasible'],
        recipe=[
            dict(
                id=s.salt_id,
                name=s.name,
                grams_per_litre=s.dose.value,
                grams_in_batch=s.mass.value,
                identity=identities[s.name],
            )
            for s in batch.salts
        ],
        nutrients=[
            dict(symbol=r['symbol'], target=r['target'], final=r['final'], deltaPct=r['deltaPct'])
            for r in result['rows']
            if r['target']
        ],
        incidental=[
            dict(symbol=r['symbol'], final=r['final'])
            for r in result['rows']
            if not r['target'] and r['final'] > 1e-6
        ],
        ion_balance=result['targetIonBalance'],
        unmet=result['unmetTargets'],
        warnings=result['warnings'],
        ec=dict(
            status=ec.status, ec25_ms_cm=ec.ec25_ms_cm, ph=ec.ph, range_ms_cm=ec.ec25_range_ms_cm
        ),
        assumptions=[
            'Shipped Howard Resh tomato formula; RO water with no nutrients.',
            'EC is the experimental speciation estimate (McCleskey 2012), not a measurement.',
            'Measure EC and pH after mixing; this is a planning calculation, not a dosing '
            'instruction.',
        ],
    )


def main():
    report = run()
    print(
        f"{report['formula']} in RO water: "
        f"{'every target met' if report['feasible'] else 'some targets missed'}"
    )
    print(f"\nWeigh for {report['batch_litres']} L:")
    for item in report['recipe']:
        print(
            f"  {item['name']:<38} {item['grams_in_batch']:9.1f} g   "
            f"({item['grams_per_litre']:.4f} g/L)"
        )
    print('\nNutrients (mg/L): target -> delivered')
    for row in report['nutrients']:
        print(
            f"  {row['symbol']:<6} {row['target']:8.2f} -> {row['final']:8.2f}  "
            f"({row['deltaPct']:+.2f}%)"
        )
    balance = report['ion_balance']
    print(
        f"\nFormula ion balance: cations {balance['cationsMeqPerL']:.1f} vs anions "
        f"{balance['anionsMeqPerL']:.1f} meq/L ({balance['imbalancePercent']:+.1f}%)"
    )
    ec = report['ec']
    print(ec_summary(ec))
    if ec['ph'] is not None and not 5.3 <= ec['ph'] <= 5.8:
        print(
            f"Mixed pH {ec['ph']:.2f} is outside the 5.3-5.8 feed range: plan an acid dose "
            "(see python -m examples.tomato_advanced)."
        )
    for line in report['assumptions']:
        print('  -', line)


if __name__ == '__main__':
    main()
