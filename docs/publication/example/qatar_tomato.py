"""Worked example for the FlahaX publications: tomato on a published Qatar well.

Needs FlahaX with measured-pH water balancing (rafatahmed/Flahax PR 15, not
yet released). Rerun on the released version before publishing and paste
its output, unchanged, into the paper and the story.

Run from the repository root:  PYTHONPATH=src python docs/publication/example/qatar_tomato.py
"""
from flahax import VolumeLitres, balance_water_analysis, load_library, plan_fertilizer_workflow
from flahax.aqueous_model import nitric_target
from flahax.product_conversion import MOLAR_MASS

# Shomar et al. (2024), Groundwater, doi:10.1111/gwat.13411, supplementary Table S1,
# station 104: measured pH 7.80; mg/L; CO3-2 is inorganic carbon as C.
WELL_MG_L = {'Na+': 680, 'K+': 44.2, 'Ca+2': 244, 'Mg+2': 100.8, 'Cl-': 1280.4,
             'SO4-2': 723.3, 'NO3-': 15.38, 'CO3-2': 38.75}
GRAMS_PER_MOL = {'Na+': 22.98977, 'K+': 39.0983, 'Ca+2': 40.078, 'Mg+2': 24.305, 'Cl-': 35.45,
                 'SO4-2': 96.06, 'NO3-': 62.004, 'CO3-2': 12.011}
WELL_PH = 7.8
BLEND = .25          # 1 part well water to 3 parts desalinated water, taken as ion-free

# De Kreij, Voogt and Baas (1999), Brochure 196, Supplement 2, tomato, open system, p. 32.
MMOL = {'N_NO3': (16.0, 'N'), 'N_NH4': (1.2, 'N'), 'P': (1.5, 'P'), 'K': (9.5, 'K'),
        'Ca': (5.4, 'Ca'), 'Mg': (2.4, 'Mg'), 'S': (4.4, 'S')}
UMOL = {'Fe': 15, 'Mn': 10, 'Zn': 5, 'B': 30, 'Cu': .75, 'Mo': .5}
TARGET_PH = 5.5      # root-environment target in the same table

# Illustrative 60% w/w nitric acid at 1.37 kg/L. Use the actual product's assay.
NITRIC_FRACTION, NITRIC_DENSITY = .60, 1.37


def targets():
    macro = {k: v * MOLAR_MASS[e] for k, (v, e) in MMOL.items()}
    return macro | {k: v * MOLAR_MASS[k] / 1000 for k, v in UMOL.items()}


def ppm(totals):
    """mg/L of the water, for formulation, from mol/kg totals (1 kg water per litre)."""
    keys = {'Ca+2': 'Ca', 'Mg+2': 'Mg', 'K+': 'K', 'Na+': 'Na', 'SO4-2': 'S'}
    out = {k: totals[b] * MOLAR_MASS[k] * 1000 for b, k in keys.items()}
    out['N_NO3'] = totals['NO3-'] * MOLAR_MASS['N'] * 1000
    out['Cl'] = totals['Cl-'] * 35.45 * 1000
    return out


def workflow(water, salts, label):
    """Formulate on the laboratory analysis; speciate the charge-balanced record (#84)."""
    return plan_fertilizer_workflow(
        salts, targets(), ppm(water.analytical_totals), TARGET_PH, final_volume=VolumeLitres(1000),
        equilibrium=dict(water_balance=water, water_mass_kg=1000, water_analysis_id=label,
                         complete_analysis=True, carbon_boundary='closed', temperature_c=25, phases=[]))


def main():
    well = {ion: mg / GRAMS_PER_MOL[ion] / 1000 for ion, mg in WELL_MG_L.items()}
    balanced = balance_water_analysis(well, measured_ph=WELL_PH)
    print(f'Well: imbalance {balanced.imbalance_percent:.1f}% at pH {WELL_PH}; for the chemistry only it is closed by '
          f'{100 * balanced.balance_adjustment_molal / balanced.analysed_balance_ion_molal:+.1f}% Cl. '
          'Nutrients and limits use the laboratory values.')

    library = load_library()['salts']
    raw = workflow(balanced, library, 'station-104')
    lab = ppm(balanced.analytical_totals)
    print(f"1. Well water alone: best tomato recipe misses by {raw.recommendation['maxAbsDeltaPct']:.0f}% "
          f"(water Ca {lab['Ca']:.0f}, S {lab['S']:.0f} mg/L)")

    blend = balanced.diluted(BLEND)
    acid_p = workflow(blend, library, 'station-104-blend')
    chem = acid_p.stages['chemistry'].value
    print(f"2. Blend, best mass balance: within {acid_p.recommendation['maxAbsDeltaPct']:.2f}% of every target, "
          f"but the mix is pH {chem['mixed'].ph:.2f} (blend water pH {chem['water'].ph:.2f})")

    salts = [s for s in library if 'Phosphoric' not in s['name']]
    mkp = workflow(blend, salts, 'station-104-blend')
    mixed = mkp.stages['chemistry'].value['mixed']
    acid = nitric_target(mixed.totals, mixed.ph, TARGET_PH, phases=[])
    acid_n = acid.nitric_acid_molal * MOLAR_MASS['N'] * 1000
    millilitres = acid.nitric_acid_molal * 1000 * 63.01 / NITRIC_FRACTION / NITRIC_DENSITY
    rows = {r['symbol']: r for r in mkp.recommendation['rows']}
    no3 = rows['N_NO3']
    print(f"3. Blend with MKP instead: mix pH {mixed.ph:.2f}; {millilitres:.0f} mL of 60% nitric acid "
          f"per 1000 L reaches pH {TARGET_PH} and adds {acid_n:.1f} mg N/L")
    print(f"   nitrate {no3['final']:.1f} -> {no3['final'] + acid_n:.1f} mg/L (target {no3['target']:.1f}); "
          f"ionic strength {acid.target.ionic_strength:.3f} mol/kg")
    si = acid.target.saturation_indices
    print('   saturation indices: ' + ', '.join(f'{p} {si[p]:.2f}' for p in
                                             ('Calcite', 'Gypsum', 'CaHPO4:2H2O', 'Hydroxylapatite')))
    print(f"   from the water: Na {rows['Na']['final']:.0f} mg/L, Cl {rows['Cl']['final']:.0f} mg/L")
    for s in mkp.recommendation['salts']:
        print(f"     {s['name']}: {s['gramsPerLitre'] * 1000:.1f} g per 1000 L")


if __name__ == '__main__':
    main()
