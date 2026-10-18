import json
from pathlib import Path
import unittest

from flahax.delivery_contracts import DeliveryError
from flahax.engine import load_library
from flahax.materials import (IDENTITIES_SHA256, IDENTITY_STATUSES, identity_for_product,
                              load_identities)

FIXTURES = Path(__file__).parent / 'fixtures' / 'materials'

# Charge per dissolved component as declared in ion_forms. Neutral solutes are 0.
CHARGES = {
    'Na+': 1, 'K+': 1, 'NH4+': 1,
    'Ca+2': 2, 'Mg+2': 2, 'Fe+2': 2, 'Cu+2': 2, 'Zn+2': 2,
    'NO3-': -1, 'SO4-2': -2, 'H2PO4-': -1, 'HPO4-2': -2, 'CO3-2': -2,
    'MoO4-2': -2, 'B(OH)4-': -1, 'citrate': -3,
    'Fe(III)-EDTA': -1, 'Mn-EDTA': -2, 'Zn-EDTA': -2, 'Cu-EDTA': -2,
    'Fe(III)-DTPA': -2, 'Fe(III)-o,o-EDDHA': -1,
    'H3PO4': 0, 'B(OH)3': 0, 'CO(NH2)2': 0,
}

REQUIRED_KEYS = {'id', 'products', 'name', 'formula', 'hydration', 'molecular_weight', 'cas',
                 'ion_forms', 'theoretical_analysis', 'comparator', 'status', 'notes'}


class IdentityTests(unittest.TestCase):
    def test_every_catalogue_product_has_exactly_one_identity(self):
        names = [s['name'] for s in load_library()['salts']]
        covered = [p for i in load_identities().values() for p in i['products']]
        self.assertEqual(sorted(names), sorted(covered))

    def test_theoretical_analysis_matches_independent_audit_values(self):
        audit = json.loads((FIXTURES / 'audit_theory.json').read_text(encoding='utf-8'))
        compared = 0
        for name, ref in audit.items():
            ident = identity_for_product(name)
            if ident['formula'] == ref['formula']:
                compared += 1
                self.assertEqual(set(ident['theoretical_analysis']), set(ref['analysis']), name)
                for key, value in ref['analysis'].items():
                    self.assertAlmostEqual(ident['theoretical_analysis'][key], value, places=6,
                                           msg=(name, key))
        # Potassium Citrate is the only fixture row whose formula (monohydrate
        # comparator) differs from the shipped anhydrous identity.
        self.assertEqual(compared, len(audit) - 1)

    def test_calcium_nitrate_is_the_double_salt_and_exercised(self):
        ident = identity_for_product('Calcium Nitrate (ag grade)')
        self.assertEqual(ident['formula'], '5Ca(NO3)2.NH4NO3.10H2O')
        self.assertEqual(ident['status'], 'commercial_double_salt')

    def test_mg_nitrate_identity_is_hexahydrate(self):
        ident = identity_for_product('Mg Nitrate')
        self.assertEqual(ident['formula'], 'Mg(NO3)2.6H2O')
        self.assertAlmostEqual(ident['theoretical_analysis']['N_NO3'], 10.92564, places=4)
        self.assertAlmostEqual(ident['theoretical_analysis']['Mg'], 9.47931, places=4)

    def test_ion_forms_are_charge_neutral(self):
        for ident in load_identities().values():
            if ident['status'] == 'assumed_blend':
                continue
            self.assertEqual(sum(CHARGES[c] * n for c, n in ident['ion_forms'].items()), 0, ident['id'])

    def test_records_have_required_keys_and_known_status(self):
        for key, ident in load_identities().items():
            self.assertEqual(key, ident['id'])
            self.assertTrue(key.startswith('idn-'), key)
            self.assertTrue(REQUIRED_KEYS <= set(ident), (key, REQUIRED_KEYS - set(ident)))
            self.assertIn(ident['status'], IDENTITY_STATUSES, key)
            self.assertEqual(set(ident['comparator']), {'product', 'url', 'accessed'}, key)

    def test_chelates_are_defined_sodium_salts(self):
        expected = {
            'Iron EDTA': ('C10H12FeN2NaO8', {'Na+': 1, 'Fe(III)-EDTA': 1}),
            'Mn EDTA': ('C10H12MnN2Na2O8', {'Na+': 2, 'Mn-EDTA': 1}),
            'Zn EDTA': ('C10H12N2Na2O8Zn', {'Na+': 2, 'Zn-EDTA': 1}),
            'Copper EDTA': ('C10H12CuN2Na2O8', {'Na+': 2, 'Cu-EDTA': 1}),
            'Iron DTPA': ('C14H18FeN3Na2O10', {'Na+': 2, 'Fe(III)-DTPA': 1}),
            'Iron EDDHA': ('C18H16FeN2NaO6', {'Na+': 1, 'Fe(III)-o,o-EDDHA': 1}),
        }
        for name, (formula, ions) in expected.items():
            ident = identity_for_product(name)
            self.assertEqual(ident['status'], 'chelate_salt_defined', name)
            self.assertEqual(ident['formula'], formula, name)
            self.assertEqual(ident['ion_forms'], ions, name)
        self.assertAlmostEqual(identity_for_product('Iron EDTA')['theoretical_analysis']['Fe'],
                               15.2148, places=3)

    def test_special_statuses(self):
        self.assertEqual(identity_for_product('Phosphoric Acid (75%)')['status'], 'aqueous_solution')
        self.assertEqual(identity_for_product('Phosphoric Acid (75%)')['formula'], 'H3PO4')
        blend = identity_for_product('CH - micro')
        self.assertEqual(blend['status'], 'assumed_blend')
        for component in ('Fe(III)-EDTA', 'Mn-EDTA', 'Zn-EDTA', 'Cu-EDTA', 'B(OH)4-', 'MoO4-2'):
            self.assertIn(component, blend['ion_forms'])
        self.assertEqual(identity_for_product('Potassium Citrate')['formula'], 'C6H5K3O7')
        self.assertEqual(identity_for_product('Sodium Borate (Decahydrate) (borax)')['ion_forms'],
                         {'Na+': 2, 'B(OH)4-': 2, 'B(OH)3': 2})
        self.assertAlmostEqual(identity_for_product('Urea')['theoretical_analysis']['N_UREA'],
                               46.64642736062887, places=9)

    def test_unknown_product_fails_closed(self):
        with self.assertRaises(DeliveryError) as caught:
            identity_for_product('Unobtainium Nitrate')
        self.assertEqual(caught.exception.code, 'unknown_product')

    def test_identities_file_is_pinned(self):
        self.assertEqual(IDENTITIES_SHA256, '7713f20cc7e8eb83ea4fa9e90bf36b875c81599c2965f9ddf96818e4c372c891')


if __name__ == '__main__':
    unittest.main()
