# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Read the fixed Steiner laboratory XLSX without executing Excel or its formulas."""

import argparse
import hashlib
import io
import json
import math
import posixpath
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
FORMULAS = ('KH2PO4', 'Ca(NO3)2.4H2O', 'MgSO4.7H2O', 'Mg(NO3)2.6H2O', 'KNO3', 'KOH')
DOSES = (44.88, 36.60, 13.55, 12.40, 14.45, 24.70)
SETTINGS = (
    10,
    0.05,
    25,
    6.28,
    6.32,
    0.001,
    0.02,
    1,
    0.95,
    0.05,
    1,
    62.11693096571703,
    102.15051542013006,
    1.70947360992432,
    0.3,
)
SHEETS = (
    'Batch',
    'Stock assays',
    'Dispensers',
    'Calibration',
    'Observations',
    'Measurement records',
    'Preparation',
)
BOUND = 'total_bound_through_valid_until'


class WorkbookImportError(ValueError):
    """An unsupported layout or incomplete/unsafe input cannot become evidence."""

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__('; '.join(self.issues))


def _xml(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise WorkbookImportError(['XML declarations with entities are not supported'])
    return ET.fromstring(data)


class _Book:
    def __init__(self, path):
        self.issues = []
        self.cells = {}
        path = Path(path)
        if path.stat().st_size > 10_000_000:
            raise WorkbookImportError(['Workbook exceeds the 10 MB file limit'])
        raw = path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        try:
            with ZipFile(io.BytesIO(raw)) as z:
                info = z.infolist()
                names = z.namelist()
                if (
                    len(info) > 256
                    or len(set(names)) != len(names)
                    or sum(i.file_size for i in info) > 40_000_000
                ):
                    raise WorkbookImportError(['Workbook ZIP size or duplicate member limit'])
                if any(
                    'vbaproject' in n.lower() or n.startswith('xl/externalLinks/') for n in names
                ):
                    raise WorkbookImportError(
                        ['Macro and external-link workbooks are unsupported']
                    )
                book = _xml(z.read('xl/workbook.xml'))
                properties = book.find(f'{NS}workbookPr')
                if properties is not None and properties.get('date1904') in ('1', 'true'):
                    raise WorkbookImportError(['Use the template 1900 Excel date system'])
                shared = []
                if 'xl/sharedStrings.xml' in names:
                    shared = [''.join(s.itertext()) for s in _xml(z.read('xl/sharedStrings.xml'))]
                relationships = _xml(z.read('xl/_rels/workbook.xml.rels'))
                targets = {}
                for item in relationships:
                    if item.get('TargetMode') == 'External':
                        raise WorkbookImportError(['External workbook relationships unsupported'])
                    target = item.get('Target', '')
                    targets[item.get('Id')] = posixpath.normpath(
                        target.lstrip('/') if target.startswith('/') else 'xl/' + target
                    )
                for sheet in book.find(f'{NS}sheets'):
                    name = sheet.get('name')
                    if name in self.cells:
                        raise WorkbookImportError(['Duplicate worksheet name'])
                    target = targets[sheet.get(REL)]
                    if not target.startswith('xl/worksheets/'):
                        raise WorkbookImportError(['Unsupported worksheet relationship'])
                    root = _xml(z.read(target))
                    cells = {}
                    for c in root.findall(f'.//{NS}sheetData/{NS}row/{NS}c'):
                        address = c.get('r')
                        if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}', address or ''):
                            raise WorkbookImportError(['Malformed cell address'])
                        if address in cells:
                            raise WorkbookImportError([f'{name}!{address}: duplicate cell'])
                        v = c.find(f'{NS}v')
                        value = None if v is None else v.text
                        kind = c.get('t', 'n')
                        if kind == 'inlineStr':
                            value = ''.join(c.find(f'{NS}is').itertext())
                        elif value is not None and kind == 's':
                            value = shared[int(value)]
                        elif value is not None and kind == 'n':
                            value = float(value)
                        elif kind == 'b':
                            value = value == '1'
                        elif kind == 'e':
                            value = ('error', value)
                        cells[address] = (value, c.find(f'{NS}f') is not None)
                    self.cells[name] = cells
        except (
            BadZipFile,
            ET.ParseError,
            KeyError,
            IndexError,
            ValueError,
            AttributeError,
        ) as exc:
            if isinstance(exc, WorkbookImportError):
                raise
            raise WorkbookImportError([f'Invalid XLSX structure: {exc}']) from exc
        if set(self.cells) != set(SHEETS):
            raise WorkbookImportError(['Use the seven-sheet Steiner laboratory workbook template'])

    def raw(self, sheet, address):
        return self.cells[sheet].get(address, (None, False))

    def read(self, sheet, address, kind='text'):
        value, formula = self.raw(sheet, address)
        reason = None
        if formula:
            reason = 'input must be a recorded value, not an Excel formula'
        elif value is None or value == '':
            reason = 'required input is blank'
        elif kind == 'number' and (type(value) not in (int, float) or not math.isfinite(value)):
            reason = 'a finite numeric cell is required'
        elif kind == 'text' and (not isinstance(value, str) or not value.strip()):
            reason = 'a nonempty text cell is required'
        elif kind == 'yes' and value != 'YES':
            reason = 'supported YES declaration is required'
        if reason:
            self.issues.append(f'{sheet}!{address}: {reason}')
            return None
        return value.strip() if isinstance(value, str) else value

    def date(self, sheet, address, timestamp=False):
        value = self.read(sheet, address, 'number')
        if value is None:
            return None
        try:
            # Modern dates only: reject Excel's fictitious 1900-02-29 and date strings.
            if value < 61 or value > 2_958_465 or (not timestamp and value != int(value)):
                raise ValueError('date outside supported range or date-only field contains time')
            result = datetime(1899, 12, 30, tzinfo=timezone.utc) + timedelta(
                seconds=round(value * 86400, 3)
            )
            return (
                result.isoformat(timespec='milliseconds')
                if timestamp
                else result.date().isoformat()
            )
        except (ValueError, OverflowError) as exc:
            self.issues.append(f'{sheet}!{address}: {exc}')
            return None

    def expected(self, sheet, address, expected):
        kind = 'number' if isinstance(expected, (int, float)) else 'text'
        value = self.read(sheet, address, kind)
        same = value == expected
        if kind == 'number' and value is not None:
            same = math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12)
        if value is not None and not same:
            self.issues.append(
                f'{sheet}!{address}: template/design changed; expected {expected!r}'
            )

    def finish(self):
        if self.issues:
            raise WorkbookImportError(self.issues)


