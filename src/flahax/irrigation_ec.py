"""EXPERIMENTAL (M1): speciation-based irrigation EC from McCleskey et al. (2012).

Source: McCleskey, Nordstrom, Ryan, Ball (2012) Geochim. Cosmochim. Acta 77,
369-382, Table 1 (Eq. 8 parameters), shipped in
data/conductivity_mccleskey2012.json and pinned by SHA-256. This module holds
the coefficient loader, the ionic molal conductivity and EC25 from speciated
analytical totals. Units are mS kg cm-1 mol-1 x mol/kgw (no density
conversion). Not validated for concentrated nutrient solutions; every result
carries QUALIFIER.
"""
import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files

import json

from .aqueous_model import AqueousResult, chemistry, solve
from .calculated_ph import calculate_equilibrium_ph
from .delivery_contracts import DeliveryError

_RESOURCE = 'data/conductivity_mccleskey2012.json'
_RAW = files('flahax').joinpath(_RESOURCE).read_bytes()
COEFFICIENTS_SHA256 = hashlib.sha256(_RAW).hexdigest()


@lru_cache(maxsize=1)
def _load():
    return json.loads(_RAW.decode('utf-8'))


def load_conductivity_coefficients() -> dict:
    """Return the cached McCleskey 2012 Table 1 data (treat as read-only)."""
    return _load()


def covered_species() -> frozenset:
    """FlahaX aqueous species names that have a Table 1 coefficient."""
    return frozenset(_load()['species_map'])


