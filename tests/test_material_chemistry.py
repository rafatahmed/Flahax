"""A material is what it puts in the water (interactive mix Task 11, owner decision 2026-10-22).

Compounds are defined by their formula or ions, blends by their analysis; the catalogue's
records are pre-filled materials. Pinned values are the pre-Task-11 conversion of every
catalogue product at 1 g/kg water, in insertion order: the refactor must not move a bit.
"""
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow
from flahax.delivery_contracts import DeliveryError
from flahax.material_chemistry import ions_from_formula, material_chemistry
from flahax.materials import load_identities
from flahax.product_conversion import catalogue_dose_totals

PINNED_BASIS = {
    'Ammonium Dibasic Phosphate': [('NH4+', 0.01514775071929862), ('PO4-3', 0.007571246915373082)],
    'Ammonium Monobasic Phosphate': [('NH4+', 0.008695838420184626), ('PO4-3', 0.008692518525841323)],
    'Ammonium Nitrate': [('NO3-', 0.012493306774615003), ('NH4+', 0.012493306774615003)],
    'Ammonium Sulfate': [('NH4+', 0.015137755502723695), ('SO4-2', 0.007569245165315034)],
    'Boric Acid': [('H3BO3', 0.016172062904717854)],
    'CH - micro': [('Fe+3', 0.0012534694242994002), ('Zn+2', 6.11807892321811e-05), ('Mn+2', 0.00036404645203604263), ('Cu+2', 1.7310294904478647e-05), ('H3BO3', 0.0012025901942645698), ('MoO4-2', 5.211047420531527e-06), ('Na+', 0.002750261688618153), ('Edta-4', 0.0016960069604721026)],
    'Calcium Chloride (Dihydrate)': [('Ca+2', 0.0068023805066630685), ('Cl-', 0.013604761013326137)],
    'Calcium Nitrate (ag grade)': [('Ca+2', 0.00474075552672289), ('NO3-', 0.010280794191351283), ('NH4+', 0.0007853384451726674)],
    'Copper EDTA': [('Cu+2', 0.0022031284423881916), ('Na+', 0.004406256884776383), ('Edta-4', 0.0022031284423881916)],
    'Copper Sulfate (pentahydrate)': [('Cu+2', 0.004004972775627105), ('SO4-2', 0.004004990642545227)],
    'Iron DTPA': [('Fe+3', 0.0019697376667562), ('Na+', 0.0039394753335124), ('Dtp-5', 0.0019697376667562)],
    'Iron EDDHA': [('Fe+3', 0.0010744023636852001), ('Na+', 0.0010744023636852001), ('Edd-4', 0.0010744023636852001)],
    'Iron EDTA': [('Fe+3', 0.0023278717879846003), ('Na+', 0.0023278717879846003), ('Edta-4', 0.0023278717879846003)],
    'Iron II Sulfate (Hepahydrate)': [('Fe+2', 0.0035974572477392784), ('SO4-2', 0.0035963817841547095)],
    'Magnesium Sulfate (Heptahydrate)': [('Mg+2', 0.004056778440650072), ('SO4-2', 0.004058016219588271)],
    'Mg Nitrate': [('Mg+2', 0.003900148117671261), ('NO3-', 0.007800295572833)],
    'Mn EDTA': [('Mn+2', 0.0023663019382342775), ('Na+', 0.004732603876468555), ('Edta-4', 0.0023663019382342775)],
    'Phosphoric Acid (75%)': [('PO4-3', 0.007653585960917502)],
    'Potassium Bicarbonate': [('K+', 0.009988599013086462), ('CO3-2', 0.009988599013086462)],
    'Potassium Carbonate': [('K+', 0.014471298350416703), ('CO3-2', 0.0072356491752083515)],
    'Potassium Chloride': [('K+', 0.013414122119484949), ('Cl-', 0.01341412211948495)],
    'Potassium Citrate': [('K+', 0.00979093505344222), ('Citrate-3', 0.0032636450178140735)],
    'Potassium Dibasic Phosphate': [('K+', 0.011483107961215704), ('PO4-3', 0.005740665276629942)],
    'Potassium Hydroxide (45% solution)': [('K+', 0.008020655505003641)],
    'Potassium Monobasic Phosphate': [('K+', 0.007348657102738482), ('PO4-3', 0.007347509159526699)],
    'Potassium Nitrate': [('K+', 0.00989045559525606), ('NO3-', 0.009892408633011343)],
    'Potassium Sulfate': [('K+', 0.011476969586912985), ('SO4-2', 0.005739862757330006)],
    'Sodium Borate (Decahydrate) (borax)': [('Na+', 0.005245811734776456), ('H3BO3', 0.010490286771507863)],
    'Sodium Molybdate (Dihydrate)': [('Na+', 0.00826454585080868), ('MoO4-2', 0.0041323606044815)],
    'Urea': [('Ure', 0.016651316869783744)],
    'Zinc Sulfate (Monohydrate)': [('Zn+2', 0.005573569899051698), ('SO4-2', 0.005570804741110417)],
    'Zn EDTA': [('Zn+2', 0.002141327623126339), ('Na+', 0.004282655246252678), ('Edta-4', 0.002141327623126339)],
}
TODAY = {
    'Ammonium Dibasic Phosphate': ('macro_salt', ('NH4+', 'HPO4-2')),
    'Ammonium Monobasic Phosphate': ('macro_salt', ('NH4+', 'H2PO4-')),
    'Ammonium Nitrate': ('macro_salt', ('NH4+', 'NO3-')),
    'Ammonium Sulfate': ('macro_salt', ('NH4+', 'SO4-2')),
    'Boric Acid': ('boron', ('B(OH)3',)),
    'CH - micro': ('edta_borax_molybdate_blend', ('Fe(III)-EDTA', 'Mn-EDTA', 'Zn-EDTA', 'Cu-EDTA', 'borax', 'sodium molybdate')),
    'Calcium Chloride (Dihydrate)': ('macro_salt', ('Ca+2', 'Cl-')),
    'Calcium Nitrate (ag grade)': ('macro_salt', ('Ca+2', 'NO3-', 'NH4+')),
    'Copper EDTA': ('edta_chelate', ('Na+', 'Cu-EDTA')),
    'Copper Sulfate (pentahydrate)': ('free_metal_sulfate', ('Cu+2', 'SO4-2')),
    'Iron DTPA': ('dtpa_chelate', ('Na+', 'Fe(III)-DTPA')),
    'Iron EDDHA': ('eddha_chelate', ('Na+', 'Fe(III)-o,o-EDDHA')),
    'Iron EDTA': ('edta_chelate', ('Na+', 'Fe(III)-EDTA')),
    'Iron II Sulfate (Hepahydrate)': ('free_metal_sulfate', ('Fe+2', 'SO4-2')),
    'Magnesium Sulfate (Heptahydrate)': ('macro_salt', ('Mg+2', 'SO4-2')),
    'Mg Nitrate': ('macro_salt', ('Mg+2', 'NO3-')),
    'Mn EDTA': ('edta_chelate', ('Na+', 'Mn-EDTA')),
    'Phosphoric Acid (75%)': ('macro_acid', ('H3PO4',)),
    'Potassium Bicarbonate': ('macro_salt', ('K+', 'HCO3-')),
    'Potassium Carbonate': ('macro_salt', ('K+', 'CO3-2')),
    'Potassium Chloride': ('macro_salt', ('K+', 'Cl-')),
    'Potassium Citrate': ('citrate_salt', ('K+', 'citrate')),
    'Potassium Dibasic Phosphate': ('macro_salt', ('K+', 'HPO4-2')),
    'Potassium Hydroxide (45% solution)': ('strong_base', ('K+', 'OH-')),
    'Potassium Monobasic Phosphate': ('macro_salt', ('K+', 'H2PO4-')),
    'Potassium Nitrate': ('macro_salt', ('K+', 'NO3-')),
    'Potassium Sulfate': ('macro_salt', ('K+', 'SO4-2')),
    'Sodium Borate (Decahydrate) (borax)': ('boron', ('Na+', 'B(OH)4-', 'B(OH)3')),
    'Sodium Molybdate (Dihydrate)': ('molybdate', ('Na+', 'MoO4-2')),
    'Urea': ('neutral_urea', 'CO(NH2)2'),  # a bare string before Task 11 (missing comma)
    'Zinc Sulfate (Monohydrate)': ('free_metal_sulfate', ('Zn+2', 'SO4-2')),
    'Zn EDTA': ('edta_chelate', ('Na+', 'Zn-EDTA')),
}