def _design(book):
    header_rows = {
        'Stock assays': [
            'Formula',
            'Nominal g/L',
            'Planned mL',
            'Stock ID',
            'Assay record ID',
            'Measured g/L',
            'Bound g/L',
            'Temperature °C',
            'Measured UTC date',
            'Valid through UTC date',
            'Source report',
            'Method',
            'Compound basis confirmed?',
            'Reactive impurities excluded?',
            'Total bound through expiry?',
        ],
        'Dispensers': [
            'Formula',
            'Stock ID',
            'Planned mL',
            'Dispenser ID',
            'Calibration ID',
            'Dose minimum mL',
            'Dose maximum mL',
            'Absolute bias mL',
            'Additional bound mL',
            'Temperature °C',
            'Measured UTC date',
            'Valid through UTC date',
            'Source report',
            'Method',
            'Whole range confirmed?',
            'Total bound through expiry?',
        ],
        'Observations': [
            'Observation ID',
            'Sample timestamp UTC',
            'Temperature °C',
            'Indicated pH',
            'Additional pH bound',
            'Turbidity NTU',
            'Turbidity bound NTU',
            'Dissolved Ca mg/L',
            'Ca bound mg/L',
            'Dissolved P mg/L',
            'P bound mg/L',
            'Remaining volume L',
            'Volume bound L',
            'pH record ID',
            'pH valid through UTC',
            'pH report',
            'pH method',
            'pH total-bound confirmed?',
            'No unaccounted additions?',
            'Sample handling / storage notes',
            'Withdrawal L',
            'Sampler / analyst',
        ],
        'Measurement records': [
            'Slot',
            'Metric',
            'Observation ID',
            'Instrument ID',
            'Calibration reference',
            'Method',
            'Source report',
            'Total bounded error?',
            'Record result',
            'Raw data / preservation reference',
        ],
    }
    for sheet, labels in header_rows.items():
        for index, label in enumerate(labels):
            book.expected(sheet, f'{chr(65 + index)}5', label)
    for first, labels in [
        (
            6,
            [
                'Vessel ID',
                'Calibration record ID',
                'Source report',
                'Method',
                'Measured UTC date',
                'Valid through UTC date',
                'Temperature °C',
                'Nominal contained L',
                'Measured contained L',
                'Absolute bound L',
                'To contain confirmed?',
                'Final solution includes stocks?',
                'Total bound through expiry?',
            ],
        ),
        (
            26,
            [
                'Meter ID',
                'Electrode ID',
                'Calibration record ID',
                'Source report',
                'Method',
                'Calibrated timestamp (UTC)',
                'Valid through UTC date',
                'Temperature °C',
                'Covered pH minimum',
                'Covered pH maximum',
                'Maximum residual absolute bias',
                'Calibration absolute bound',
                'Whole range confirmed?',
                'Total bound through expiry?',
            ],
        ),
    ]:
        for r, label in enumerate(labels, first):
            book.expected('Calibration', f'A{r}', label)
    anchors = {
        'Batch': {
            'A6': 'Batch ID',
            'A8': 'Preparation fingerprint',
            'E6': 'Final volume (L)',
            'E19': 'Requested strength (mmol/L)',
        },
        'Stock assays': {'A5': 'Formula', 'F5': 'Measured g/L', 'G5': 'Bound g/L'},
        'Dispensers': {'D5': 'Dispenser ID', 'H5': 'Absolute bias mL'},
        'Calibration': {
            'A6': 'Vessel ID',
            'A26': 'Meter ID',
            'A36': 'Maximum residual absolute bias',
        },
        'Observations': {
            'A5': 'Observation ID',
            'B5': 'Sample timestamp UTC',
            'H5': 'Dissolved Ca mg/L',
            'J5': 'Dissolved P mg/L',
        },
        'Measurement records': {'D5': 'Instrument ID', 'H5': 'Total bounded error?'},
        'Preparation': {'K5': 'Actual delivered mL'},
    }
    for sheet, labels in anchors.items():
        for address, label in labels.items():
            book.expected(sheet, address, label)
    for row, value in enumerate(SETTINGS, 6):
        book.expected('Batch', f'F{row}', value)
    for row, formula in enumerate(FORMULAS, 6):
        for sheet in ('Stock assays', 'Dispensers', 'Preparation'):
            book.expected(sheet, f'A{row}', formula)
        book.expected('Stock assays', f'B{row}', 1 if formula == 'KOH' else 10)
        for sheet in ('Stock assays', 'Dispensers'):
            book.expected(sheet, f'C{row}', DOSES[row - 6])


