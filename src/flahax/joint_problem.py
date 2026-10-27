# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Immutable joint-problem inputs and fixed-candidate residual evaluation.

No optimizer, new acceptance tolerance, or global feasibility claim is supplied.
All component coefficients are mol/g product, nutrients g/g product, and doses
are g/L final solution. Solvent mass denotes the final inventory, not source water.
"""

from dataclasses import dataclass, field
from collections.abc import Mapping
from types import MappingProxyType
import math

from .aqueous_model import chemistry, solve
from .composition import validate_profile
from .delivery_contracts import DeliveryError
from .engine import score
from .product_conversion import component_nutrient_masses


def _number(value, name, *, positive=False, signed=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if (positive and value <= 0) or (not signed and value < 0):
        raise DeliveryError('out_of_range', f'{name} is outside its permitted range')
    return float(value)


def _profile(value, name, *, components=False):
    if not isinstance(value, Mapping):
        raise DeliveryError('invalid_type', f'{name} must be an object')
    values = {k: _number(v, name) for k, v in value.items()}
    if components:
        if set(values) - set(chemistry()['bases']):
            raise DeliveryError('unknown_component', f'{name} contains unsupported components')
    else:
        values = validate_profile(values, name)
    return MappingProxyType(values)


@dataclass(frozen=True)
class JointSource:
    """One permitted product with explicit coefficients and solvent/density data.

    None components means missing chemistry; an empty map explicitly declares no
    conserved components. Solvent fraction is declared, never inferred from assay
    remainder. The caller is responsible for coefficient provenance and product roles.
    """

    product_id: str
    nutrients: Mapping
    components: Mapping | None
    solvent_fraction: float = 0.0
    density_kg_per_litre: float | None = None

    def __post_init__(self):
        if not isinstance(self.product_id, str) or not self.product_id.strip():
            raise DeliveryError('invalid_value', 'product_id must be a nonempty string')
        object.__setattr__(self, 'nutrients', _profile(self.nutrients, 'nutrient fractions'))
        if self.components is not None:
            object.__setattr__(
                self, 'components', _profile(self.components, 'components', components=True)
            )
        fraction = _number(self.solvent_fraction, 'solvent_fraction')
        if fraction + sum(self.nutrients.values()) > 1:
            raise DeliveryError(
                'inconsistent_assay', 'declared nutrient and solvent fractions exceed one'
            )
        if self.density_kg_per_litre is not None:
            _number(self.density_kg_per_litre, 'density', positive=True)


@dataclass(frozen=True)
class JointProblem:
    """One fixed-target problem with one explicitly offered reagent per candidate.

    reference_charge_mol_per_kg is the declared charge/proton closure on the same
    final-solvent basis; it must not be inferred from a nutrient subtotal. Analytical
    nutrient totals and dissolved/precipitated chemistry remain distinct outputs.
    """

    fertilizers: tuple[JointSource, ...]
    reagent: JointSource
    targets: Mapping
    water: Mapping
    water_components: Mapping | None
    final_volume_litres: float
    solvent_mass_kg: float
    target_ph: float
    reference_charge_mol_per_kg: float
    maximum_reagent_mass_g: float
    maximum_concentrations: Mapping = field(default_factory=dict)
    maximum_reagent_volume_litres: float | None = None
    phases: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.fertilizers, (tuple, list)):
            raise DeliveryError('invalid_type', 'fertilizers must be an explicit sequence')
        object.__setattr__(self, 'fertilizers', tuple(self.fertilizers))
        sources = (*self.fertilizers, self.reagent)
        if not all(isinstance(s, JointSource) for s in sources):
            raise DeliveryError('invalid_type', 'sources must be JointSource records')
        if len({s.product_id for s in sources}) != len(sources):
            raise DeliveryError('duplicate_product', 'fertilizer/reagent IDs must be distinct')
        for name in ('targets', 'water', 'maximum_concentrations'):
            object.__setattr__(self, name, _profile(getattr(self, name), name))
        if not self.targets:
            raise DeliveryError('missing_field', 'targets are required')
        if self.water_components is not None:
            object.__setattr__(
                self,
                'water_components',
                _profile(self.water_components, 'water components', components=True),
            )
        _number(self.final_volume_litres, 'final volume', positive=True)
        _number(self.solvent_mass_kg, 'final solvent mass', positive=True)
        if _number(self.target_ph, 'target pH') > 14:
            raise DeliveryError('out_of_range', 'target pH must be in [0,14]')
        _number(self.reference_charge_mol_per_kg, 'reference charge', signed=True)
        _number(self.maximum_reagent_mass_g, 'maximum reagent mass')
        if self.maximum_reagent_volume_litres is not None:
            _number(self.maximum_reagent_volume_litres, 'maximum reagent volume')
            if self.reagent.density_kg_per_litre is None:
                raise DeliveryError('missing_density', 'a volume cap requires reagent density')
        if not isinstance(self.phases, (tuple, list)) or not all(
            isinstance(p, str) for p in self.phases
        ):
            raise DeliveryError('invalid_type', 'phases must be an explicit sequence')
        object.__setattr__(self, 'phases', tuple(self.phases))
        if set(self.phases) - {p['name'] for p in chemistry()['phases']}:
            raise DeliveryError('unknown_phase', 'unsupported phase selection')

    def evaluate(self, fertilizer_g_per_litre, reagent_g_per_litre, *, equilibrium_start=None):
        """Evaluate a supplied dose vector without fitting, clipping or changing targets.

        Missing fertilizer IDs mean zero. Charge residual and equilibrium residuals
        are exposed without defining a new pass threshold. Nonconvergence propagates
        as DeliveryError, never as an accepted or substituted candidate. An optional
        equilibrium_start only seeds the existing safeguarded equilibrium iteration;
        callers must still verify the final candidate from a fresh solve.
        """
        doses = _profile_doses(fertilizer_g_per_litre, self.fertilizers)
        q = _number(reagent_g_per_litre, 'reagent dose')
        sources = [*((s, doses.get(s.product_id, 0)) for s in self.fertilizers), (self.reagent, q)]
        concentrations = dict(self.water)
        components = dict(self.water_components or {})
        missing = self.water_components is None
        solvent = 0.0
        for source, dose in sources:
            solvent += dose * self.final_volume_litres * source.solvent_fraction / 1000
            for ion, fraction in source.nutrients.items():
                concentrations[ion] = concentrations.get(ion, 0) + 1000 * fraction * dose
            if source.components is None:
                missing |= dose > 0
            else:
                for basis, coefficient in source.components.items():
                    components[basis] = (
                        components.get(basis, 0)
                        + coefficient * dose * self.final_volume_litres / self.solvent_mass_kg
                    )
        # Catch overflow before it enters chemistry or produces a misleading score.
        concentrations = dict(_profile(concentrations, 'final nutrients'))
        components = dict(_profile(components, 'final components', components=True))
        solvent = _number(solvent, 'declared product solvent')
        mass = _number(q * self.final_volume_litres, 'reagent mass')
        volume = (
            mass / (1000 * self.reagent.density_kg_per_litre)
            if self.reagent.density_kg_per_litre is not None
            else None
        )
        if volume is not None:
            volume = _number(volume, 'reagent volume')
        try:
            loss, rows = score(concentrations, self.targets)
            _number(loss, 'objective')
        except OverflowError as exc:
            raise DeliveryError('numerical_failure', 'objective overflow') from exc
        violations = [
            dict(kind='zero_target', symbol=k)
            for k, t in self.targets.items()
            if t == 0 and concentrations.get(k, 0) > 0
        ]
        violations += [
            dict(kind='maximum', symbol=k)
            for k, cap in self.maximum_concentrations.items()
            if concentrations.get(k, 0) > cap
        ]
        violations += [
            dict(kind='contradictory_target', symbol=k)
            for k, t in self.targets.items()
            if k in self.maximum_concentrations and t > self.maximum_concentrations[k]
        ]
        for kind, failed in (
            ('reagent_mass', mass > self.maximum_reagent_mass_g),
            ('solvent_inventory', solvent > self.solvent_mass_kg),
            ('final_volume', volume is not None and volume > self.final_volume_litres),
            (
                'reagent_volume',
                volume is not None
                and volume
                > (
                    self.maximum_reagent_volume_litres
                    if self.maximum_reagent_volume_litres is not None
                    else self.final_volume_litres
                ),
            ),
        ):
            if failed:
                violations.append(dict(kind=kind))
        state = (
            None
            if missing
            else solve(components, self.target_ph, phases=self.phases, start=equilibrium_start)
        )
        chemistry_nutrients = {
            k: g * self.solvent_mass_kg / self.final_volume_litres * 1000
            for k, g in component_nutrient_masses(components).items()
        }
        return dict(
            status='missing_chemistry' if missing else 'requires_joint_acceptance',
            concentrations=concentrations,
            loss=loss,
            rows=rows,
            violations=violations,
            componentsMolPerKg=None if missing else components,
            nutrientComponentDifference=None
            if missing
            else {
                k: concentrations.get(k, 0) - chemistry_nutrients.get(k, 0)
                for k in concentrations.keys() | chemistry_nutrients.keys()
            },
            reagentMassGrams=mass,
            reagentVolumeLitres=volume,
            reagentSolventKg=q * self.final_volume_litres * self.reagent.solvent_fraction / 1000,
            declaredProductSolventKg=solvent,
            equilibrium=state,
            chargeResidual=None
            if state is None
            else state.charge_balance - self.reference_charge_mol_per_kg,
            acceptance='Not assessed: evaluate residual qualification, model domain '
            'and phase policy separately.',
        )


def _profile_doses(value, sources):
    if not isinstance(value, Mapping) or set(value) - {s.product_id for s in sources}:
        raise DeliveryError('unknown_product', 'doses must map only supplied fertilizer IDs')
    return {k: _number(v, 'fertilizer dose') for k, v in value.items()}
