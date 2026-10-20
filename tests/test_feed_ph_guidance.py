"""Feed-pH guidance and residual bicarbonate reporting (research report 2026-10-20)."""
import unittest

from flahax import load_library, plan_fertilizer_workflow
from flahax.fertilizer_workflow import ACCEPTABLE_FEED_PH, RECOMMENDED_FEED_PH

LIBRARY = load_library()
TARGETS = next(f for f in LIBRARY["formulas"] if f["name"] == "Hoagland solution")["targets"]


def notes(target_ph):
    return plan_fertilizer_workflow(LIBRARY["salts"], TARGETS, {}, target_ph).recommendation["warnings"]


class FeedPhGuidanceTests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(RECOMMENDED_FEED_PH, (5.3, 5.8))
        self.assertEqual(ACCEPTABLE_FEED_PH, (5.0, 7.0))

    def test_recommended_ph_adds_no_note(self):
        self.assertFalse(any("Target pH" in w for w in notes(5.5)))

    def test_outside_recommended_band_is_noted(self):
        self.assertTrue(any("feed range of Dutch soilless practice" in w for w in notes(6.5)))

    def test_outside_acceptable_band_is_noted(self):
        self.assertTrue(any("acceptable for most soilless crops" in w for w in notes(7.5)))


if __name__ == "__main__":
    unittest.main()
