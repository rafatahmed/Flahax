# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Workbook transport rejects unsafe archives and malformed recorded
inputs.
"""

import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from flahax.lab_workbook import WorkbookImportError, load_lab_workbook, main
from tests.test_lab_workbook import NS, ROOT, TEMPLATE, synthetic_inputs, write_book


class WorkbookValidationBoundaryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'input.xlsx'

    def rewrite(self, member, transform):
        with ZipFile(TEMPLATE) as source, ZipFile(self.path, 'w') as dest:
            for name in source.namelist():
                data = source.read(name)
                dest.writestr(name, transform(data) if name == member else data)

    def test_archive_size_and_member_limits(self):
        with self.path.open('wb') as stream:
            stream.seek(10_000_000)
            stream.write(b'x')
        with self.assertRaisesRegex(WorkbookImportError, '10 MB'):
            load_lab_workbook(self.path)
        with ZipFile(self.path, 'w') as book:
            for index in range(257):
                book.writestr(str(index), b'')
        with self.assertRaisesRegex(WorkbookImportError, 'ZIP size'):
            load_lab_workbook(self.path)

    def test_xml_entities_external_targets_and_unsupported_date_system(self):
        def properties(raw):
            root = ET.fromstring(raw)
            item = root.find(f'{{{NS}}}workbookPr')
            if item is None:
                item = ET.SubElement(root, f'{{{NS}}}workbookPr')
            item.set('date1904', 'true')
            return ET.tostring(root)

        def external(raw):
            root = ET.fromstring(raw)
            root[0].set('TargetMode', 'External')
            return ET.tostring(root)

        def wrong_target(raw):
            root = ET.fromstring(raw)
            for item in root:
                item.set('Target', '../outside.xml')
            return ET.tostring(root)

        for member, transform, reason in (
            ('xl/workbook.xml', lambda raw: b'<!DOCTYPE x>' + raw, 'entities'),
            ('xl/workbook.xml', properties, '1900 Excel'),
            ('xl/_rels/workbook.xml.rels', external, 'External workbook'),
            ('xl/_rels/workbook.xml.rels', wrong_target, 'worksheet relationship'),
        ):
            self.rewrite(member, transform)
            with self.subTest(reason=reason), self.assertRaisesRegex(WorkbookImportError, reason):
                load_lab_workbook(self.path)

    def test_duplicate_sheets_missing_sheets_and_malformed_cells(self):
        for change, reason in (
            ('duplicate_sheet', 'Duplicate worksheet'),
            ('missing_sheet', 'seven-sheet'),
            ('bad_address', 'Malformed cell'),
            ('duplicate_cell', 'duplicate cell'),
        ):

            def transform(raw):
                root = ET.fromstring(raw)
                if change.endswith('sheet'):
                    sheets = root.find(f'{{{NS}}}sheets')
                    if change == 'duplicate_sheet':
                        sheets.append(copy.deepcopy(sheets[0]))
                    else:
                        sheets.remove(sheets[-1])
                else:
                    row = root.find(f'.//{{{NS}}}sheetData/{{{NS}}}row')
                    cell = row.find(f'{{{NS}}}c')
                    if change == 'bad_address':
                        cell.set('r', 'A0')
                    else:
                        row.append(copy.deepcopy(cell))
                return ET.tostring(root)

            member = 'xl/workbook.xml' if change.endswith('sheet') else 'xl/worksheets/sheet1.xml'
            self.rewrite(member, transform)
            with self.subTest(change=change), self.assertRaisesRegex(WorkbookImportError, reason):
                load_lab_workbook(self.path)

    def test_literal_cell_types_and_dates_are_validated(self):
        for sheet, address, value in (
            ('Batch', 'B6', 10),
            ('Batch', 'B14', 'NO'),
            ('Batch', 'B9', 60),
            ('Stock assays', 'I6', 46000.5),
            ('Observations', 'U6', -1),
            ('Calibration', 'B6', 'another vessel'),
        ):
            edits = synthetic_inputs()
            edits[sheet][address] = value
            write_book(self.path, edits)
            with self.subTest(address=address), self.assertRaises(WorkbookImportError):
                load_lab_workbook(self.path)

    def test_shared_boolean_and_error_cells_are_not_treated_as_measured_numbers(self):
        # Genuine OOXML cell types, rather than Python values coerced by
        # a spreadsheet library.
        for kind, value in (('b', '1'), ('e', '#VALUE!'), ('s', '0')):
            write_book(self.path, synthetic_inputs())
            with ZipFile(self.path) as source:
                members = {name: source.read(name) for name in source.namelist()}
            root = ET.fromstring(members['xl/worksheets/sheet1.xml'])
            cell = root.find(f'.//{{{NS}}}c[@r="B9"]')
            cell.clear()
            cell.set('r', 'B9')
            cell.set('t', kind)
            ET.SubElement(cell, f'{{{NS}}}v').text = value
            members['xl/worksheets/sheet1.xml'] = ET.tostring(root)
            members['xl/sharedStrings.xml'] = (
                f'<sst xmlns="{NS}"><si><t>not a numeric date</t></si></sst>'.encode()
            )
            with ZipFile(self.path, 'w') as dest:
                for name, data in members.items():
                    dest.writestr(name, data)
            with self.subTest(kind=kind), self.assertRaises(WorkbookImportError):
                load_lab_workbook(self.path)

    def test_cli_preserves_input_and_reports_unwritable_output(self):
        write_book(self.path, synthetic_inputs())
        original = self.path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main([str(self.path), '--output', str(self.path)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.path.read_bytes(), original)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main([str(TEMPLATE), '--output', str(self.path.parent)])
        self.assertEqual(code, 2)
        self.assertIn('Cannot write laboratory report', stderr.getvalue())

    def test_inline_only_workbook_preserves_literal_inputs(self):
        write_book(self.path, synthetic_inputs())
        with ZipFile(self.path) as source:
            members = {name: source.read(name) for name in source.namelist()}
        shared = [
            ''.join(item.itertext()) for item in ET.fromstring(members.pop('xl/sharedStrings.xml'))
        ]
        for name, raw in list(members.items()):
            if not name.startswith('xl/worksheets/') or not name.endswith('.xml'):
                continue
            root = ET.fromstring(raw)
            for cell in root.findall(f'.//{{{NS}}}c[@t="s"]'):
                value = cell.find(f'{{{NS}}}v')
                text = shared[int(value.text)]
                cell.remove(value)
                cell.set('t', 'inlineStr')
                ET.SubElement(ET.SubElement(cell, f'{{{NS}}}is'), f'{{{NS}}}t').text = text
            members[name] = ET.tostring(root)
        with ZipFile(self.path, 'w') as dest:
            for name, raw in members.items():
                dest.writestr(name, raw)
        request, _ = load_lab_workbook(self.path)
        self.assertEqual(request['stock_evidence']['batch_ph']['measurement']['indicated_ph'], 6.3)

    def test_full_cli_rejects_records_without_matching_preparation_fingerprint(self):
        import json

        write_book(self.path, synthetic_inputs())
        output = self.path.with_suffix('.json')
        self.assertEqual(main([str(self.path), '--output', str(output)]), 1)
        report = json.loads(output.read_text())
        self.assertFalse(report['verified'])
        self.assertFalse(report['stable'])
        self.assertEqual(report['uncertainty_verification']['status'], 'passed')
