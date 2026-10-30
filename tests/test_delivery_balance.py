# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent dilution identities and adversarial delivery boundaries."""

from dataclasses import replace
from fractions import Fraction
import unittest

from flahax import DeliveryError, VolumeLitres
from flahax.delivery_quantities import GramsPerLitre, MassGrams, InjectionRatio
from flahax.delivery_plan import compose_delivery_plan, transition_plan
from tests.test_delivery_plan import DeliveryPlanTests
from tests.test_ph_planning import inputs
from flahax.ph_planning import plan_ph
from tests.catalogue_history import historical_catalogue


class DeliveryBalanceTests(unittest.TestCase):
    def setUp(self):
        self.plan = DeliveryPlanTests().make_plan()

    def compose(self, **changes):
        p = replace(self.plan, **changes)
        return compose_delivery_plan(p.recipe, p.stocks, p.ph_plan, p.commands, p.audit_record)

    def test_exact_rational_mass_identity(self):
        # 1/10 g/L * 10 L = 1 g; 10 g/L * 1/10 L = 1 g.
        expected = Fraction(1, 10) * 10
        tank = self.plan.stocks.tanks[0]
        self.assertEqual(self.plan.recipe.salts[0].mass.value, float(expected))
        self.assertEqual(
            tank.salts[0].concentration.value * tank.stock_volume.value, float(expected)
        )
        self.assertEqual(self.plan.commands[0].requested_volume.value, float(Fraction(10, 100)))

    def test_trace_product_cannot_disappear_or_double(self):
        from flahax.delivery_quantities import final_solution_recipe
        from flahax.stock_planning import plan_stocks
        from tests.test_stock_assignments import synthetic_model
        from tests.test_ph_planning import record

        original = self.plan
        for dose in (1e-15, 1e-10, 0.1, 1.0):
            recipe = final_solution_recipe(
                {'feasible': True, 'salts': [{'id': 'a', 'name': 'A', 'gramsPerLitre': dose}]},
                VolumeLitres(10),
            )
            stocks = plan_stocks(
                recipe,
                original.stocks.injection_ratio,
                [original.stocks.tanks[0].tank],
                [],
                [
                    record(
                        'limit',
                        productId='a',
                        maxGramsPerLitre=200,
                        temperatureMinC=0,
                        temperatureMaxC=30,
                    )
                ],
                original.stocks.temperature,
                mixture_model=synthetic_model,
            )
            compose_delivery_plan(recipe, stocks, None, original.commands, original.audit_record)
            tank = stocks.tanks[0]
            for factor in (0, 2):
                bad = replace(
                    tank,
                    salts=(
                        replace(
                            tank.salts[0],
                            concentration=GramsPerLitre(
                                tank.salts[0].concentration.value * factor
                            ),
                        ),
                    ),
                )
                with self.subTest(dose=dose, factor=factor), self.assertRaises(DeliveryError):
                    compose_delivery_plan(
                        recipe,
                        replace(stocks, tanks=(bad,)),
                        None,
                        original.commands,
                        original.audit_record,
                    )

    def test_two_stocks_and_reagent_reach_one_final_batch(self):
        from flahax import StockTank, TemperatureCelsius
        from flahax.delivery_quantities import final_solution_recipe
        from flahax.stock_planning import plan_stocks
        from flahax.injector_sizing import size_injection_requirements
        from flahax.pump_planning import plan_pump_command
        from tests.test_stock_assignments import synthetic_model
        from tests.test_ph_planning import record
        from tests.test_pump_planning import calibration, CALIBRATION_AS_OF

        recipe = final_solution_recipe(
            {
                'feasible': True,
                'salts': [
                    {'id': k, 'name': k, 'gramsPerLitre': dose}
                    for k, dose in [('a', 0.1), ('b', 0.2)]
                ],
            },
            VolumeLitres(120),
        )
        stocks = plan_stocks(
            recipe,
            InjectionRatio(100),
            [StockTank(k, VolumeLitres(2)) for k in ('A', 'B')],
            [
                record(
                    'separate',
                    productIds=['a', 'b'],
                    constraint='separate',
                    reason='synthetic',
                    temperatureMinC=10,
                    temperatureMaxC=30,
                )
            ],
            [
                record(k, productId=k, maxGramsPerLitre=50, temperatureMinC=10, temperatureMaxC=30)
                for k in ('a', 'b')
            ],
            TemperatureCelsius(20),
            mixture_model=synthetic_model,
        )
        water, curve, reagent = inputs()
        # Curve endpoint: exactly 1.2 meq/L / 10000 meq/L reagent at 120 L.
        ph = plan_ph(
            water,
            curve,
            reagent,
            6.0,
            recipe.final_volume,
            VolumeLitres(1),
            {'N_NO3': 100},
            {'N_NO3': 123.184},
        )
        acid = Fraction(12, 10) * 120 / 10000
        self.assertEqual(ph.reagent_volume_litres, float(acid))
        channels = {
            t.tank.tank_id: dict(
                final_litres_per_stock_litre=100, available_stock_litres=t.stock_volume.value
            )
            for t in stocks.tanks
        }
        channels['acid'] = dict(
            final_litres_per_stock_litre=float(Fraction(120) / acid), available_stock_litres=1
        )
        sizing = size_injection_requirements(
            duration_hours=2,
            channels=channels,
            equipment_type='dosing_pump',
            final_volume_litres=120,
        )
        commands = [
            plan_pump_command(
                calibration() | {'channelId': k, 'validMinLitres': 0},
                VolumeLitres(v['required_stock_litres']),
                VolumeLitres(2),
                as_of=CALIBRATION_AS_OF,
            )
            for k, v in sizing['channels'].items()
        ]
        plan = compose_delivery_plan(recipe, stocks, ph, commands, {'modelVersion': 'synthetic'})
        self.assertEqual(transition_plan(plan, 'validated').state, 'validated')
        self.assertEqual(sizing['carrier_water_litres'], float(120 - Fraction(12, 5) - acid))
        for tank in stocks.tanks:
            salt = tank.salts[0]
            expected = Fraction(12 if salt.salt_id == 'a' else 24)
            self.assertEqual(salt.concentration.value * tank.stock_volume.value, float(expected))
        self.assertAlmostEqual(ph.reagent_mass.value, float(acid * 1400))
        self.assertAlmostEqual(
            ph.nutrient_contribution['N_NO3'].value,
            float(acid * 1400 * Fraction(138, 1000) * 1000 / 120),
        )

    def test_channel_errors(self):
        c = self.plan.commands[0]
        for commands in (
            (c, c),
            (replace(c, channel_id='unknown'),),
            (replace(c, requested_volume=VolumeLitres(0.2)),),
        ):
            with self.subTest(commands=commands), self.assertRaises(DeliveryError):
                self.compose(commands=commands)

    def test_missing_commands_are_draft_only(self):
        draft = self.compose(commands=())
        self.assertEqual(draft.state, 'draft')
        with self.assertRaises(DeliveryError):
            transition_plan(draft, 'validated')
        # A manually replaced approval state cannot bypass delivery completeness.
        with self.assertRaises(DeliveryError):
            transition_plan(replace(draft, state='validated'), 'operator-approved')

    def test_stock_material_and_volume_errors(self):
        stocks = self.plan.stocks
        t = stocks.tanks[0]
        salt = t.salts[0]
        mutations = [
            replace(stocks, tanks=(t, t)),
            replace(stocks, tanks=(replace(t, stock_volume=VolumeLitres(0.2)),)),
            replace(stocks, tanks=(replace(t, stock_volume=VolumeLitres(2)),)),
            replace(stocks, tanks=(replace(t, salts=(salt, salt)),)),
            replace(stocks, tanks=(replace(t, salts=()),)),
            replace(
                stocks,
                tanks=(replace(t, salts=(replace(salt, concentration=GramsPerLitre(11)),)),),
            ),
            replace(
                stocks,
                tanks=(
                    replace(
                        t,
                        salts=(replace(salt, concentration=GramsPerLitre(1e308)),),
                        stock_volume=VolumeLitres(10),
                        tank=replace(t.tank, capacity=VolumeLitres(10)),
                    ),
                ),
                injection_ratio=InjectionRatio(1),
            ),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(DeliveryError):
                self.compose(stocks=mutation)

    def test_inconsistent_recipe_mass(self):
        r = self.plan.recipe
        for salts in (
            (r.salts[0], r.salts[0]),
            (replace(r.salts[0], mass=MassGrams(2)),),
            (replace(r.salts[0], dose=GramsPerLitre(0.2)),),
        ):
            bad = replace(r, salts=salts)
            with self.subTest(salts=salts), self.assertRaises(DeliveryError):
                self.compose(recipe=bad, stocks=replace(self.plan.stocks, recipe=bad))

    def test_reagent_identity_volume_and_carrier(self):
        water, curve, reagent = inputs()
        ph = plan_ph(
            water,
            curve,
            reagent,
            6.7,
            VolumeLitres(10),
            VolumeLitres(1),
            {'N_NO3': 100},
            {'N_NO3': 111.592},
        )
        for mutation in (
            {'final_volume': None},
            {'final_volume': VolumeLitres(100)},
            {'reagent_channel_id': 'A'},
            {'reagent_channel_id': ''},
            {'reagent_volume_litres': -1},
            {'reagent_volume_litres': float('inf')},
            {'reagent_volume_litres': 9.9},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(DeliveryError):
                self.compose(ph_plan=replace(ph, **mutation))
        zero = replace(ph, reagent_volume_litres=0)
        self.compose(ph_plan=zero)
        with self.assertRaises(DeliveryError):
            self.compose(
                ph_plan=zero,
                commands=self.plan.commands + (replace(self.plan.commands[0], channel_id='acid'),),
            )
        with self.assertRaises(DeliveryError):
            transition_plan(
                replace(
                    self.compose(ph_plan=ph),
                    stocks=replace(self.plan.stocks, mixture_approved=True),
                ),
                'validated',
            )

    def test_envelope_errors_and_blocked_transition(self):
        from flahax.delivery_plan import delivery_report

        p = self.plan
        for changes in (
            {'recipe': None},
            {'stocks': None},
            {'ph_plan': 1},
            {'stocks': replace(p.stocks, recipe=replace(p.recipe, feasible=False))},
            {'commands': (None,)},
            {'audit_record': {}},
            {'audit_record': {'modelVersion': 1}},
            {'audit_record': {'modelVersion': ' '}},
            {'stocks': replace(p.stocks, tanks=())},
        ):
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                self.compose(**changes)
        infeasible = replace(p.recipe, feasible=False)
        with self.assertRaises(DeliveryError):
            self.compose(recipe=infeasible, stocks=replace(p.stocks, recipe=infeasible))
        for target in ('unknown', 'executed'):
            with self.assertRaises(DeliveryError):
                transition_plan(p, target)
        with self.assertRaises(DeliveryError):
            transition_plan(None, 'validated')
        with self.assertRaises(DeliveryError):
            delivery_report(None)
        self.assertEqual(transition_plan(p, 'blocked').state, 'blocked')


class EquilibriumChannelTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        from tests import test_equilibrium_delivery as fixtures

        fixtures.EquilibriumDeliveryTests.setUpClass()
        cls.plan = fixtures.EquilibriumDeliveryTests().compose()

    def test_missing_acid_and_mismatched_audit(self):
        p = self.plan
        for commands, audit in (
            (p.commands[1:], p.audit_record),
            (p.commands, {'modelVersion': 'x', 'equilibrium': {}}),
        ):
            with self.assertRaises(DeliveryError):
                compose_delivery_plan(p.recipe, p.stocks, p.ph_plan, commands, audit)

    def test_zero_reagent_and_review_gate(self):
        p = self.plan
        zero = replace(p.ph_plan, reagent_volume_litres=0, reagent_mass=MassGrams(0))
        audit = {'modelVersion': 'test'}
        draft = compose_delivery_plan(p.recipe, p.stocks, zero, p.commands[1:], audit)
        validated = transition_plan(draft, 'validated')
        no_verification = replace(
            validated,
            commands=tuple(
                replace(c, requires_operator_verification=False) for c in validated.commands
            ),
        )
        self.assertEqual(
            transition_plan(no_verification, 'operator-approved').state, 'operator-approved'
        )
        with self.assertRaises(DeliveryError):
            compose_delivery_plan(p.recipe, p.stocks, zero, p.commands, audit)
        review = replace(zero, incidental_assessment={'requiresReview': True})
        with self.assertRaises(DeliveryError) as caught:
            transition_plan(
                compose_delivery_plan(p.recipe, p.stocks, review, p.commands[1:], audit),
                'validated',
            )
        self.assertEqual(caught.exception.code, 'incidental_review_required')