LIBRARY = load_library()
CATALOGUE = {s['name']: s for s in LIBRARY['salts']}
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']
NITRIC = dict(id='HNO3-example', source='EXAMPLE GRADE', revision='1', recordedAt='2026-10-22T00:00:00Z',
              chemicalFormula='HNO3', massFraction=.60, densityKgPerL=1.37)
RO = dict(water_totals={}, water_mass_kg=1000, water_analysis_id='RO', complete_analysis=True,
          carbon_boundary='closed', temperature_c=25, phases=[])
UNDEFINED = 'give its formula, its ions, or its analysis by nutrient form'


def user_list():
    """The catalogue re-entered by a developer: no catalogue names, ids or identity links.

    The four of the brief are defined as a grower would: two by formula, calcium nitrate by its
    commercial double-salt formula with its label, the iron chelate by ions and its chelating
    agent. The rest carry their ions. Elements (the label) are the catalogue's.
    """
    own = {'Potassium Monobasic Phosphate': ('My MKP', {'formula': 'KH2PO4'}),
           'Potassium Nitrate': ('My potassium nitrate', {'formula': 'KNO3'}),
           'Calcium Nitrate (ag grade)': ('My calcium nitrate', {'formula': '5Ca(NO3)2·NH4NO3·10H2O'}),
           'Iron EDTA': ('My Fe chelate', {'formula': None, 'ions': {'Na+': 1, 'Fe+3': 1}, 'chelating_agent': 'EDTA'})}
    records, names = [], {}
    for salt in LIBRARY['salts']:
        name, definition = own.get(salt['name'], (f"User {salt['name'].lower()}",
                                                  {'ions': dict(load_identities()[salt['identityId']]['ion_forms'])}))
        record = {k: v for k, v in salt.items() if k not in ('identityId', 'analysisBasis', 'source', 'displayName')}
        record.update(definition, id=f'user-{len(records)}', name=name)
        records.append(record)
        names[name] = salt['name']
    return records, names