def _request():
    return dict(
        cation_shares=[50, 30, 20],
        anion_shares=[5, 3, 1],
        ph=6.3,
        counted_mmol_l=SETTINGS[13],
        volume_litres=10,
        water='demineralized',
        water_mass_kg=10,
        ph_range=[6.28, 6.32],
        selected_phases=['Brushite', 'Monetite', 'Hydroxyapatite'],
        mass_decimals=5,
        saturation_margin=0.3,
        uncertainty=dict(
            volume_error_litres=0.05,
            ratio_relative_tolerance=0.01,
            concentration_relative_tolerance=0.02,
            impurity_model='inert',
        ),
        stock_dosing=dict(
            concentrations_g_l={f: 1 if f == 'KOH' else 10 for f in FORMULAS},
            concentration_relative_error=0.001,
            dose_error_ml=0.02,
            dose_decimals=2,
        ),
    )


def _stocks(book):
    evidence = dict(assignments={}, assays=[], calibrations=[])
    for r, formula in enumerate(FORMULAS, 6):

        def a(column, kind='text'):
            return book.read('Stock assays', f'{column}{r}', kind)

        def d(column, kind='text'):
            return book.read('Dispensers', f'{column}{r}', kind)

        for column in ('M', 'N', 'O'):
            a(column, 'yes')
        for column in ('O', 'P'):
            d(column, 'yes')
        stock, assay_id = a('D'), a('E')
        device, cal_id = d('D'), d('E')
        evidence['assignments'][formula] = dict(
            stock_id=stock,
            dispenser_id=device,
            assay_record_id=assay_id,
            calibration_record_id=cal_id,
        )
        evidence['assays'].append(
            dict(
                record_id=assay_id,
                stock_id=stock,
                formula=formula,
                measured_concentration_g_l=a('F', 'number'),
                absolute_uncertainty_g_l=a('G', 'number'),
                temperature_c=a('H', 'number'),
                measured_on=book.date('Stock assays', f'I{r}'),
                valid_until=book.date('Stock assays', f'J{r}'),
                source=a('K'),
                method=a('L'),
                uncertainty_basis=BOUND,
                concentration_basis='specified_compound_equivalent_g_l',
                reactive_impurities='excluded_by_measurement',
            )
        )
        evidence['calibrations'].append(
            dict(
                record_id=cal_id,
                stock_id=stock,
                dispenser_id=device,
                dose_min_ml=d('F', 'number'),
                dose_max_ml=d('G', 'number'),
                maximum_absolute_bias_ml=d('H', 'number'),
                absolute_uncertainty_ml=d('I', 'number'),
                temperature_c=d('J', 'number'),
                measured_on=book.date('Dispensers', f'K{r}'),
                valid_until=book.date('Dispensers', f'L{r}'),
                source=d('M'),
                method=d('N'),
                uncertainty_basis=BOUND,
                coverage='entire_declared_range',
            )
        )
    return evidence


