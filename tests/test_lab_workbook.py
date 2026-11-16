# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Real XLSX transport and synthetic lab records; never experimental evidence."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'examples/steiner-10-litre-lab-worksheet.xlsx'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
SHEETS = [
    'Batch',
    'Stock assays',
    'Dispensers',
    'Calibration',
    'Observations',
    'Measurement records',
    'Preparation',
]


def write_book(path, edits):
    """Mutate only temporary test copies of the actual distributed workbook."""
    with ZipFile(TEMPLATE) as source, ZipFile(path, 'w') as dest:
        for name in source.namelist():
            data = source.read(name)
            for index, sheet in enumerate(SHEETS, 1):
                if name != f'xl/worksheets/sheet{index}.xml' or sheet not in edits:
                    continue
                root = ET.fromstring(data)
                rows = root.find(f'{{{NS}}}sheetData')
                for address, value in edits[sheet].items():
                    number = ''.join(x for x in address if x.isdigit())
                    row = next((r for r in rows if r.get('r') == number), None)
                    if row is None:
                        row = ET.SubElement(rows, f'{{{NS}}}row', r=number)
                    old = next((c for c in row if c.get('r') == address), None)
                    if old is not None:
                        row.remove(old)
                    c = ET.SubElement(row, f'{{{NS}}}c', r=address)
                    if value is None:
                        continue
                    if isinstance(value, tuple):
                        ET.SubElement(c, f'{{{NS}}}f').text = value[0]
                        ET.SubElement(c, f'{{{NS}}}v').text = str(value[1])
                    elif isinstance(value, (float, int)):
                        ET.SubElement(c, f'{{{NS}}}v').text = str(value)
                    else:
                        c.set('t', 'inlineStr')
                        ET.SubElement(ET.SubElement(c, f'{{{NS}}}is'), f'{{{NS}}}t').text = value
                data = ET.tostring(root)
            dest.writestr(name, data)


