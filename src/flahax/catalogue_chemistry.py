# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The explicit aqueous-chemistry identity of every shipped fertilizer.

This is the input boundary for the unified P2/P3 equilibrium system.  A product
may not enter an equilibrium calculation by its display name alone: it has
dissolved ions, a family, a source profile, and a temperature domain.  Since
interactive mix Task 11 these are read from what the material puts in the water
(material_chemistry); ``PRODUCT_CHEMISTRY`` is a view of the catalogue's records.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from .delivery_contracts import DeliveryError


@dataclass(frozen=True, slots=True)
class ProductChemistry:
    """Source-versioned chemical identity; not a nutrient-assay replacement."""

    name: str
    family: str
    components: tuple[str, ...]
    source_profile: str
    temperature_c: float = 25.0
    ions: tuple = ()  # (ion, count per formula unit) pairs; complexes carry their ligand

    def __post_init__(self) -> None:
        if not self.name or not self.family or not self.components or not self.source_profile:
            raise DeliveryError(
                "missing_field",
                "product chemistry requires name, family, components, and source profile",
            )


PHREEQC_MINTEQ_V4 = "USGS PHREEQC 3.8.6 minteq.v4.dat, 25 C"


# The canonical, fully deprotonated ligand forms used by the unified solver.
# EDDHA is explicitly the o,o form selected for the otherwise unspecific
# catalogue product; it is not interchangeable with o,p-EDDHA.
def _ligand_profiles():
    # Public summaries must be derived from the actual reaction set, not a
    # second, independently rounded table of equilibrium constants.
    from .aqueous_model import chemistry

    result = {}
    for label, basis, charge in (
        ("EDTA", "Edta-4", -4),
        ("DTPA", "Dtp-5", -5),
        ("o,o-EDDHA", "Edd-4", -4),
        ("citrate", "Citrate-3", -3),
    ):
        protonation, metals = {}, {}
        sources = set()
        for record in chemistry()['aqueous']:
            powers = record['powers']
            if powers.get(basis) != 1:
                continue
            sources.add(record['source'])
            other = set(powers) - {basis}
            if other == {'H+'} and powers['H+'] > 0:
                protonation[powers['H+']] = record['beta']
            if len(other) == 1 and next(iter(other)) in {
                'Fe+3',
                'Fe+2',
                'Mn+2',
                'Zn+2',
                'Cu+2',
                'Ca+2',
                'Mg+2',
            }:
                metals[next(iter(other))] = record['beta']
        result[label] = dict(
            charge=charge,
            protonation_log_k=tuple(protonation[k] for k in sorted(protonation)),
            metal_log_beta=metals,
            source='; '.join(sorted(sources)),
        )
    return result


LIGAND_PROFILES = _ligand_profiles()


class _CatalogueChemistry(Mapping):
    """The catalogue's records through ``material_chemistry``, keyed by name; built on first use."""

    _data: dict | None = None

    def _records(self) -> dict:
        if self._data is None:
            from .engine import load_library  # deferred: the engine imports product_conversion
            from .material_chemistry import material_chemistry

            type(self)._data = {
                str(s['name']): material_chemistry(s) for s in load_library()['salts']
            }
        return self._data

    def __getitem__(self, name: str) -> ProductChemistry:
        return self._records()[name]

    def __iter__(self):
        return iter(self._records())

    def __len__(self) -> int:
        return len(self._records())


PRODUCT_CHEMISTRY: Mapping[str, ProductChemistry] = _CatalogueChemistry()


def chemistry_for_product(name: str) -> ProductChemistry:
    """Return a product's explicit equilibrium identity or fail closed."""
    try:
        return PRODUCT_CHEMISTRY[name]
    except KeyError as exc:
        raise DeliveryError(
            "unsupported_product_chemistry", f"no chemistry record for {name!r}"
        ) from exc


def assert_catalogue_coverage(products: list[Mapping[str, object]]) -> None:
    """Require exact one-to-one coverage of the package fertilizer catalogue."""
    names = {str(product.get("name", "")) for product in products}
    mapped = set(PRODUCT_CHEMISTRY)
    if names != mapped:
        missing, stale = sorted(names - mapped), sorted(mapped - names)
        raise DeliveryError("catalogue_chemistry_mismatch", f"missing={missing}; stale={stale}")
