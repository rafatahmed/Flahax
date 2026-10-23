# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""ASV timings: setup/validation outside timing; invalid results fail teardown."""

import subprocess
import sys

from .cases import NNLS_CASES, TARGETS, objective, read_fixture, require_chemistry


class Import:
    rounds = 1
    repeat = 10
    number = 1
    warmup_time = 0

    def time_fresh_process_import(self):
        # Includes interpreter/process startup; OS filesystem cache is NOT cold.
        subprocess.run(
            [sys.executable, "-c", "import flahax"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
        )


class Library:
    rounds = 1
    warmup_time = 0
    repeat = 10
    number = 1

    def setup(self):
        from flahax import load_library

        self.load = load_library
        if not self.load()["salts"]:
            raise ValueError("Empty catalogue")

    def time_load_library(self):
        self.result = self.load()

    def teardown(self):
        if hasattr(self, "result") and not self.result["salts"]:
            raise ValueError("Empty catalogue")


class Kernel:
    rounds = 1
    warmup_time = 0
    params = list(NNLS_CASES)
    param_names = ["case"]
    repeat = 10
    number = 1

    def setup(self, case):
        from flahax.engine import nnls
        from scipy.optimize import nnls as reference

        self.solve = nnls
        self.matrix, self.rhs = NNLS_CASES[case]
        weights, _ = reference(self.matrix, self.rhs)
        self.reference_objective = objective(self.matrix, self.rhs, weights)
        self.result = self.solve(self.matrix, self.rhs)
        self.teardown(case)

    def time_nnls(self, case):
        self.result = self.solve(self.matrix, self.rhs)

    def teardown(self, case):
        error = abs(objective(self.matrix, self.rhs, self.result) - self.reference_objective)
        if error > 1e-12 + 1e-8 * self.reference_objective:
            raise ValueError("NNLS objective differs from reference")


class Formulation:
    rounds = 1
    warmup_time = 0
    params = [0, 20]
    param_names = ["water_calcium_mg_l"]
    repeat = 10
    number = 1

    def setup(self, calcium):
        from flahax import load_library, recommend
        from .cases import evaluate_recipe

        self.solve, self.evaluate = recommend, evaluate_recipe
        self.products = load_library()["salts"]
        self.water = {"Ca": calcium}
        self.result = self.solve(self.products, TARGETS, self.water)
        self.teardown(calcium)

    def time_recommend(self, calcium):
        self.result = self.solve(self.products, TARGETS, self.water)

    def peakmem_recommend(self, calcium):
        self.result = self.solve(self.products, TARGETS, self.water)
        return self.result

    def teardown(self, calcium):
        report = self.evaluate(self.products, self.result, TARGETS, self.water)
        if not report["whole_recipe_passes"]:
            raise ValueError("Representative recipe no longer meets its fixed target tolerance")


class Equilibrium:
    rounds = 1
    warmup_time = 0
    params = [
        "products/mixed_products",
        "phases/calcite",
        "phases/mixed_product_phases",
        "products/mixed_target_ph_nitric",
    ]
    param_names = ["fixture"]
    repeat = 10
    number = 1
    timeout = 900

    def setup(self, fixture):
        from .cases import solve_fixture

        self.data = read_fixture(fixture)
        self.solve = solve_fixture
        self.result, self.acid = self.solve(self.data)
        self.teardown(fixture)

    def time_solve(self, fixture):
        self.result, self.acid = self.solve(self.data)

    def peakmem_solve(self, fixture):
        self.result, self.acid = self.solve(self.data)
        return self.result

    def track_final_state_iterations(self, fixture):
        return self.result.iterations

    def track_search_solves(self, fixture):
        # Total equilibrium solves per call; an acid target runs a search, so its
        # final-state iterations alone understate the work.
        from flahax import aqueous_model

        original, count = aqueous_model.solve, [0]

        def counted(*args, **kwargs):
            count[0] += 1
            return original(*args, **kwargs)

        aqueous_model.solve = counted
        try:
            self.solve(self.data)
        finally:
            aqueous_model.solve = original
        return count[0]

    def teardown(self, fixture):
        require_chemistry(self.data, self.result, self.acid)


class IrrigationEC:
    rounds = 1
    warmup_time = 0
    repeat = 10
    number = 1

    def setup(self):
        from flahax import calculate_ec_from_totals

        self.solve = calculate_ec_from_totals
        self.totals = {"K+": 0.01, "Cl-": 0.01}
        self.kwargs = dict(
            solution_id="benchmark-v1-kcl", ph_mode="calculated", phase_policy="dissolved"
        )
        self.result = self.solve(self.totals, **self.kwargs)
        self.teardown()

    def time_experimental_ec(self):
        self.result = self.solve(self.totals, **self.kwargs)

    def teardown(self):
        if self.result.status != "estimated" or abs(self.result.ec25_ms_cm - 1.4235) > 0.001:
            raise ValueError("Experimental EC regression changed; not a physical accuracy test")


class Delivery:
    rounds = 1
    warmup_time = 0
    repeat = 10
    number = 1
    timeout = 180

    def setup(self):
        # Existing synthetic composed workflow; includes record construction.
        # Root is needed for examples in isolated ASV environments.
        from .cases import ROOT

        if str(ROOT) not in sys.path:
            sys.path.append(str(ROOT))
        from examples.equilibrium_delivery import run

        self.run = run
        self.result = self.run()
        self.teardown()

    def time_composed_delivery_example(self):
        self.result = self.run()

    def teardown(self):
        if self.result["workflow"].stages["nitric"].status != "calculated":
            raise ValueError("Delivery calculation did not complete")