def workflow(salts):
    return plan_fertilizer_workflow(salts, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000), equilibrium=RO,
                                    ph_adjustment=dict(products=[NITRIC], maximum_reagent_volume_litres=5))


class MaterialChemistryTests(unittest.TestCase):
    def test_every_catalogue_product_keeps_its_family_and_components(self):
        for name, (family, components) in TODAY.items():
            chemistry = material_chemistry(CATALOGUE[name])
            self.assertEqual(chemistry.family, family, name)
            if name == 'Urea':
                self.assertEqual(chemistry.components, ('CO(NH2)2',))
            elif name == 'Calcium Nitrate (ag grade)':
                # Same ions; the order is now the identity's ion_forms (data), not a hand-typed tuple.
                self.assertEqual(sorted(chemistry.components), sorted(components))
            else:
                self.assertEqual(chemistry.components, components, name)
        self.assertEqual(set(TODAY), set(CATALOGUE))

    def test_every_catalogue_product_converts_bit_for_bit(self):
        for name, expected in PINNED_BASIS.items():
            self.assertEqual(list(catalogue_dose_totals({name: 1.0}).items()), expected, name)

    def test_identity_formulas_parse_to_their_ion_forms(self):
        for identity in load_identities().values():
            if identity['formula']:
                self.assertEqual(ions_from_formula(identity['formula']), identity['ion_forms'], identity['id'])

    def test_a_name_alone_is_not_a_material(self):
        for record in ({'name': 'Mystery'}, {'name': 'Mystery', 'formula': 'Ch micro', 'elements': {'Fe': 7}}):
            with self.assertRaises(DeliveryError) as caught:
                material_chemistry(record)
            self.assertEqual(caught.exception.code, 'material_undefined')
            self.assertIn(UNDEFINED, str(caught.exception))
            if 'formula' in record:      # a trade name typed where the formula belongs
                self.assertIn("'Ch micro' is a name, not a chemical formula", str(caught.exception))

    def test_counterions_follow_the_ions_not_the_name(self):
        products = {'My potash': {'name': 'My potash', 'formula': 'K2CO3', 'elements': {'K': 56.58}},
                    'My bicarb': {'name': 'My bicarb', 'formula': 'KHCO3', 'elements': {'K': 39.05}},
                    'My ferrous': {'name': 'My ferrous', 'formula': 'FeSO4·7H2O', 'elements': {'Fe': 20.09}}}
        totals = catalogue_dose_totals({'My potash': 1.0}, products=products)
        self.assertEqual(totals['CO3-2'], totals['K+'] / 2)
        totals = catalogue_dose_totals({'My bicarb': 1.0}, products=products)
        self.assertEqual(totals['CO3-2'], totals['K+'])
        totals = catalogue_dose_totals({'My ferrous': 1.0}, products=products)
        self.assertEqual(set(totals), {'Fe+2', 'SO4-2'})
        self.assertEqual(totals['SO4-2'], totals['Fe+2'])

    def test_a_label_that_contradicts_its_ions_is_refused(self):
        with self.assertRaises(DeliveryError) as caught:
            material_chemistry({'name': 'Odd nitrate', 'formula': 'KNO3', 'elements': {'K': 38.67, 'N_NO3': 20}})
        self.assertEqual(caught.exception.code, 'identity_inconsistent')
        with self.assertRaises(DeliveryError) as caught:
            material_chemistry({'name': 'Odd salt', 'ions': {'K+': 2, 'NO3-': 1}, 'elements': {'K': 10}})
        self.assertEqual(caught.exception.code, 'invalid_composition')

    def test_user_materials_without_catalogue_names_give_the_catalogue_result(self):
        records, names = user_list()
        self.assertFalse({r['name'] for r in records} & set(CATALOGUE))
        mine, shipped = workflow(records), workflow(LIBRARY['salts'])
        for result in (mine, shipped):
            self.assertIn(result.stages['chemistry'].status, ('calculated', 'requires_review'))

        def salts(result):
            return sorted((names.get(s['name'], s['name']), s['gramsPerLitre']) for s in result.recommendation['salts'])
        self.assertEqual(salts(mine), salts(shipped))
        self.assertAlmostEqual(mine.stages['chemistry'].value['mixed'].ph,
                               shipped.stages['chemistry'].value['mixed'].ph, delta=1e-9)
        a, b = mine.stages['ph_adjustment'].value.selected, shipped.stages['ph_adjustment'].value.selected
        self.assertEqual((a.status, a.product_id), (b.status, b.product_id))
        self.assertAlmostEqual(a.dose_molal, b.dose_molal, delta=1e-9 * b.dose_molal)
        self.assertAlmostEqual(a.target.ph, b.target.ph, delta=1e-9)

    def test_a_name_only_material_stops_chemistry_with_what_to_give(self):
        records, _ = user_list()
        mkp = next(r for r in records if r['name'] == 'My MKP')
        del mkp['formula']
        stage = workflow(records).stages['chemistry']
        self.assertEqual(stage.error_code, 'material_undefined')
        self.assertIn(f'My MKP: {UNDEFINED}', stage.message)


if __name__ == '__main__':
    unittest.main()
