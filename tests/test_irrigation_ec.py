import hashlib
import json
from importlib.resources import files
from pathlib import Path
import unittest

from flahax.aqueous_model import chemistry
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (COEFFICIENTS_SHA256, covered_species,
                                  ionic_molal_conductivity,
                                  load_conductivity_coefficients)

FIXTURES = Path(__file__).parent / 'fixtures' / 'conductivity'


class CoefficientTests(unittest.TestCase):
    def test_shipped_table_matches_independent_transcription(self):
        shipped = load_conductivity_coefficients()['ions']
        fixture = json.loads((FIXTURES / 'mccleskey2012_table1_independent.json').read_text())['ions']
        self.assertEqual(set(shipped), set(fixture))
        self.assertEqual(len(shipped), 28)
        for ion in shipped:
            self.assertEqual(shipped[ion], fixture[ion], ion)

    def test_species_map_targets_exist_and_cover_flahax_species(self):
        data = load_conductivity_coefficients()
        names = {r['name'] for r in chemistry()['aqueous']}
        self.assertEqual(len(data['species_map']), 21)
        self.assertEqual(covered_species(), frozenset(data['species_map']))
        for species, ion in data['species_map'].items():
            self.assertIn(species, names); self.assertIn(ion, data['ions'])

    def test_eq8_at_25c_by_hand(self):
        # K+: l0 = 0.003046*625 + 1.261*25 + 40.70 = 74.12875; A = 49.22375; B = 1.5
        self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.0), 74.12875, places=9)
        self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.01), 74.12875 - 49.22375*0.1/1.15, places=9)
        # Cl-: l0 = 76.800625; A = 49.51375
        self.assertAlmostEqual(ionic_molal_conductivity('Cl-', 0.01), 76.800625 - 49.51375*0.1/1.15, places=9)

    def test_coefficient_file_is_pinned(self):
        raw = files('flahax').joinpath('data/conductivity_mccleskey2012.json').read_bytes()
        self.assertEqual(COEFFICIENTS_SHA256, hashlib.sha256(raw).hexdigest())

    def test_lambda_rejects_unknown_ion_and_bad_strength(self):
        for args in (('Li2+', .01), ('K+', -1.), ('K+', float('nan'))):
            with self.subTest(args=args), self.assertRaises(DeliveryError):
                ionic_molal_conductivity(*args)


if __name__ == '__main__':
    unittest.main()
