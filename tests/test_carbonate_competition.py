import unittest
from flahax.competition import carbonate_competition
class CarbonateCompetitionTests(unittest.TestCase):
 def test_phreeqc_carbonate_competition_probe(self):
  r=carbonate_competition(5.044e-4,1.274e-5,5.697e-4,4.598e-4,7.616e-4,5.262e-8)
  self.assertAlmostEqual(r.calcite_si,.26,places=2); self.assertAlmostEqual(r.gypsum_si,-1.99,places=1); self.assertAlmostEqual(r.struvite_si,-.48,places=1)