def _volume(book):
    def v(row, kind='text'):
        return book.read('Calibration', f'B{row}', kind)

    for r in (16, 17, 18):
        v(r, 'yes')
    vessel, record = v(6), v(7)
    return dict(
        assignment=dict(vessel_id=vessel, calibration_record_id=record),
        calibration=dict(
            record_id=record,
            vessel_id=vessel,
            source=v(8),
            method=v(9),
            measured_on=book.date('Calibration', 'B10'),
            valid_until=book.date('Calibration', 'B11'),
            temperature_c=v(12, 'number'),
            nominal_volume_litres=v(13, 'number'),
            measured_volume_litres=v(14, 'number'),
            absolute_uncertainty_litres=v(15, 'number'),
            uncertainty_basis=BOUND,
            capacity_basis='to_contain',
            application='final_solution_including_stocks',
        ),
    )


def _ph_calibration(book):
    def p(row, kind='text'):
        return book.read('Calibration', f'B{row}', kind)

    for r in (38, 39):
        p(r, 'yes')
    time = book.date('Calibration', 'B31', timestamp=True)
    return dict(
        record_id=p(28),
        meter_id=p(26),
        electrode_id=p(27),
        source=p(29),
        method=p(30),
        calibrated_at=time,
        measured_on=time[:10] if time else None,
        valid_until=book.date('Calibration', 'B32'),
        temperature_c=p(33, 'number'),
        ph_min=p(34, 'number'),
        ph_max=p(35, 'number'),
        maximum_absolute_bias_ph=p(36, 'number'),
        absolute_uncertainty_ph=p(37, 'number'),
        uncertainty_basis=BOUND,
        coverage='entire_declared_range',
        buffers=[
            dict(reference=p(r), certified_ph=book.read('Calibration', f'D{r}', 'number'))
            for r in (41, 42)
        ],
    )


