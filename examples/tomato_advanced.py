#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Advanced tomato example: a published brackish well, from laboratory analysis to batch plan.

Steps: balance the well analysis at its measured pH (for chemistry only); choose the largest blend with
desalinated water that keeps Na and Cl within open-system limits; formulate Dutch
tomato targets on that water; speciate the mix (pH, saturation indices); evaluate
nitric and phosphoric acid; estimate EC; group concentrates into compatible tanks
from a cited table; size injection; and compare growth-stage formulas, each as its
own batch.

Run from the repository root:  python -m examples.tomato_advanced
"""

from flahax import (
    VolumeLitres,
    balance_water_analysis,
    group_tanks,
    calculate_ec_from_totals,
    load_library,
    plan_acid_options,
    plan_catalogue_nitric_target,
    plan_fertilizer_workflow,
    recommend,
    size_injection_requirements,
)
from flahax.product_conversion import MOLAR_MASS
from flahax.tank_grouping import ANALOGUE

# Shomar et al. (2024), Groundwater, doi:10.1111/gwat.13411, supplementary Table S1, station 104
# (Qatar). Measured pH 7.80; mg/L; CO3-2 is total inorganic carbon expressed as C.
WELL_MG_L = {
    'Na+': 680,
    'K+': 44.2,
    'Ca+2': 244,
    'Mg+2': 100.8,
    'Cl-': 1280.4,
    'SO4-2': 723.3,
    'NO3-': 15.38,
    'CO3-2': 38.75,
}
GRAMS_PER_MOL = {
    'Na+': 22.98977,
    'K+': 39.0983,
    'Ca+2': 40.078,
    'Mg+2': 24.305,
    'Cl-': 35.45,
    'SO4-2': 96.06,
    'NO3-': 62.004,
    'CO3-2': 12.011,
}
WELL_PH = 7.8

# Raw-water limits for open systems with drain: 3 mmol/L Na and Cl
# (De Kreij, Voogt and Baas 2003, PPO Brochure 191, p. 6).
LIMITS_MG_L = {'Na': 3 * 22.98977, 'Cl': 3 * 35.45}

# Tomato, open system: De Kreij, Voogt and Baas (1999), Brochure 196, Supplement 2, p. 32.
MMOL = {
    'N_NO3': (16.0, 'N'),
    'N_NH4': (1.2, 'N'),
    'P': (1.5, 'P'),
    'K': (9.5, 'K'),
    'Ca': (5.4, 'Ca'),
    'Mg': (2.4, 'Mg'),
    'S': (4.4, 'S'),
}
UMOL = {'Fe': 15, 'Mn': 10, 'Zn': 5, 'B': 30, 'Cu': 0.75, 'Mo': 0.5}
TARGET_PH = 5.5  # root-environment pH in the same table

# EXAMPLE acid grades, not a supplier's certificate: replace with your product's assay and density.
ACIDS = [
    dict(
        schemaVersion='0.1',
        id=f'{formula}-example',
        source='EXAMPLE GRADE - use your certificate',
        revision='1',
        recordedAt='2026-10-21T00:00:00Z',
        chemicalFormula=formula,
        massFraction=fraction,
        densityKgPerL=density,
    )
    for formula, fraction, density in (('HNO3', 0.60, 1.37), ('H3PO4', 0.75, 1.58))
]

# Phosphoric acid is in the catalogue as a P source; on this water it over-acidifies the feed.
PHOSPHORIC = 'Phosphoric Acid (75%)'
BATCH_LITRES = 1000
INJECTION_RATIO = 100  # final litres per litre of each concentrate (1:100)
# Illustrative irrigation event for sizing: 1000 m2 greenhouse, 5 mm in 1 hour.
SITE = dict(active_area_m2=1000, gross_depth_mm=5, duration_hours=1, equipment_type='dosatron')
STAGES = [
    'Tomato Stage.1 - 10-14 days (Howard Resh)',
    'Tomato Stage.2 - first cluster (Howard Resh)',
    'Tomato Stage.3 - to plant maturity (Howard Resh)',
]


def targets():
    macro = {k: v * MOLAR_MASS[element] for k, (v, element) in MMOL.items()}
    return macro | {k: v * MOLAR_MASS[k] / 1000 for k, v in UMOL.items()}


def water_mg_l(totals):
    """Nutrient and salinity mg/L of a water (1 kg water per litre) from mol/kg totals."""
    keys = {'Ca+2': 'Ca', 'Mg+2': 'Mg', 'K+': 'K', 'Na+': 'Na', 'SO4-2': 'S'}
    out = {k: totals[b] * MOLAR_MASS[k] * 1000 for b, k in keys.items()}
    out['N_NO3'] = totals['NO3-'] * MOLAR_MASS['N'] * 1000
    out['Cl'] = totals['Cl-'] * 35.45 * 1000
    return out


def largest_blend(balanced):
    """Largest whole-percent share of well water whose Na and Cl stay within LIMITS_MG_L.

    Decided on the laboratory analysis, never on the charge-balanced model (#84).
    """
    for percent in range(100, 0, -1):
        water = water_mg_l({k: v * percent / 100 for k, v in balanced.analytical_totals.items()})
        if all(water[ion] <= limit for ion, limit in LIMITS_MG_L.items()):
            return percent
    return 0


def tank_table(salts, products):
    """The packaged default grouping (flahax.group_tanks) in the shape this report prints."""
    grouping = group_tanks(salts, products)
    return dict(
        source=grouping.source,
        separations=grouping.separations,
        tanks={
            t.name: dict(
                products=[
                    dict(
                        name=p.name,
                        analogue=ANALOGUE.get(p.name, 'by composition'),
                        gramsPerLitre=p.grams_per_litre,
                        basis=p.basis,
                    )
                    for p in t.products
                ],
                notes=list(t.notes),
            )
            for t in grouping.tanks
        },
    )


def run():
    library = load_library()
    salts = library['salts']
    goal = targets()

    # 1. The laboratory analysis is 3.5% out of charge balance; anchor it at the measured pH.
    well = {ion: mg / GRAMS_PER_MOL[ion] / 1000 for ion, mg in WELL_MG_L.items()}
    balanced = balance_water_analysis(well, measured_ph=WELL_PH)

    # 2. Blend with desalinated (ion-free) water until Na and Cl meet the open-system limits,
    #    on the laboratory values. The balanced model (Cl -9.5%) is for the chemistry only.
    percent = largest_blend(balanced)
    blend_water = balanced.diluted(percent / 100)
    blend = blend_water.totals  # chemistry
    blend_mg_l = water_mg_l(blend_water.analytical_totals)  # nutrients and limits
    blends = [
        dict(
            well_percent=p,
            **{
                k: round(v, 1)
                for k, v in water_mg_l(
                    {k: v * p / 100 for k, v in balanced.analytical_totals.items()}
                ).items()
            },
            Cl_model=round(
                water_mg_l({k: v * p / 100 for k, v in balanced.totals.items()})['Cl'], 1
            ),
        )
        for p in sorted({100, 25, percent + 1, percent}, reverse=True)
    ]

    # 3. Formulate on the blend and speciate the mix. With the whole catalogue the fit takes P
    #    from phosphoric acid and the feed ends far below the target pH; without it, potassium
    #    phosphate supplies P and both acids are evaluated against the targets.
    def plan(products):
        return plan_fertilizer_workflow(
            products,
            goal,
            blend_mg_l,
            TARGET_PH,
            final_volume=VolumeLitres(BATCH_LITRES),
            equilibrium=dict(
                water_balance=blend_water,
                water_mass_kg=BATCH_LITRES,
                complete_analysis=True,
                water_analysis_id=f'station-104-{percent}pct',
                carbon_boundary='closed',
                temperature_c=25,
                phases=[],
            ),
        )

    with_phosphoric = plan(salts)
    workflow = plan([s for s in salts if s['name'] != PHOSPHORIC])
    recipe = workflow.recommendation
    chemistry = workflow.stages['chemistry'].value
    mixed = chemistry['mixed']

    # 4. Acid to the target pH. Each acid is evaluated on the mixed feed and its nutrients are
    #    rescored against the targets; a plan with a supersaturated phase is not accepted.
    achieved = {row['symbol']: row['final'] for row in recipe['rows']}
    options = plan_acid_options(
        mixed.totals,
        mixed.ph,
        TARGET_PH,
        products=ACIDS,
        water_mass_kg=BATCH_LITRES,
        final_volume_litres=BATCH_LITRES,
        achieved=achieved,
        targets=goal,
        maximum_nutrient_error_percent=5,
        maximum_reagent_volume_litres=2,
    )
    # The nitric demand itself, computed directly so it is reported even when no plan is accepted.
    doses = {s['name']: s['gramsPerLitre'] for s in recipe['salts']}
    nitric = plan_catalogue_nitric_target(doses, mixed.ph, TARGET_PH, water_totals=blend)
    grade = ACIDS[0]
    nitric_ml = (
        nitric.nitric_acid_molal
        * BATCH_LITRES
        * 63.01
        / grade['massFraction']
        / grade['densityKgPerL']
    )
    added_n = nitric.nitric_acid_molal * MOLAR_MASS['N'] * 1000
    nitrate = next(row for row in recipe['rows'] if row['symbol'] == 'N_NO3')
    risky = sorted(
        (
            (p, s)
            for p, s in nitric.target.saturation_indices.items()
            if isinstance(s, float) and s > 0
        ),
        key=lambda item: -item[1],
    )

    # 5. EC of the feed before and after the acid (experimental speciation estimate).
    ec = {
        label: calculate_ec_from_totals(
            state.totals,
            solution_id=f'tomato-{label}',
            ph_mode='supplied',
            ph=state.ph,
            phase_policy='dissolved',
        )
        for label, state in (('mixed', mixed), ('acidified', nitric.target))
    }

    # 6. Concentrate tanks from the cited compatibility table, then injection sizing.
    tanks = tank_table(recipe['salts'], salts)
    channels = {
        name: dict(final_litres_per_stock_litre=INJECTION_RATIO, available_stock_litres=50)
        for name in tanks['tanks']
    }
    sizing = size_injection_requirements(channels=channels, **SITE)

    # 7. Growth stages: each stage formula is its own batch calculation on the same water.
    stages = []
    for name in STAGES:
        stage_targets = next(f['targets'] for f in library['formulas'] if f['name'] == name)
        result = recommend(salts, stage_targets, blend_mg_l)
        stages.append(
            dict(
                stage=name,
                feasible=result['feasible'],
                worst_miss_percent=max(
                    abs(r['deltaPct']) for r in result['rows'] if r['deltaPct'] is not None
                ),
                ion_imbalance_percent=result['targetIonBalance']['imbalancePercent'],
                unmet=[(u['symbol'], u['reason']) for u in result['unmetTargets']],
                doses={s['name']: s['gramsPerLitre'] for s in result['salts']},
            )
        )

    return dict(
        well=dict(
            analysis_mg_l=WELL_MG_L,
            measured_ph=WELL_PH,
            imbalance_percent=balanced.imbalance_percent,
            chloride_adjustment_percent=100
            * balanced.balance_adjustment_molal
            / balanced.analysed_balance_ion_molal,
        ),
        limits_mg_l=LIMITS_MG_L,
        blend_percent=percent,
        blends=blends,
        targets=goal,
        target_ph=TARGET_PH,
        chloride_boundary_percent=100 * LIMITS_MG_L['Cl'] / WELL_MG_L['Cl-'],
        phosphoric_check=dict(
            phosphoric_g_per_litre=next(
                (
                    x['gramsPerLitre']
                    for x in with_phosphoric.recommendation['salts']
                    if x['name'] == PHOSPHORIC
                ),
                0.0,
            ),
            mixed_ph=with_phosphoric.stages['chemistry'].value['mixed'].ph,
            feasible=with_phosphoric.recommendation['feasible'],
        ),
        recipe=dict(
            feasible=recipe['feasible'],
            salts=recipe['salts'],
            rows=[r for r in recipe['rows'] if r['target'] or r['final'] > 1e-6],
            ion_balance=recipe['targetIonBalance'],
            unmet=recipe['unmetTargets'],
            warnings=recipe['warnings'],
        ),
        chemistry=dict(
            water_ph=chemistry['water'].ph,
            mixed_ph=mixed.ph,
            ionic_strength=mixed.ionic_strength,
            saturation=sorted(
                (
                    (p, s)
                    for p, s in mixed.saturation_indices.items()
                    if isinstance(s, float) and s > -1
                ),
                key=lambda item: -item[1],
            ),
        ),
        acid=dict(
            selected=options.selected_product_id,
            candidates=[
                dict(
                    product=c.product_id,
                    status=c.status,
                    message=c.message,
                    volume_litres=c.reagent_volume_litres,
                )
                for c in options.candidates
            ],
            nitric_ml_per_batch=nitric_ml,
            nitric_grade=f"{grade['massFraction']:.0%} HNO3, {grade['densityKgPerL']} kg/L",
            added_nitrate_n_mg_l=added_n,
            nitrate_target_mg_l=nitrate['target'],
            nitrate_before_mg_l=nitrate['final'],
            nitrate_after_mg_l=nitrate['final'] + added_n,
            supersaturated_after_acid=risky,
        ),
        ec={
            label: dict(
                status=r.status, ec25_ms_cm=r.ec25_ms_cm, ph=r.ph, range_ms_cm=r.ec25_range_ms_cm
            )
            for label, r in ec.items()
        },
        tanks=tanks,
        injection_ratio=INJECTION_RATIO,
        site=SITE,
        sizing=sizing,
        stages=stages,
        assumptions=[
            'Well: Shomar et al. (2024) station 104, measured pH 7.80; desalinated water taken as ion-free.',
            'Na and Cl limits: 3 mmol/L each, De Kreij, Voogt and Baas (2003), open systems; checked on the '
            'laboratory analysis. The charge-balanced water (Cl closed) is used only for pH, saturation and EC.',
            'Targets: De Kreij, Voogt and Baas (1999) tomato, open system; target pH 5.5 from the same table.',
            'Phosphoric acid is withdrawn as a P source because, on this water, it drives the feed below the target pH.',
            'Acid grades are EXAMPLES (60% HNO3 1.37 kg/L; 75% H3PO4 1.58 kg/L); use your certificate.',
            'Tank grouping is the packaged default (flahax.group_tanks): Yara page 63/65 rules, micronutrients and '
            'chelates in tank A, which is never acidified. Stock solubility is not verified.',
            'Site figures for injection sizing are illustrative.',
            'Positive saturation indices mean a precipitation risk, not a predicted rate; measure after mixing.',
        ],
    )


def main():
    r = run()
    w = r['well']
    print(
        f"Well: {w['imbalance_percent']:.2f}% charge imbalance at pH {w['measured_ph']}, "
        f"closed by {w['chloride_adjustment_percent']:+.1f}% Cl"
    )
    print('Blend check (mg/L):  well %   Na     Cl     Ca     S')
    for b in r['blends']:
        print(
            f"                      {b['well_percent']:>4}  {b['Na']:6.1f} {b['Cl']:6.1f} {b['Ca']:6.1f} {b['S']:6.1f}"
        )
    print(
        f"-> use {r['blend_percent']}% well water (Na <= {r['limits_mg_l']['Na']:.1f}, Cl <= {r['limits_mg_l']['Cl']:.1f})"
    )
    pc = r['phosphoric_check']
    print(
        f"\nWhole catalogue: {pc['phosphoric_g_per_litre'] * BATCH_LITRES:.0f} g phosphoric acid per batch -> "
        f"feed pH {pc['mixed_ph']:.2f}, below the {r['target_ph']} target. Phosphoric acid is removed below."
    )
    rec = r['recipe']
    print(
        f"\nRecipe on the blend: {'every target met' if rec['feasible'] else 'targets missed'}; "
        f"ion balance {rec['ion_balance']['imbalancePercent']:+.1f}%"
    )
    for s in rec['salts']:
        print(f"  {s['name']:<38} {s['gramsPerLitre'] * BATCH_LITRES:8.1f} g per {BATCH_LITRES} L")
    c = r['chemistry']
    print(
        f"\npH: blend water {c['water_ph']:.2f}, mixed feed {c['mixed_ph']:.2f}; target {r['target_ph']}"
    )
    print('Saturation indices > -1:', ', '.join(f'{p} {s:.2f}' for p, s in c['saturation']))
    a = r['acid']
    for c in a['candidates']:
        print(f"Acid {c['product']}: {c['status']} - {c['message']}")
    print(
        f"Nitric demand to pH {r['target_ph']}: {a['nitric_ml_per_batch']:.0f} mL of {a['nitric_grade']} "
        f"per {BATCH_LITRES} L, +{a['added_nitrate_n_mg_l']:.1f} mg/L nitrate-N"
    )
    print(
        f"Nitrate-N: {a['nitrate_before_mg_l']:.1f} -> {a['nitrate_after_mg_l']:.1f} mg/L with the acid "
        f"(target {a['nitrate_target_mg_l']:.1f})"
    )
    print(
        'Supersaturated after acid:',
        ', '.join(f'{p} {s:.2f}' for p, s in a['supersaturated_after_acid']) or 'none',
    )
    for label, e in r['ec'].items():
        print(f"EC25 {label}: {e['ec25_ms_cm']:.2f} mS/cm at pH {e['ph']:.2f} (experimental)")
    print('\nConcentrate tanks (1:%d):' % r['injection_ratio'])
    for name, tank in r['tanks']['tanks'].items():
        print(f"  Tank {name}: " + ', '.join(p['name'] for p in tank['products']))
    print('\nStages on the same water:')
    for s in r['stages']:
        print(
            f"  {s['stage']:<50} {'met' if s['feasible'] else 'missed'}; worst {s['worst_miss_percent']:.1f}%"
        )


if __name__ == '__main__':
    main()
