"""Source-qualified allocation REVIEW, not an executable StockPlan.

Yara 04_Fertilizer.pdf pp.63,65,66 supports macro separation patterns, not
complete compatibility/solubility approval for these generic product grades.
"""


def review(recommendation, final_volume_litres):
    routes = {
        'Calcium Nitrate (ag grade)': ('A', 'Calcium side; exclude sulfate and phosphate concentrates.'),
        'Mg Nitrate': ('A', 'Magnesium NITRATE, analogous to KRISTA-MAG; not magnesium sulfate. Grade confirmation needed.'),
        'Potassium Nitrate': ('A', 'Chosen on the nitrate side for this draft; page 65 also permits the B-side macro products.'),
        'Mn EDTA': ('A', 'Page 66 places chelates on the A side; exact Mn-EDTA co-storage/solubility still needs confirmation. Do not acidify this tank.'),
        'Potassium Sulfate': ('B', 'Sulfate side, analogous to KRISTA-SOP; keep separate from calcium.'),
        'Potassium Monobasic Phosphate': ('B', 'Phosphate side, analogous to KRISTA-MKP; keep separate from calcium and magnesium nitrate per page 65.'),
        'Phosphoric Acid (75%)': ('Acid', 'Proposed dedicated acid channel for independent control. Page 66 allows an acid-containing B concept, but this does not approve every grade/mixture.'),
        'Iron II Sulfate (Hepahydrate)': ('Unassigned', 'Not iron chelate. Calcium/sulfate separation applies; trace-sulfate/phosphate co-storage is not established by page 65.'),
        'Copper Sulfate (pentahydrate)': ('Unassigned', 'Keep away from calcium concentrate; compatibility with the phosphate-bearing B mixture is not established here.'),
        'Zinc Sulfate (Monohydrate)': ('Unassigned', 'Keep away from calcium concentrate; compatibility with the phosphate-bearing B mixture is not established here.'),
        'Boric Acid': ('Unassigned', 'Not listed in page 65; trace-nutrient product, not the dedicated pH-control acid reagent.'),
        'Sodium Molybdate (Dihydrate)': ('Unassigned', 'Not listed in page 65; no automatic assignment based only on elemental Mo.'),
    }
    rows = []
    for salt in recommendation['salts']:
        group, reason = routes.get(salt['name'], ('Unassigned', 'No reviewed source mapping for this product.'))
        rows.append(dict(product_id=salt['id'], product=salt['name'], proposed_channel=group,
            status='unresolved' if group == 'Unassigned' else 'candidate_only',
            final_dose_g_per_litre=salt['gramsPerLitre'],
            recipe_mass_g=salt['gramsPerLitre'] * final_volume_litres,
            stock_concentration_g_per_litre=None, reason=reason))
    return dict(status='not_ready_for_mixing', source='04_Fertilizer.pdf, pages 63, 65 and 66',
        source_sha256='3ba275fa3e3a7011e5a3f93f046e2c84a2656656b772b656778dc66e5110242e',
        final_volume_litres=final_volume_litres, rows=rows,
        acid_policy='Dedicated acid channel is a proposed design choice, not a requirement stated by the PDF.',
        acid_accounting='Phosphoric acid shown here is already in the nutrient recipe. Do not add that mass again as a pH dose. Additional nitric/phosphoric demand is not yet calculated for the pepper water.',
        missing=['Complete trace-product co-storage evidence; a separate trace stock may be needed.',
                 'Actual tank capacities, prepared volumes, injection ratios and temperature.',
                 'Grade- and mixture-qualified solubility limits, including page 65 starred restrictions.',
                 'Complete source-water chemistry and acid assay/density for pH demand and reagent volume.'])
