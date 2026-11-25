# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The catalogue is indexed once, the sensitivity matrix stays sparse, no point is solved twice.

Three causes made the unit tests take over an hour: the packaged catalogue was re-parsed on
every product lookup (about 12,000 times in one batch), the pH sensitivity matrix was built
densely from exact fractions although almost every term is zero, and the joint search solved
the same cold equilibrium again whenever it revisited a point. These tests keep all three
fixed without timing anything: they count catalogue loads and equilibrium solves, and pin
gradient values computed by the dense implementation.
"""

import unittest
from unittest.mock import patch

from flahax import engine, load_library, make_joint_problem, product_conversion, recommend
from flahax import joint_problem, joint_solver
from flahax.delivery_contracts import DeliveryError
from flahax.joint_sensitivity import equilibrium_charge_gradient
from flahax.materials import _shipped_salt
from flahax.ph_adjustment import nutrient_salts
from tests import test_joint_problem_contract as contract
from tests.test_joint_fit import controls


def counting_loader():
    """A substitute for ``engine.load_library`` that counts its calls."""
    calls = []
    original = engine.load_library

    def load():
        calls.append(1)
        return original()

    return load, calls


class CatalogueIndexTests(unittest.TestCase):
    def test_repeated_lookups_load_the_catalogue_once(self):
        loader, calls = counting_loader()
        with patch.object(engine, 'load_library', loader):
            for _ in range(5):
                engine.catalogue_salts_by_name()
                _shipped_salt('Potassium Nitrate')
                product_conversion.catalogue_dose_contributions({'Potassium Nitrate': 1.0})
        self.assertEqual(len(calls), 1)

    def test_a_substituted_catalogue_gets_its_own_index(self):
        # tests.catalogue_history replaces load_library; the index must follow the loader.
        salts = load_library()['salts']
        first = [dict(salts[0], name='Alpha')]
        second = [dict(salts[0], name='Beta')]
        with patch.object(engine, 'load_library', lambda: {'salts': first}):
            self.assertEqual(list(engine.catalogue_salts_by_name()), ['Alpha'])
        with patch.object(engine, 'load_library', lambda: {'salts': second}):
            self.assertEqual(list(engine.catalogue_salts_by_name()), ['Beta'])

    def test_index_returns_the_record_a_linear_scan_finds(self):
        index = engine.catalogue_salts_by_name()
        shipped = load_library()['salts']
        self.assertEqual(len(index), len({s['name'] for s in shipped}))
        for salt in shipped:
            with self.subTest(name=salt['name']):
                self.assertEqual(_shipped_salt(salt['name']), salt)

    def test_unknown_and_unhashable_names_are_unknown_products(self):
        for name in ('No such product', ['Potassium Nitrate'], None):
            with self.subTest(name=name), self.assertRaises(DeliveryError) as caught:
                _shipped_salt(name)
            self.assertEqual(caught.exception.code, 'unknown_product')


def lettuce_problem():
    library = load_library()
    pool = nutrient_salts(library['salts'])
    targets = next(
        f['targets'] for f in library['formulas'] if f['name'] == 'Lettuce 2 (Howard Resh)'
    )
    problem = make_joint_problem(
        pool,
        dict(
            id='r',
            chemicalFormula='HNO3',
            massFraction=0.5,
            densityKgPerL=1.2,
            source='synthetic test grade',
            revision='1',
            recordedAt='2026-10-26',
        ),
        targets,
        {},
        reagent_solvent_fraction=0.5,
        water_components={},
        final_volume_litres=1000,
        solvent_mass_kg=1000,
        target_ph=5.8,
        reference_charge_mol_per_kg=0,
        maximum_reagent_mass_g=6000,
        maximum_reagent_volume_litres=5,
    )
    doses = {s['id']: s['gramsPerLitre'] for s in recommend(pool, targets, {})['salts']}
    return problem, doses


# Gradients d(charge)/d(product g/L) from the dense matrix construction, before the sparse
# accumulation replaced it. The exact rational solve is unchanged; the tolerance only absorbs
# platform differences in the floating-point state the problem is evaluated at.
CONTRACT_SALT = [0.0031971163783613005, -0.017848341822687196]
LETTUCE_CHELATE = [
    5.690979273308167e-12,
    -3.398845640583962e-06,
    1.0979806833216411e-05,
    -3.4143537539159914e-05,
    -2.8290336514833887e-05,
    -3.497791061899184e-05,
    -0.0008313985059355646,
    -0.0007111489210233469,
    -2.4520746781408083e-06,
    8.414722592916042e-06,
    -0.00010856339434640908,
    -0.00012988523047273678,
    -9.930057198392687e-05,
    -7.816380286192164e-07,
    1.9194136365945334e-06,
    0.0038652250563868955,
    0.003945935781238419,
    -3.805880767735523e-05,
    6.545010594127934e-05,
    5.213258895146923e-06,
    8.460200898906349e-06,
    0.00523741140709291,
    -8.008847598297533e-06,
    7.816368378307078e-05,
    -0.007934451097671696,
]


class SparseSensitivityTests(unittest.TestCase):
    def assert_gradient(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for index, (a, e) in enumerate(zip(actual, expected)):
            with self.subTest(source=index):
                self.assertAlmostEqual(a, e, delta=abs(e) * 1e-12 + 1e-300)

    def test_small_problem_keeps_its_dense_gradient(self):
        problem = contract.JointContractTests().problem()
        state = problem.evaluate({'salt': 0.3}, 0.05)
        self.assert_gradient(equilibrium_charge_gradient(problem, state), CONTRACT_SALT)

    def test_full_catalogue_chelate_problem_keeps_its_dense_gradient(self):
        problem, doses = lettuce_problem()
        state = problem.evaluate(doses, 0.01)
        self.assert_gradient(equilibrium_charge_gradient(problem, state), LETTUCE_CHELATE)


class RepeatedPointTests(unittest.TestCase):
    """The contract problem stalls with its default controls, so its search revisits points."""

    def search(self, limit):
        """Run the search; return its result and every (doses, reagent) solved from cold."""
        problem = contract.JointContractTests().problem()
        original = joint_problem.JointProblem.evaluate
        cold = []

        def record(self, doses, reagent, *, equilibrium_start=None):
            if equilibrium_start is None:
                cold.append((tuple(sorted(dict(doses).items())), reagent))
            return original(self, doses, reagent, equilibrium_start=equilibrium_start)

        with (
            patch.object(joint_problem.JointProblem, 'evaluate', record),
            patch.object(joint_solver, '_OUTCOME_LIMIT', limit),
        ):
            result = joint_solver.solve_joint_problem(
                problem, {'salt': 0.3}, 0.05, **controls(problem)
            )
        return result, cold

    def test_only_the_final_fresh_recheck_solves_a_cold_point_again(self):
        _, cold = self.search(8192)
        self.assertTrue(cold)
        # finish() re-solves its candidate on purpose (cold=True is never answered from memory).
        self.assertLessEqual(len(cold) - len(set(cold)), 1)

    def test_remembering_points_does_not_change_the_search(self):
        remembered, kept = self.search(8192)
        repeated, unkept = self.search(0)
        # The guard has teeth: without it the same search solves many points again.
        self.assertGreater(len(unkept), 2 * len(set(unkept)))
        self.assertGreater(len(unkept), len(kept))
        self.assertEqual(remembered['reason'], repeated['reason'])
        for field in ('fertilizerDoses', 'reagentDose', 'diagnostics', 'stationarity'):
            with self.subTest(field=field):
                self.assertEqual(repr(remembered[field]), repr(repeated[field]))


if __name__ == '__main__':
    unittest.main()
