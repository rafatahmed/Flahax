import os
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_product_phreeqc


class LiveReferencePolicyTests(unittest.TestCase):
    def test_missing_reference_is_not_skippable_in_release_mode(self):
        case=test_product_phreeqc.LiveProductPhreeqcTests('test_replay_every_product_input')
        with patch('tests.test_product_phreeqc.INSTALL',Path(__file__).parent/'not-an-installation'):
            with patch.dict(os.environ,{'FLAHAX_REQUIRE_PHREEQC':'1'}):
                with self.assertRaises(AssertionError):
                    case.test_replay_every_product_input()
            with patch.dict(os.environ,{'FLAHAX_REQUIRE_PHREEQC':'0'}):
                with self.assertRaises(unittest.SkipTest):
                    case.test_replay_every_product_input()