def synthetic_inputs():
    """Independent, explicitly synthetic inputs for a completed seven-day study."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    base = now - timedelta(days=8)
    epoch = datetime(1899, 12, 30, tzinfo=timezone.utc)

    def serial(dt):
        return (dt - epoch).total_seconds() / 86400

    early, late = serial(base - timedelta(days=1)), serial(now + timedelta(days=7))
    e = {s: {} for s in SHEETS}
    b = e['Batch']
    b.update({f'B{r}': 'SYNTHETIC TEST ONLY' for r in range(6, 23)})
    b.update(B8='pending', B9=serial(now), B18=0.45, B13='FAIL')
    for r in (14, 19, 20, 21, 22):
        b[f'B{r}'] = 'YES'
    for r in range(6, 12):
        for c, v in zip(
            'DEFGHIJKLMNO',
            [
                f'stock-{r}',
                f'assay-{r}',
                1 if r == 11 else 10,
                0.0005 if r == 11 else 0.005,
                25,
                int(early),
                int(late),
                'synthetic',
                'method',
                'YES',
                'YES',
                'YES',
            ],
        ):
            e['Stock assays'][f'{c}{r}'] = v
        for c, v in zip(
            'DEFGHIJKLMNOP',
            [
                f'device-{r}',
                f'disp-{r}',
                0,
                100,
                0.005,
                0.005,
                25,
                int(early),
                int(late),
                'synthetic',
                'method',
                'YES',
                'YES',
            ],
        ):
            e['Dispensers'][f'{c}{r}'] = v
        e['Preparation'][f'K{r}'] = [44.88, 36.6, 13.55, 12.4, 14.45, 24.7][r - 6]
    for r, v in enumerate(
        [
            'SYNTHETIC TEST ONLY',
            'volume-id',
            'synthetic',
            'method',
            int(early),
            int(late),
            25,
            10,
            10,
            0.01,
            'YES',
            'YES',
            'YES',
        ],
        6,
    ):
        e['Calibration'][f'B{r}'] = v
    for r, v in enumerate(
        [
            'meter',
            'electrode',
            'phcal',
            'synthetic',
            'method',
            early,
            int(late),
            25,
            6,
            7,
            0.002,
            0.003,
            'YES',
            'YES',
        ],
        26,
    ):
        e['Calibration'][f'B{r}'] = v
    e['Calibration'].update(B41='buffer4', B42='buffer7', D41=4, D42=7)
    for i, hour in enumerate((0, 24, 72, 168)):
        r = i + 6
        values = [
            f'obs-{i}',
            serial(base + timedelta(hours=hour)),
            25,
            6.3,
            0.005,
            0.2,
            0.05,
            6.211693096571703,
            0.001,
            10.215051542013006,
            0.001,
            10,
            0.001,
            f'ph-{i}',
            int(late),
            'synthetic',
            'method',
            'YES',
            'YES',
            'closed vessel',
            0,
            'synthetic analyst',
        ]
        e['Observations'].update({f'{chr(65 + j)}{r}': v for j, v in enumerate(values)})
        for j in range(4):
            mr = 6 + i * 4 + j
            for c, v in zip(
                'DEFGHJ', ['instrument', 'calibration', 'method', 'source', 'YES', 'raw report']
            ):
                e['Measurement records'][f'{c}{mr}'] = v
    return e


class LabWorkbookTests(unittest.TestCase):
    def test_import_workflow_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('flahax.lab_workbook'))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'batch.xlsx'

    def test_blank_workbook_reports_input_cell_locations(self):
        from flahax.lab_workbook import WorkbookImportError, load_lab_workbook

        with self.assertRaises(WorkbookImportError) as caught:
            load_lab_workbook(TEMPLATE)
        self.assertIn('Batch!B6', str(caught.exception))

    def test_mapping_and_stale_excel_statuses_are_not_authoritative(self):
        from flahax.lab_workbook import load_lab_workbook

        edits = synthetic_inputs()
        edits['Batch']['B32'] = 'PASS'
        write_book(self.path, edits)
        request, provenance = load_lab_workbook(self.path)
        self.assertEqual(request['stock_evidence']['assays'][0]['formula'], 'KH2PO4')
        self.assertEqual(
            request['batch_stability']['observations'][0]['ph_measurement'],
            request['stock_evidence']['batch_ph']['measurement'],
        )
        self.assertEqual(len(request['batch_stability']['observations']), 4)
        self.assertEqual(request['stock_evidence']['batch_ph']['measurement']['indicated_ph'], 6.3)
        self.assertEqual(provenance['worksheet_statuses_used'], False)
        self.assertEqual(len(provenance['sha256']), 64)

    def test_formula_inputs_missing_bounds_changed_design_and_bad_dates_rejected(self):
        from flahax.lab_workbook import WorkbookImportError, load_lab_workbook

        for sheet, address, value in [
            ('Observations', 'D6', ('6.3', 6.3)),
            ('Observations', 'I6', None),
            ('Batch', 'F13', 5),
            ('Observations', 'B6', '2026-11-01'),
            ('Stock assays', 'G6', True),
            ('Preparation', 'K6', 45),
        ]:
            edits = synthetic_inputs()
            edits[sheet][address] = value
            write_book(self.path, edits)
            with self.subTest(address=f'{sheet}!{address}'):
                with self.assertRaises(WorkbookImportError):
                    load_lab_workbook(self.path)

    def test_orphan_provenance_and_extra_observations_are_not_dropped(self):
        from flahax.lab_workbook import WorkbookImportError, load_lab_workbook

        edits = synthetic_inputs()
        edits['Measurement records']['D22'] = 'unassigned data'
        write_book(self.path, edits)
        with self.assertRaises(WorkbookImportError):
            load_lab_workbook(self.path)
        edits = synthetic_inputs()
        edits['Observations']['A18'] = 'beyond capacity'
        write_book(self.path, edits)
        with self.assertRaises(WorkbookImportError):
            load_lab_workbook(self.path)

    def test_full_verification_recomputes_numerical_and_measured_results(self):
        from flahax.lab_workbook import load_lab_workbook, verify_lab_workbook
        from flahax.batch_stability import assess_batch_stability

        edits = synthetic_inputs()
        write_book(self.path, edits)
        prepared = verify_lab_workbook(self.path, prepare=True)
        self.assertFalse(prepared['verified'])
        self.assertFalse(prepared['stable'])
        edits['Batch']['B8'] = prepared['stock_verification']['preparation_fingerprint']
        write_book(self.path, edits)
        result = verify_lab_workbook(self.path)
        self.assertTrue(result['verified'])
        self.assertTrue(result['stable'])
        self.assertEqual(result['uncertainty_verification']['status'], 'passed')
        self.assertEqual(result['stability_assessment']['qualified_duration_hours'], 168)
        edits['Observations']['F8'] = 2
        write_book(self.path, edits)
        request, _ = load_lab_workbook(self.path)
        self.assertFalse(assess_batch_stability(result, request['batch_stability'])['stable'])
        wrong = copy.deepcopy(request['stock_evidence'])
        wrong['batch_ph']['measurement']['preparation_fingerprint'] = 'wrong'
        from flahax.stock_evidence import assess_stock_evidence

        self.assertFalse(assess_stock_evidence(result, wrong)['verified'])

    def test_cli_blank_workbook_returns_structured_failure_without_traceback(self):
        proc = subprocess.run(
            [sys.executable, '-m', 'flahax', 'lab-import', str(TEMPLATE)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        result = json.loads(proc.stdout)
        self.assertFalse(result['verified'])
        self.assertFalse(result['stable'])
        self.assertEqual(result['status'], 'invalid_workbook')
        self.assertNotIn('Traceback', proc.stderr)

    def test_unsupported_archives_and_date_system_fail_closed(self):
        from flahax.lab_workbook import WorkbookImportError, load_lab_workbook

        edits = synthetic_inputs()
        write_book(self.path, edits)
        for extra in ('xl/vbaProject.bin', 'xl/externalLinks/externalLink1.xml'):
            other = self.path.with_name('unsupported.xlsx')
            with ZipFile(self.path) as source, ZipFile(other, 'w') as dest:
                for name in source.namelist():
                    dest.writestr(name, source.read(name))
                dest.writestr(extra, b'unsupported')
            with self.assertRaises(WorkbookImportError):
                load_lab_workbook(other)
        self.path.write_bytes(b'not a workbook')
        with self.assertRaises(WorkbookImportError):
            load_lab_workbook(self.path)

    def test_prepare_mode_requires_only_preparation_inputs(self):
        from flahax.lab_workbook import load_lab_workbook

        edits = synthetic_inputs()
        edits['Observations'] = {}
        edits['Measurement records'] = {}
        edits['Batch']['B8'] = None
        write_book(self.path, edits)
        request, provenance = load_lab_workbook(self.path, prepare=True)
        self.assertNotIn('batch_stability', request)
        self.assertNotIn('batch_ph', request['stock_evidence'])
        self.assertEqual(provenance['mode'], 'prepare')

    def test_changed_measurement_units_and_overflow_metadata_are_rejected(self):
        from flahax.lab_workbook import WorkbookImportError, load_lab_workbook

        for sheet, address, value in [
            ('Observations', 'I5', 'Ca bound mmol/L'),
            ('Measurement records', 'D54', 'additional instrument'),
        ]:
            edits = synthetic_inputs()
            edits[sheet][address] = value
            write_book(self.path, edits)
            with self.assertRaises(WorkbookImportError):
                load_lab_workbook(self.path)

    def test_failed_preparation_does_not_exit_successfully(self):
        from flahax.lab_workbook import main
        from unittest.mock import patch

        edits = synthetic_inputs()
        write_book(self.path, edits)
        report = dict(
            verified=False,
            stable=False,
            uncertainty_verification={'status': 'passed'},
            stock_verification={'failures': [{'code': 'stock_record_check_failed'}]},
        )
        with patch('flahax.lab_workbook.verify_lab_workbook', return_value=report):
            code = main(
                [str(self.path), '--prepare', '--output', str(self.path.with_suffix('.json'))]
            )
        self.assertEqual(code, 1)
