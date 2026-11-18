# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Convert explicit source-document bounds without inventing missing
intervals.
"""

from copy import deepcopy

from .delivery_contracts import DeliveryError
from .materials import make_grade, make_lot, resolve_material


def resolve_documented_assays(options, sources):
    """Return copied numeric bounds and their source evidence for recipe
    verification.
    """
    resolved = deepcopy(options)
    evidence = {}
    entries = resolved.get("product_element_factors")
    if not isinstance(entries, dict):
        return resolved, evidence
    for row in sources:
        name = row["name"]
        entry = entries.get(name)
        if isinstance(entry, dict) and entry.get("source") == "blend_ingredients":
            continue
        if not isinstance(entry, dict) or "source" not in entry:
            continue
        lot_mode = entry.get("source") == "lot" and set(entry) == {"source", "lot"}
        if entry != {"source": "grade"} and not lot_mode:
            raise DeliveryError("invalid_assay_document_source", "Select a supported assay source")
        product = row["product"]
        raw_grade = product.get("grade")
        if not isinstance(raw_grade, dict):
            raise DeliveryError("missing_assay_document", f"{name}: supply a grade document")
        grade = make_grade(raw_grade)
        if grade.impurity_limits:
            raise DeliveryError(
                "unsupported_assay_impurity_bounds",
                "Document impurity limits need explicit composition and bounded inventories; "
                "they cannot be treated as zero or inferred from assay factors",
            )
        if grade.composition != "single":
            raise DeliveryError(
                "unsupported_elemental_grade", "Document bounds require a single identity"
            )
        lot = make_lot(entry["lot"]) if lot_mode else None
        if lot is not None and set(lot.measured) - set(product["elements"]):
            raise DeliveryError(
                "assay_document_element_mismatch",
                "Lot measurements introduce elements absent from the nominal product; "
                "model them explicitly",
            )
        # Existing resolution validates catalogue identity and
        # lot-to-grade linkage.
        resolve_material(name, grade=grade, lot=lot)
        intervals, factors = {}, {}
        for key, nominal in product["elements"].items():
            if lot is None:
                low, high = grade.minimum.get(key), grade.maximum.get(key)
            else:
                measured, error = lot.measured.get(key), lot.uncertainty.get(key)
                low = measured - error if measured is not None and error is not None else None
                high = measured + error if measured is not None and error is not None else None
            if low is None or high is None or nominal <= 0 or low <= 0:
                raise DeliveryError(
                    "incomplete_assay_bounds",
                    f"{name}: {key} needs positive nominal content and explicit "
                    "positive lower/upper bounds",
                )
            intervals[key] = [low, high]
            factors[key] = [low / nominal, high / nominal]
        entries[name] = factors
        evidence[name] = dict(
            source="lot" if lot_mode else "grade",
            grade=deepcopy(raw_grade),
            lot=deepcopy(entry["lot"]) if lot_mode else None,
            units="elemental_mass_percent",
            intervals=intervals,
            oxide_conversions=deepcopy(lot.oxide_conversions if lot else grade.oxide_conversions),
            qualification=(
                "Documented bounds are inputs, not independent measurement verification."
            ),
        )
    return resolved, evidence
