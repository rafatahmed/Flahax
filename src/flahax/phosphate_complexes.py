"""Fixed-pH Ca/Mg orthophosphate complexation kernel at 25 °C."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma
from .phosphate import LOG_BETA_H2PO4_25C, LOG_BETA_H3PO4_25C, LOG_BETA_HPO4_25C


LOG_BETA_CA_PO4 = 6.459
LOG_BETA_CA_HPO4 = 2.739
LOG_BETA_CA_H2PO4 = 1.408
LOG_BETA_MG_PO4 = 6.589
LOG_BETA_MG_HPO4 = 2.870
LOG_BETA_MG_H2PO4 = 1.513
LOG_BETA_NA_HPO4 = 0.290
LOG_K_HYDROXYAPATITE_HPO4 = -3.421


@dataclass(frozen=True, slots=True)
class CalciumMagnesiumPhosphateSpeciation:
    """Species and hydroxyapatite SI for a fixed-pH, fixed-I solution."""

    calcium_molal: float
    magnesium_molal: float
    phosphate_molal: float
    sodium_molal: float
    ph: float
    ionic_strength: float
    free_calcium_molal: float
    free_magnesium_molal: float
    free_phosphate_molal: float
    hpo4_molal: float
    h2po4_molal: float
    calcium_hpo4_molal: float
    magnesium_hpo4_molal: float
    hydroxyapatite_si: float


def hydroxyapatite_hpo4_activity_at_equilibrium(calcium_activity: float, ph: float) -> float:
    """Return the HPO4-2 activity at SI(Hydroxyapatite) = 0.

    Uses the `phreeqc.dat` reaction
    ``Hydroxyapatite + 4H+ = 5Ca+2 + 3HPO4-2 + H2O``.
    It is a thermodynamic boundary, not a precipitation-kinetics prediction.
    """
    if not math.isfinite(calcium_activity) or calcium_activity <= 0:
        raise DeliveryError("out_of_range", "calcium activity must be positive and finite")
    if not math.isfinite(ph) or not 0 <= ph <= 14:
        raise DeliveryError("out_of_range", "pH must be finite and in [0, 14]")
    log_hpo4 = (LOG_K_HYDROXYAPATITE_HPO4 - 5 * math.log10(calcium_activity) - 4 * ph) / 3
    return 10.0 ** log_hpo4


def _solve_linear3(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise DeliveryError("nonconvergent", "phosphate complexation Jacobian is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(3):
            if row != column:
                scale = augmented[row][column]
                augmented[row] = [value - scale * base for value, base in zip(augmented[row], augmented[column])]
    return [augmented[row][3] for row in range(3)]


def calcium_magnesium_phosphate_speciation(
    calcium_molal: float, magnesium_molal: float, phosphate_molal: float, sodium_molal: float, ph: float, ionic_strength: float
) -> CalciumMagnesiumPhosphateSpeciation:
    """Solve source-defined Ca/Mg phosphate complexes at fixed pH and I.

    The model is limited to 25 °C and I <= 0.1 mol/kgw. It includes the
    phosphate acid forms, Ca/Mg phosphate complexes, and NaHPO4-; it does not
    solve charge balance, pH, ionic strength, precipitation, or other ligands.
    """
    values = (calcium_molal, magnesium_molal, phosphate_molal, sodium_molal, ph, ionic_strength)
    if not all(math.isfinite(value) for value in values):
        raise DeliveryError("invalid_value", "all complexation inputs must be finite")
    if min(calcium_molal, magnesium_molal, phosphate_molal, sodium_molal) <= 0:
        raise DeliveryError("out_of_range", "analytical totals must be positive")
    if not 0 <= ph <= 14 or not 0 <= ionic_strength <= 0.1:
        raise DeliveryError("out_of_range", "pH must be in [0, 14] and ionic strength in [0, 0.1]")
    g1, g2, g3 = (davies_gamma(charge, ionic_strength) for charge in (1, 2, 3))
    a_h = 10.0 ** -ph

    def species(logs: list[float]) -> dict[str, float]:
        a_ca, a_mg, a_po4 = (10.0 ** value for value in logs)
        a_hpo4 = 10.0 ** LOG_BETA_HPO4_25C * a_po4 * a_h
        a_h2po4 = 10.0 ** LOG_BETA_H2PO4_25C * a_po4 * a_h**2
        a_h3po4 = 10.0 ** LOG_BETA_H3PO4_25C * a_po4 * a_h**3
        a_na = sodium_molal * g1
        result = {
            "ca": a_ca / g2, "mg": a_mg / g2, "po4": a_po4 / g3,
            "hpo4": a_hpo4 / g2, "h2po4": a_h2po4 / g1, "h3po4": a_h3po4,
            "ca_hpo4": 10.0 ** LOG_BETA_CA_HPO4 * a_ca * a_hpo4,
            "mg_hpo4": 10.0 ** LOG_BETA_MG_HPO4 * a_mg * a_hpo4,
            "ca_h2po4": 10.0 ** LOG_BETA_CA_H2PO4 * a_ca * a_h2po4 / g1,
            "mg_h2po4": 10.0 ** LOG_BETA_MG_H2PO4 * a_mg * a_h2po4 / g1,
            "ca_po4": 10.0 ** LOG_BETA_CA_PO4 * a_ca * a_po4 / g1,
            "mg_po4": 10.0 ** LOG_BETA_MG_PO4 * a_mg * a_po4 / g1,
            "na_hpo4": 10.0 ** LOG_BETA_NA_HPO4 * a_na * a_hpo4 / g1,
            "a_ca": a_ca, "a_hpo4": a_hpo4,
        }
        result["ca_total"] = result["ca"] + result["ca_hpo4"] + result["ca_h2po4"] + result["ca_po4"]
        result["mg_total"] = result["mg"] + result["mg_hpo4"] + result["mg_h2po4"] + result["mg_po4"]
        result["p_total"] = sum(result[name] for name in ("po4", "hpo4", "h2po4", "h3po4", "ca_hpo4", "mg_hpo4", "ca_h2po4", "mg_h2po4", "ca_po4", "mg_po4", "na_hpo4"))
        return result

    targets = (calcium_molal, magnesium_molal, phosphate_molal)
    logs = [math.log10(calcium_molal * g2), math.log10(magnesium_molal * g2), math.log10(phosphate_molal * g3)]
    for _ in range(30):
        current = species(logs)
        residual = [math.log10(current[name] / target) for name, target in zip(("ca_total", "mg_total", "p_total"), targets)]
        if max(abs(value) for value in residual) < 1e-12:
            break
        step = 1e-5
        jacobian = []
        for row in range(3):
            jacobian.append([])
            for column in range(3):
                perturbed = logs[:]
                perturbed[column] += step
                changed = species(perturbed)
                changed_residual = math.log10(changed[("ca_total", "mg_total", "p_total")[row]] / targets[row])
                jacobian[row].append((changed_residual - residual[row]) / step)
        delta = _solve_linear3(jacobian, [-value for value in residual])
        logs = [value + min(1.0, max(-1.0, adjustment)) for value, adjustment in zip(logs, delta)]
    else:
        raise DeliveryError("nonconvergent", "phosphate complexation did not converge")
    result = species(logs)
    hap_iap = 5 * math.log10(result["a_ca"]) + 3 * math.log10(result["a_hpo4"]) - 4 * math.log10(a_h)
    return CalciumMagnesiumPhosphateSpeciation(calcium_molal, magnesium_molal, phosphate_molal, sodium_molal, ph, ionic_strength, result["ca"], result["mg"], result["po4"], result["hpo4"], result["h2po4"], result["ca_hpo4"], result["mg_hpo4"], hap_iap - LOG_K_HYDROXYAPATITE_HPO4)
