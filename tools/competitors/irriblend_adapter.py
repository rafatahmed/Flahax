"""Drive the authors' Irriblend-DSW optimiser (MIT, pinned) with the FlahaX catalogue.

Irriblend-DSW: Gallego-Elvira, B., Reca, J., Martin-Gorriz, B., Maestre-Valero, J. F. and
Martinez-Alvarez, V. (2021) Irriblend-DSW: a decision support tool for the optimal blending
of desalinated and conventional irrigation waters in dry regions. Agricultural Water
Management 255, 107012, doi:10.1016/j.agwat.2021.107012. Code: https://github.com/irriblend-dsw/irriblend-dsw-v1, MIT licence
(Copyright (c) 2026 irriblend-dsw), added at commit a046d5c on top of the 2021 code
commit 197d650. The module is used unmodified; its SHA-256 is checked before import.

Its notebook mounts Google Drive and writes to a fixed Colab path, so it does not run
outside Colab. Its optimiser does: ``ferti_eco_min(ferts_xlsx, ideal_sol, water,
water_EC, max_EC)`` minimises fertiliser cost with SciPy SLSQP (0-3 g/L per product)
subject to exact NO3-, NH4+, H2PO4-, K+ and H+ (residual HCO3-), Ca, Mg, SO4, Cl and
Na at or above need, and an EC cap (anion meq/L / 10). This adapter writes the FlahaX
catalogue into its "ferts" sheet and calls it directly.

Translation, following the authors' case-study sheets (mmol per g; phosphate as
H2PO4-; an acid's H+ column is minus its anion):
- products whose nutrients all fit the ten Irriblend columns are translated exactly
  (mmol/g = mass % x 10 / molar mass; round trip checked);
- phosphoric acid: H+ -1 per P; dibasic phosphates: H+ +1 per P (HPO4 2- = H2PO4- - H+);
- micronutrient products, chelates, urea (no urea column) and potassium citrate
  (citrate has no column; it would enter as charge-free K) are outside the model and
  left out, with the reason recorded.
Neutral settings, because the catalogue has no prices and the other engines apply no EC
limit: every product costs 1 EUR/kg (cost = total grams), the EC cap is non-binding, and
the residual HCO3- target is 0 (the benchmark waters carry no bicarbonate). A result is
kept only if it passes the authors' own filter (final NO3- not below the ideal).
"""
import hashlib
import os
from pathlib import Path
import sys
import tempfile

from flahax.product_conversion import MOLAR_MASS

PIN = {"repository": "https://github.com/irriblend-dsw/irriblend-dsw-v1",
       "commit": "a046d5c", "code_commit": "197d650", "licence": "MIT",
       "copyright": "Copyright (c) 2026 irriblend-dsw",
       "module": "code/irriblend_dsw_funs.py",
       "module_sha256": "2a3c06f8a511e50b1dd13e796eaa32ba46db27e9493edd009aeb7d7fd414732e",
       "citation": "Gallego-Elvira et al. (2021) Agric. Water Manag. 255, 107012, doi:10.1016/j.agwat.2021.107012"}
# Irriblend column order, and the FlahaX element each column counts.
COLUMNS = ("NO3-", "NH4+", "H2PO4-", "K+", "Ca++", "Mg++", "SO4-2", "Cl-", "Na+", "H+")
ELEMENT = {"NO3-": "N_NO3", "NH4+": "N_NH4", "H2PO4-": "P", "K+": "K", "Ca++": "Ca", "Mg++": "Mg",
           "SO4-2": "S", "Cl-": "Cl", "Na+": "Na"}
MASS = {"N_NO3": MOLAR_MASS["N"], "N_NH4": MOLAR_MASS["N"], "P": MOLAR_MASS["P"], "K": MOLAR_MASS["K"],
        "Ca": MOLAR_MASS["Ca"], "Mg": MOLAR_MASS["Mg"], "S": MOLAR_MASS["S"], "Cl": MOLAR_MASS["Cl"],
        "Na": MOLAR_MASS["Na"]}
H_PER_P = {"H3PO4": -1.0, "K2HPO4": 1.0, "(NH4)2HPO4": 1.0}
UNREPRESENTED_ANIONS = {"C6H5K3O7": "citrate has no Irriblend column"}
MAX_EC_NON_BINDING = 1e6
SOURCE_ENV = "IRRIBLEND_DSW_CODE"