def ionic_molal_conductivity(ion: str, ionic_strength: float,
                             temperature_c: float = 25.0) -> float:
    """Eq. 8: lambda = lambda0(T) - A(T)*sqrt(I)/(1 + B*sqrt(I)), T in C."""
    row = _load()['ions'].get(ion) if isinstance(ion, str) else None
    if row is None:
        raise DeliveryError('unknown_ion', f'no McCleskey 2012 Table 1 coefficient for {ion!r}')
    for name, v in (('ionic_strength', ionic_strength), ('temperature_c', temperature_c)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if ionic_strength < 0:
        raise DeliveryError('invalid_value', 'ionic_strength must be >= 0')
    t = float(temperature_c)
    poly = lambda c: c[0] * t * t + c[1] * t + c[2]
    root = math.sqrt(ionic_strength)
    return poly(row['lambda0']) - poly(row['A']) * root / (1 + row['B'] * root)


QUALIFIER = 'Accuracy on this fertilizer mixture has not yet been established.'
MODEL_VERSION = 'irrigation-ec-mccleskey2012-m1-experimental'
CONDUCTIVITY_UNITS = 'mS kg cm-1 mol-1 x mol/kgw'
_REPORTING_TOLERANCE = 1e-12
_ASSAY_LIMIT_PERCENT = 0.1
_CORE_AUDIT_KEYS = frozenset((
    'temperature_reference_c', 'ph_mode', 'ph', 'phase_policy', 'phases', 'carbon_boundary',
    'chemistrySha256', 'coefficientsSha256', 'equation', 'speciesMappingVersion',
    'conductivity_units', 'unit_conversions', 'solver_iterations', 'charge_balance', 'model'))


@dataclass(frozen=True)
class IrrigationECResult:
    """EXPERIMENTAL (M1) irrigation EC25 result; see calculate_ec_from_totals."""
    status: str
    ec25_ms_cm: float | None
    known_species_subtotal_ms_cm: float | None
    contributions_ms_cm: dict
    transport_numbers: dict
    missing_species: tuple
    unrecorded_counterions_eq_per_kgw: float | None
    assay_charge_residual: dict
    reason: str | None
    ph: float | None
    ionic_strength: float | None
    precipitated_molal: dict
    warnings: tuple
    audit: dict
    qualifier: str = field(default=QUALIFIER)


@lru_cache(maxsize=1)
def _chemistry_sha256():
    return hashlib.sha256(files('flahax').joinpath('data/chemistry_25c.json').read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _charges():
    return {r['name']: r['charge'] for r in chemistry()['aqueous']}


def _is_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _validate_request(*, ph_mode, ph, phase_policy, phases, temperature_c, carbon_boundary,
                      assay_residual_eq):
    """Validate mode inputs; return (phases tuple, not_supported reason or None).

    Invalid input raises DeliveryError. Temperature and carbon boundary outside
    the M1 scope are not errors: they return a not_supported reason, checked
    before any solve.
    """
    if ph_mode == 'calculated':
        if ph is not None:
            raise DeliveryError('invalid_ph_input', "ph_mode='calculated' takes no supplied pH")
    elif ph_mode == 'supplied':
        if not _is_number(ph) or not 0 <= ph <= 14:
            raise DeliveryError('invalid_ph_input', "ph_mode='supplied' needs a finite pH in [0, 14]")
    else:
        raise DeliveryError('invalid_ph_input', "ph_mode must be 'calculated' or 'supplied'")
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError('invalid_phase_policy', 'phases must be a sequence of phase names')
    phases = tuple(phases)
    if not (phase_policy == 'dissolved' and phases == ()
            or phase_policy == 'equilibrated' and phases):
        raise DeliveryError('invalid_phase_policy',
                            "phase_policy 'dissolved' needs phases=(); 'equilibrated' needs a nonempty phase list")
    if not _is_number(assay_residual_eq):
        raise DeliveryError('invalid_value', 'assay charge residual must be a finite number')
    if not _is_number(temperature_c):
        raise DeliveryError('invalid_value', 'temperature_c must be a finite number')
    if temperature_c != 25:
        return phases, 'temperature_outside_reference'
    if carbon_boundary != 'closed':
        return phases, 'unsupported_carbon_boundary'
    return phases, None


def _audit(*, ph_mode, ph, phase_policy, phases, carbon_boundary, state, audit_inputs):
    inputs = dict(audit_inputs or {})
    clash = sorted(_CORE_AUDIT_KEYS & set(inputs))
    if clash:
        raise DeliveryError('invalid_audit_inputs', f'audit_inputs may not override model keys: {clash}')
    data = _load()
    audit = {'temperature_reference_c': 25, 'ph_mode': ph_mode, 'ph': ph,
             'phase_policy': phase_policy, 'phases': tuple(phases),
             'carbon_boundary': carbon_boundary, 'solution_id': inputs.pop('solution_id', None),
             'chemistrySha256': _chemistry_sha256(), 'coefficientsSha256': COEFFICIENTS_SHA256,
             'equation': data['model_id'], 'speciesMappingVersion': data['species_mapping_version'],
             'conductivity_units': CONDUCTIVITY_UNITS, 'unit_conversions': [],
             'solver_iterations': state.iterations if state is not None else None,
             'charge_balance': state.charge_balance if state is not None else None,
             'model': MODEL_VERSION}
    audit.update(inputs)
    return audit


def _not_supported_unsolved(reason, *, ph_mode, ph, phase_policy, phases, carbon_boundary,
                            assay_residual_eq, audit_inputs):
    return IrrigationECResult(
        status='not_supported', ec25_ms_cm=None, known_species_subtotal_ms_cm=None,
        contributions_ms_cm={}, transport_numbers={}, missing_species=(),
        unrecorded_counterions_eq_per_kgw=None,
        assay_charge_residual={'eq_per_kgw': assay_residual_eq, 'percent': None},
        reason=reason, ph=ph, ionic_strength=None, precipitated_molal={}, warnings=(),
        audit=_audit(ph_mode=ph_mode, ph=ph, phase_policy=phase_policy, phases=phases,
                     carbon_boundary=carbon_boundary, state=None, audit_inputs=audit_inputs))


def _ec_from_state(state: AqueousResult, *, ph_mode, phase_policy, phases, assay_residual_eq,
                   audit_inputs) -> IrrigationECResult:
    """EXPERIMENTAL (M1): EC25 from an already-solved 25 C, closed-carbon state.

    The caller has validated the mode inputs (see _validate_request). Status
    order: O5 assay gate, then (supplied only) unrecorded counterions, then
    missing species coverage. Supersaturation warnings (dissolved policy) are
    reported whatever the status.
    """
    charges = _charges()
    species_map = _load()['species_map']
    strength = state.ionic_strength
    equivalents = sum(abs(charges[n]) * m for n, m in state.species.items() if charges.get(n))
    percent = 100 * assay_residual_eq / equivalents if equivalents else 0.
    contributions, missing = {}, []
    for name in sorted(state.species):
        molal, charge = state.species[name], charges.get(name, 0)
        if not charge or molal <= _REPORTING_TOLERANCE:
            continue
        if name in species_map:
            contributions[name] = ionic_molal_conductivity(species_map[name], strength) * molal
        else:
            missing.append({'name': name, 'charge': charge, 'molal': molal})
    warnings = ()
    if phase_policy == 'dissolved':
        warnings = tuple(f'{phase} supersaturated (SI {si:.3f}); no kinetic interpretation'
                         for phase, si in sorted(state.saturation_indices.items()) if si > 0)
    unrecorded = None
    if ph_mode == 'supplied':
        unrecorded = state.charge_balance - assay_residual_eq
    if abs(percent) > _ASSAY_LIMIT_PERCENT:
        status, reason = (('not_supported', 'assay_charge_residual_too_large') if ph_mode == 'calculated'
                          else ('partial', 'unrecorded_counterions'))
    elif ph_mode == 'supplied' and abs(unrecorded) > max(1e-12, 0.001 * equivalents):
        status, reason = 'partial', 'unrecorded_counterions'
    elif missing:
        status, reason = 'partial', 'missing_species_contributions'
    else:
        status, reason = 'estimated', None
    subtotal = sum(contributions.values())
    ec = subtotal if status == 'estimated' else None
    transport = {n: c / subtotal for n, c in contributions.items()} if ec else {}
    return IrrigationECResult(
        status=status, ec25_ms_cm=ec,
        known_species_subtotal_ms_cm=subtotal if status == 'partial' else None,
        contributions_ms_cm=contributions, transport_numbers=transport,
        missing_species=tuple(missing), unrecorded_counterions_eq_per_kgw=unrecorded,
        assay_charge_residual={'eq_per_kgw': assay_residual_eq, 'percent': percent},
        reason=reason, ph=state.ph, ionic_strength=strength,
        precipitated_molal={p: v for p, v in state.precipitated.items() if v > 0},
        warnings=warnings,
        audit=_audit(ph_mode=ph_mode, ph=state.ph, phase_policy=phase_policy, phases=phases,
                     carbon_boundary='closed', state=state, audit_inputs=audit_inputs))


def calculate_ec_from_totals(totals_molal: Mapping[str, float], *, solution_id: str, ph_mode: str,
                             ph: float | None = None, phase_policy: str, phases: Sequence[str] = (),
                             carbon_boundary: str = 'closed', temperature_c: float = 25.0,
                             assay_charge_residual_eq_per_kgw: float = 0.0,
                             audit_inputs: Mapping | None = None) -> IrrigationECResult:
    """EXPERIMENTAL (M1): irrigation EC25 (mS/cm) from analytical totals in mol/kgw.

    kappa25 = sum(lambda_i(25 C, I) * m_i) over charged species of one
    speciation (McCleskey 2012 Eq. 8). Returns status 'estimated', 'partial'
    or 'not_supported'; invalid input raises DeliveryError. Accuracy on
    fertilizer mixtures has not been established.
    """
    phases, reason = _validate_request(
        ph_mode=ph_mode, ph=ph, phase_policy=phase_policy, phases=phases,
        temperature_c=temperature_c, carbon_boundary=carbon_boundary,
        assay_residual_eq=assay_charge_residual_eq_per_kgw)
    inputs = {**dict(audit_inputs or {}), 'solution_id': solution_id}
    common = dict(ph_mode=ph_mode, phase_policy=phase_policy, phases=phases,
                  assay_residual_eq=assay_charge_residual_eq_per_kgw, audit_inputs=inputs)
    if reason is not None:
        return _not_supported_unsolved(reason, ph=ph, carbon_boundary=carbon_boundary, **common)
    try:
        if ph_mode == 'calculated':
            state = calculate_equilibrium_ph(totals_molal, complete_analysis=True,
                                             carbon_boundary='closed', phases=phases)
        else:
            state = solve(totals_molal, ph, phases=phases)
    except DeliveryError as error:
        if error.code != 'activity_model_out_of_range':
            raise
        return _not_supported_unsolved('ionic_strength_outside_domain', ph=ph,
                                       carbon_boundary=carbon_boundary, **common)
    return _ec_from_state(state, **common)