def _observations(book, identity, calibration):
    observations, supplementary = [], []
    metric_keys = (
        'turbidity_ntu',
        'dissolved_calcium_mg_l',
        'dissolved_phosphorus_mg_l',
        'volume_litres',
    )
    metric_labels = ('Turbidity', 'Dissolved Ca', 'Dissolved P', 'Remaining volume')
    for address, (value, has_formula) in book.cells['Measurement records'].items():
        column, row = re.fullmatch(r'([A-Z]+)([0-9]+)', address).groups()
        if int(row) >= 54 and column in ('D', 'E', 'F', 'G', 'H', 'J'):
            if has_formula or value not in (None, ''):
                book.issues.append(f'Measurement records!{address}: beyond 12 supported slots')
    # Reject additional recorded samples outside the template capacity, rather than omit them.
    for address, (value, has_formula) in book.cells['Observations'].items():
        column, row = re.fullmatch(r'([A-Z]+)([0-9]+)', address).groups()
        if (
            int(row) >= 18
            and len(column) == 1
            and column <= 'V'
            and (has_formula or value not in (None, ''))
        ):
            if address not in ('A20', 'A22'):
                book.issues.append(
                    f'Observations!{address}: data outside 12 supported sample slots'
                )
    for r in range(6, 18):
        first = 6 + (r - 6) * 4
        used = any(
            book.raw('Observations', f'{chr(c)}{r}') != (None, False)
            and book.raw('Observations', f'{chr(c)}{r}')[0] != ''
            for c in range(65, 87)
        )
        metadata_used = any(
            book.raw('Measurement records', f'{c}{mr}')[0] not in (None, '')
            or book.raw('Measurement records', f'{c}{mr}')[1]
            for mr in range(first, first + 4)
            for c in 'DEFGHJ'
        )
        if not used and not metadata_used:
            continue

        def o(c, kind='text'):
            return book.read('Observations', f'{c}{r}', kind)

        o('R', 'yes')
        o('S', 'yes')
        time = book.date('Observations', f'B{r}', timestamp=True)
        ph = dict(
            record_id=o('N'),
            source=o('P'),
            method=o('Q'),
            measured_at=time,
            measured_on=time[:10] if time else None,
            valid_until=book.date('Observations', f'O{r}'),
            temperature_c=o('C', 'number'),
            indicated_ph=o('D', 'number'),
            additional_uncertainty_ph=o('E', 'number'),
            **identity,
            meter_id=calibration['meter_id'],
            electrode_id=calibration['electrode_id'],
            calibration_record_id=calibration['record_id'],
            uncertainty_basis=BOUND,
            application='final_mixed_batch_no_unaccounted_additions',
        )
        row = dict(observation_id=o('A'), sampled_at=time, ph_measurement=ph)
        notes = dict(
            observation_id=row['observation_id'],
            handling=o('T'),
            withdrawn_litres=o('U', 'number'),
            analyst=o('V'),
            raw_reports=[],
        )
        if notes['withdrawn_litres'] is not None and notes['withdrawn_litres'] < 0:
            book.issues.append(f'Observations!U{r}: withdrawn volume cannot be negative')
        for j, key in enumerate(metric_keys):
            mr = first + j
            book.expected('Measurement records', f'A{mr}', r - 5)
            book.expected('Measurement records', f'B{mr}', metric_labels[j])

            def m(c, kind='text'):
                return book.read('Measurement records', f'{c}{mr}', kind)

            m('H', 'yes')
            row[key] = dict(
                value=o(chr(70 + 2 * j), 'number'),
                absolute_uncertainty=o(chr(71 + 2 * j), 'number'),
                instrument_id=m('D'),
                calibration_reference=m('E'),
                method=m('F'),
                source=m('G'),
                uncertainty_basis='total_bounded_error',
            )
            notes['raw_reports'].append(m('J'))
        observations.append(row)
        supplementary.append(notes)
    if not observations:
        book.issues.append('Observations!A6: at least a baseline observation is required')
    return observations, supplementary


