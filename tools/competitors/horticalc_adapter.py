"""Drive Horticalc (pinned v0.6.7, commit db4e68c) with the FlahaX catalogue.

Horticalc stores composition as forms: N as elemental N per form (NO3, NH4,
UREA), P/K/Ca/Mg/Na as oxides, S as SO4, Si as SiO2, traces as elements. The
translation inverts Horticalc's own conversion rules with its own molar masses,
so the round trip is exact; `validate_translation` proves it before any solve.
"""
from horticalc import chemistry
from horticalc.data_io import Fertilizer, load_molar_masses
from horticalc.solver import solve_recipe_data

PIN = {"repository": "https://github.com/onethree7/Horticalc", "tag": "v0.6.7",
       "commit": "db4e68c76639df2920f43be06c77dd4c16498863", "licence": "GPL-3.0-or-later"}
N_FORMS = {"N_NO3": "NO3", "N_NH4": "NH4", "N_UREA": "UREA"}
CONFIGS = {
    # Shipped defaults: total-N objective only; S, Na and Cl report-only.
    "as_shipped": {},
    # Aligned with FlahaX's objective: each N form and S are objectives.
    "aligned": {"nitrogen_objective_mode": "n_forms_only", "s_objective_enabled": True},
}


def _form_for(element):
    for oxide, (el, mult) in chemistry.OXIDE_ELEMENT_RULES.items():
        if el == element:
            return oxide, mult
    for form, (el, mult) in chemistry.FORM_ELEMENT_RULES.items():
        if el == element:
            return form, mult
    raise KeyError(element)


def translate(salts, mm=None):
    """FlahaX catalogue (elemental mass %) -> {name: Fertilizer} with exact inverse forms."""
    mm = mm or load_molar_masses()
    out = {}
    for salt in salts:
        comp = {}
        for key, percent in salt["elements"].items():
            fraction = float(percent) / 100.0
            if key in N_FORMS:
                comp[N_FORMS[key]] = comp.get(N_FORMS[key], 0.0) + fraction
                continue
            form, mult = _form_for(key)
            comp[form] = comp.get(form, 0.0) + fraction * mm[form] / (mult * mm[key])
        out[salt["name"]] = Fertilizer(name=salt["name"], liquid=False, weight_factor=1.0, comp=comp)
    return out


def validate_translation(salts, ferts, mm=None):
    """Largest relative difference over all element contributions at 1 g/L."""
    from horticalc.solver import _fertilizer_element_contrib_per_g
    mm = mm or load_molar_masses()
    worst = 0.0
    for salt in salts:
        got = _fertilizer_element_contrib_per_g(ferts[salt["name"]], mm)
        for key, percent in salt["elements"].items():
            want = float(percent) * 10.0  # mg/L from 1 g/L
            worst = max(worst, abs(got.get(key, 0.0) - want) / want)
    return worst


def solve(ferts, targets, water, config, mm=None):
    """Return {name: g/L} for one formula and water under a Horticalc configuration."""
    recipe = {"liters": 1.0, "osmosis_percent": 0, "urea_as_nh4": False,
              "fertilizers_allowed": list(ferts), "targets": dict(targets),
              "solver_config": dict(CONFIGS[config])}
    result = solve_recipe_data(recipe, ferts=ferts, mm=mm or load_molar_masses(),
                               water_profile_data={"mg_per_l": dict(water), "osmosis_percent": 0})
    return result