def load(code_dir=None):
    """Import the pinned, unmodified irriblend_dsw_funs module after checking its hash."""
    code_dir = Path(code_dir or os.environ.get(SOURCE_ENV, "irriblend/code"))
    module = code_dir / "irriblend_dsw_funs.py"
    digest = hashlib.sha256(module.read_bytes()).hexdigest()
    if digest != PIN["module_sha256"]:
        raise RuntimeError(f"{module} does not match the pinned Irriblend-DSW module ({digest})")
    os.environ.setdefault("MPLBACKEND", "Agg")      # the module imports pyplot; no window is opened
    sys.path.insert(0, str(code_dir))
    try:
        import irriblend_dsw_funs
    finally:
        sys.path.remove(str(code_dir))
    return irriblend_dsw_funs


def translate(products):
    """(rows {name: {column: mmol/g}}, excluded {name: reason}) for the Irriblend 'ferts' sheet."""
    rows, excluded = {}, {}
    for product in products:
        elements = {k: float(v) for k, v in product["elements"].items() if v}
        outside = sorted(set(elements) - set(MASS))
        if outside:
            excluded[product["name"]] = "no Irriblend column for " + ", ".join(outside)
            continue
        if product.get("formula") in UNREPRESENTED_ANIONS:
            excluded[product["name"]] = UNREPRESENTED_ANIONS[product["formula"]]
            continue
        row = {column: elements.get(ELEMENT[column], 0.0) * 10.0 / MASS[ELEMENT[column]] for column in COLUMNS[:-1]}
        row["H+"] = H_PER_P.get(product.get("formula"), 0.0) * row["H2PO4-"]
        rows[product["name"]] = row
    return rows, excluded


def validate_translation(products, rows):
    """Largest relative error of the round trip mmol/g -> mass %, over every translated value."""
    by_name = {p["name"]: p for p in products}
    worst = 0.0
    for name, row in rows.items():
        for column, element in ELEMENT.items():
            original = float(by_name[name]["elements"].get(element, 0.0))
            back = row[column] * MASS[element] / 10.0
            if original:
                worst = max(worst, abs(back - original) / original)
            elif back:
                raise ValueError(f"{name}: {column} appeared from nothing")
    return worst


def write_ferts(rows, path):
    """The authors' 'ferts' layout: name, ten ion columns (mmol/g), price (EUR/kg), density."""
    import pandas as pd
    frame = pd.DataFrame([[row[c] for c in COLUMNS] + [1.0, 1.0] for row in rows.values()],
                         index=list(rows), columns=[*COLUMNS, "price (euro/kg)", "d (g/cm3)"])
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="ferts")
    return path


def mmol_per_litre(mg_per_litre):
    """FlahaX elemental mg/L -> the Irriblend ion vector, mmol/L, HCO3- last."""
    return [float(mg_per_litre.get(ELEMENT[c], 0.0)) / MASS[ELEMENT[c]] for c in COLUMNS[:-1]] + [0.0]


class Irriblend:
    """One translated catalogue and its 'ferts' sheet; solve() per formula and water."""

    def __init__(self, products, code_dir=None):
        self.module = load(code_dir)
        self.rows, self.excluded = translate(products)
        self.translation_error = validate_translation(products, self.rows)
        self.ids = {p["name"]: p["id"] for p in products}
        self._dir = tempfile.TemporaryDirectory()
        self.ferts = write_ferts(self.rows, Path(self._dir.name) / "user_input.xlsx")

    def solve(self, targets, water):
        """{'salts': [...]} as the optimiser returns it, or None when its own filter rejects it."""
        ideal = mmol_per_litre(targets)
        _, names, grams, final = self.module.ferti_eco_min(str(self.ferts), ideal, mmol_per_litre(water), 0.0,
                                                           MAX_EC_NON_BINDING)
        if final[0] < ideal[0]:          # the authors' filter in read_input_and_run_simulation
            return None
        return {"salts": [{"id": self.ids[name], "gramsPerLitre": float(g)} for name, g in zip(names, grams)]}

    def close(self):
        self._dir.cleanup()
