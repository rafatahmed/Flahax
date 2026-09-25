import unittest
from flahax.phase_allocation import phase_allocation
class PhaseAllocationTests(unittest.TestCase):
 def test_phreeqc_calcite_allocation_probe(self):
  r=phase_allocation("Calcite",.1,.10003)
  self.assertAlmostEqual(r.dissolved_moles,0); self.assertAlmostEqual(r.precipitated_moles,.00003)