def load_lab_workbook(path, *, prepare=False):
    """Map literal workbook inputs to existing strict evidence schemas plus provenance.

    Prepare mode imports stock and vessel records only, to obtain the fingerprint
    before making the batch. Full mode requires actual records; Excel statuses and
    cached formulas are never accepted as evidence or verification results.
    """
    book = _Book(path)
    _design(book)
    batch, vessel = book.read('Batch', 'B6'), book.read('Batch', 'B7')
    evidence = _stocks(book)
    evidence['final_volume'] = _volume(book)
    if vessel != evidence['final_volume']['assignment']['vessel_id']:
        book.issues.append('Calibration!B6: vessel must match Batch!B7')
    request = _request()
    request['stock_evidence'] = evidence
    provenance = dict(
        schema='steiner-10l-lab-workbook-v1',
        sha256=book.sha256,
        filename=Path(path).name,
        mode='prepare' if prepare else 'verify',
        worksheet_statuses_used=False,
        assessment_time_utc=datetime.now(timezone.utc).isoformat(),
        scope='Fixed six-stock template only. Source reports are not independently authenticated.',
    )
    if not prepare:
        identity = dict(
            batch_id=batch, vessel_id=vessel, preparation_fingerprint=book.read('Batch', 'B8')
        )
        provenance.update(
            operator=book.read('Batch', 'B10'),
            reviewer=book.read('Batch', 'B11'),
            worksheet_assessment_utc=book.date('Batch', 'B9', timestamp=True),
        )
        for r in (14, 19, 20, 21, 22):
            book.read('Batch', f'B{r}', 'yes')
        # Actual recorded deliveries must be the specified rounded instructions.
        # Different readings require explicit replanning, not silent dose substitution.
        for r, dose in enumerate(DOSES, 6):
            book.expected('Preparation', f'K{r}', dose)
        provenance['recorded_delivery_ml'] = dict(zip(FORMULAS, DOSES))
        provenance['preparation_notes'] = {
            address: value
            for address, (value, formula) in book.cells['Preparation'].items()
            if not formula and value not in (None, '')
        }
        calibration = _ph_calibration(book)
        observations, notes = _observations(book, identity, calibration)
        provenance['observation_notes'] = notes
        if observations:
            initial = observations[0]['ph_measurement']
            evidence['batch_ph'] = dict(
                assignment=dict(
                    batch_id=batch,
                    vessel_id=vessel,
                    meter_id=calibration['meter_id'],
                    electrode_id=calibration['electrode_id'],
                    calibration_record_id=calibration['record_id'],
                    measurement_record_id=initial['record_id'],
                ),
                calibration=calibration,
                measurement=initial,
            )
        request['batch_stability'] = dict(
            assignment=identity,
            policy=dict(
                required_hours=[0, 24, 72, 168],
                maximum_delay_hours=1,
                maximum_turbidity_ntu=1,
                minimum_retention_fraction=0.95,
                initial_nutrient_relative_tolerance=0.05,
            ),
            protocol=dict(
                protocol_id=book.read('Batch', 'B16'),
                source=book.read('Batch', 'B17'),
                storage_conditions=book.read('Batch', 'B15'),
                filter_pore_um=book.read('Batch', 'B18', 'number'),
                dissolved_basis='filtered_elemental_Ca_and_total_dissolved_P',
                turbidity_sample='representative_unfiltered_batch',
                material_accounting='no_additions_withdrawals_count_as_loss',
            ),
            observations=observations,
        )
    book.finish()
    return request, provenance


def verify_lab_workbook(path, *, prepare=False):
    """Recompute chemistry, preparation verification and observed stability from XLSX."""
    from .planning_cli import execute

    request, provenance = load_lab_workbook(path, prepare=prepare)
    result = execute('ratio', request)
    result['workbook_import'] = provenance
    return result


def main(argv=None):
    """Import the supported lab workbook and emit the complete verification report."""
    parser = argparse.ArgumentParser(prog='flahax lab-import')
    parser.add_argument('workbook', type=Path, help='completed Steiner laboratory .xlsx')
    parser.add_argument(
        '--prepare',
        action='store_true',
        help='check stock/vessel records and obtain the pre-batch fingerprint',
    )
    parser.add_argument('--output', type=Path, help='write the report here instead of stdout')
    args = parser.parse_args(argv)
    if args.output and args.output.resolve() == args.workbook.resolve():
        parser.error('output must not overwrite the source workbook')
    try:
        result = verify_lab_workbook(args.workbook, prepare=args.prepare)
        # A parsed workbook is not necessarily a verified or stable physical batch.
        if args.prepare:
            ready = result['uncertainty_verification']['status'] == 'passed' and all(
                f['code'] == 'missing_batch_ph_evidence'
                for f in result['stock_verification']['failures']
            )
        else:
            ready = result['verified'] and result['stable']
        code = 0 if ready else 1
    except (WorkbookImportError, OSError, ValueError) as exc:
        result = dict(
            status='invalid_workbook',
            verified=False,
            stable=False,
            issues=exc.issues if isinstance(exc, WorkbookImportError) else [str(exc)],
        )
        code = 2
    from .planning_cli import serializable

    text = json.dumps(serializable(result), allow_nan=False, indent=2) + '\n'
    if args.output:
        try:
            args.output.write_text(text, encoding='utf-8')
        except OSError as exc:
            print(f'Cannot write laboratory report: {exc}', file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return code
