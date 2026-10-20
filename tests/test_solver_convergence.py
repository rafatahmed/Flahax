"""#61: ionic-strength convergence and warm starts change the iteration path, not the state."""
import json
import unittest
from pathlib import Path

from flahax.aqueous_model import nitric_target, solve

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'phreeqc'


def fixture(name):
    return json.loads((FIXTURES / name / 'expected.json').read_text())


class WarmStartTests(unittest.TestCase):
    def assert_same_state(self, a, b, relative=1e-9):
        self.assertEqual(set(a.species), set(b.species))
        for name, amount in a.species.items():
            if amount > 1e-20:
                self.assertLess(abs(b.species[name] - amount), relative * amount, name)
        self.assertAlmostEqual(a.ionic_strength, b.ionic_strength, delta=1e-11)  # both stop at |dI| < 1e-12
        self.assertEqual({p for p, v in a.precipitated.items() if v > 0},
                         {p for p, v in b.precipitated.items() if v > 0})

    def test_warm_start_from_a_neighbouring_ph_reaches_the_cold_state(self):
        for name in ('products/mixed_products', 'phases/mixed_product_phases', 'phases/gypsum'):
            with self.subTest(name):
                data = fixture(name)
                ph = data['selected_rows'][-1]['pH']
                phases = data.get('phases', ())
                neighbour = solve(data['runtime_totals'], ph + .3, phases=phases)
                cold = solve(data['runtime_totals'], ph, phases=phases)
                warm = solve(data['runtime_totals'], ph, phases=phases, start=neighbour)
                self.assert_same_state(cold, warm)

    def test_warm_start_from_the_solution_takes_one_newton_step(self):
        data = fixture('products/mixed_products')
        ph = data['selected_rows'][-1]['pH']
        cold = solve(data['runtime_totals'], ph)
        warm = solve(data['runtime_totals'], ph, start=cold)
        self.assertLessEqual(warm.iterations, 2)
        self.assertLess(warm.iterations, cold.iterations)
        self.assertLessEqual(abs(warm.charge_balance - cold.charge_balance), 1e-15)

    def test_nitric_target_dose_is_unchanged(self):
        data = fixture('products/mixed_target_ph_nitric')
        plan = nitric_target(data['runtime_totals'], data['initial_ph'], data['selected_rows'][-1]['pH'])
        tolerance = data['tolerances']
        self.assertAlmostEqual(plan.nitric_acid_molal, data['nitric_acid_molal'],
                               delta=tolerance['acid_absolute'] + tolerance['acid_relative'] * data['nitric_acid_molal'])


class IonicStrengthConvergenceTests(unittest.TestCase):
    def test_strong_electrolyte_converges_in_few_newton_iterations(self):
        # Gypsum-saturated solution near I = 0.055: the averaged update needed ~47 outer
        # passes (102 Newton iterations); the secant step needs a fraction of that.
        data = fixture('phases/gypsum')
        result = solve(data['runtime_totals'], data['selected_rows'][-1]['pH'], phases=data['phases'])
        self.assertLess(result.iterations, 60)


if __name__ == '__main__':
    unittest.main()
