#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Validate an external implementation ledger without treating reproduction as repair.

The ledger stays outside versioned product sources. This tool never changes task state,
contacts GitHub, or executes evidence commands. Evidence files are checked by SHA-256.
"""

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import re

STATES = {'planned', 'ready', 'reproducing', 'implementing', 'validating', 'review', 'complete'}
KINDS = {'foundation', 'reproduction', 'fix', 'acceptance', 'physical'}
ACTIVE = {'reproducing', 'implementing', 'validating', 'review', 'complete'}


def dependencies(task):
    return [part.strip() for part in task['depends_on'].split(',') if part.strip()]


def ancestors(task_id, tasks):
    result = set()
    pending = list(dependencies(tasks[task_id]))
    while pending:
        item = pending.pop()
        if item not in result and item in tasks:
            result.add(item)
            pending.extend(dependencies(tasks[item]))
    return result


def evidence_errors(record, root, label):
    errors = []
    if not isinstance(record, dict):
        return [f'{label}: missing evidence record']
    for field in ('path', 'sha256', 'command', 'source_revision', 'environment'):
        if not record.get(field):
            errors.append(f'{label}: missing {field}')
    if type(record.get('exit_code')) is not int:
        errors.append(f'{label}: missing integer exit_code')
    path = root / record.get('path', '')
    if not path.is_file():
        errors.append(f'{label}: evidence file missing')
    elif hashlib.sha256(path.read_bytes()).hexdigest() != record.get('sha256'):
        errors.append(f'{label}: evidence hash mismatch')
    return errors


def validate(ledger, root):
    """Return contract errors; an empty list means valid state, not engine acceptance."""
    try:
        return _validate(ledger, root)
    except (KeyError, TypeError, AttributeError, OSError, ValueError) as error:
        return [f'invalid ledger or unreadable evidence: {error}']


def _validate(ledger, root):
    errors = []
    rows = ledger.get('tasks', [])
    tasks = {row['id']: row for row in rows}
    if not rows or len(tasks) != len(rows):
        errors.append('task IDs must be nonempty and unique')
    if ledger.get('schema_version') != 2:
        errors.append('unsupported ledger schema')
    policy = ledger.get('policy', {})
    gate = policy.get('issue_gate')
    final = policy.get('acceptance_task')
    reproduction = policy.get('reproduction_task')
    if not policy.get('required_assignee'):
        errors.append('required issue assignee missing from policy')
    for key in (gate, final, reproduction):
        if key not in tasks:
            errors.append(f'missing policy task: {key}')
    if errors:
        return errors
    if tasks[final].get('kind') != 'acceptance':
        errors.append('acceptance task has wrong kind')
    if tasks[reproduction].get('kind') != 'reproduction':
        errors.append('reproduction task has wrong kind')
    for task_id, task in tasks.items():
        deps = dependencies(task)
        closure = ancestors(task_id, tasks)
        status = task.get('status')
        kind = task.get('kind')
        if status not in STATES or kind not in KINDS:
            errors.append(f'{task_id}: invalid status or kind')
        if len(deps) != len(set(deps)) or any(dep not in tasks for dep in deps):
            errors.append(f'{task_id}: duplicate or unknown dependency')
        if task_id in closure:
            errors.append(f'{task_id}: dependency cycle')
        if kind != 'physical' and any(tasks[dep].get('kind') == 'physical' for dep in closure):
            errors.append(f'{task_id}: mathematical work depends on physical work')
        if kind in {'fix', 'acceptance'} and gate not in closure:
            errors.append(f'{task_id}: issue gate missing from dependencies')
        if status in ACTIVE:
            for dep in deps:
                if dep in tasks and tasks[dep].get('status') != 'complete':
                    errors.append(f'{task_id}: prerequisite {dep} incomplete')
        if kind == 'fix' and status in ACTIVE:
            issue = task.get('issue', {})
            if not re.fullmatch(
                r'https://github.com/[^/]+/[^/]+/issues/[1-9][0-9]*', issue.get('url', '')
            ):
                errors.append(f'{task_id}: issue URL missing or invalid')
            if issue.get('assignee') != policy.get('required_assignee') or not issue.get('labels'):
                errors.append(f'{task_id}: issue ownership/labels missing')
            if not issue.get('verified_at') or issue.get('state') != 'OPEN':
                errors.append(f'{task_id}: issue metadata not verified open')
            errors.extend(evidence_errors(issue.get('evidence'), root, f'{task_id} issue'))
        if status == 'complete':
            completion = task.get('completion', {})
            for field in ('documentation', 'review', 'implementation_revision'):
                if not completion.get(field):
                    errors.append(f'{task_id}: completion {field} missing')
            errors.extend(evidence_errors(completion.get('evidence'), root, task_id))
            if kind != 'reproduction' and task.get('test_outcome') != 'passed':
                errors.append(f'{task_id}: completion requires passing tests')
            if kind != 'reproduction' and completion.get('evidence', {}).get('exit_code') != 0:
                errors.append(f'{task_id}: completion evidence failed')
    controls = ledger.get('controls', [])
    if len({c.get('id') for c in controls}) != len(controls):
        errors.append('duplicate control ID')
    reproduced = tasks[reproduction].get('status') == 'complete'
    if reproduced and (
        not controls or tasks[reproduction].get('test_outcome') != 'reproduction_verified'
    ):
        errors.append('reproduction completion requires verified controls')
    required = set(ledger.get('required_controls', []))
    if not required or required != {c.get('id') for c in controls}:
        errors.append('required control inventory mismatch')
    for control in controls:
        name = control.get('id')
        owner = control.get('fix_task')
        if owner not in tasks or tasks[owner].get('kind') != 'fix':
            errors.append(f'{name}: invalid fix owner')
            continue
        fixed = tasks[owner].get('status') == 'complete'
        if reproduced or fixed:
            if not re.fullmatch('[0-9a-f]{64}', control.get('input_sha256', '')):
                errors.append(f'{name}: frozen input hash missing')
            input_path = root / control.get('input_path', '')
            if not input_path.is_file():
                errors.append(f'{name}: frozen input file missing')
            elif hashlib.sha256(input_path.read_bytes()).hexdigest() != control['input_sha256']:
                errors.append(f'{name}: frozen input file changed')
            for role in ('oracle', 'baseline'):
                errors.extend(evidence_errors(control.get(role), root, f'{name} {role}'))
            oracle = control.get('oracle', {})
            baseline = control.get('baseline', {})
            if oracle.get('exit_code') != 0 or not oracle.get('independent_method'):
                errors.append(f'{name}: independent oracle not validated')
            if baseline.get('exit_code') != 1 or baseline.get('failure_kind') != 'assertion':
                errors.append(f'{name}: baseline must show assertion failure, not setup error')
            if baseline.get('input_sha256') != control.get('input_sha256'):
                errors.append(f'{name}: baseline input identity mismatch')
            if not control.get('test_id') or baseline.get('test_id') != control.get('test_id'):
                errors.append(f'{name}: baseline assertion identity mismatch')
        if fixed:
            result = control.get('fix', {})
            errors.extend(evidence_errors(result, root, f'{name} fix'))
            if result.get('exit_code') != 0 or result.get('input_sha256') != control.get(
                'input_sha256'
            ):
                errors.append(f'{name}: fix did not pass unchanged control')
            revision = tasks[owner].get('completion', {}).get('implementation_revision')
            if result.get('source_revision') != revision:
                errors.append(f'{name}: fix evidence revision mismatch')
            if result.get('oracle_sha256') != control.get('oracle', {}).get('sha256'):
                errors.append(f'{name}: fix oracle identity mismatch')
            if result.get('test_id') != control.get('test_id'):
                errors.append(f'{name}: fix assertion identity mismatch')
        elif control.get('status') == 'resolved':
            errors.append(f'{name}: cannot resolve before fix owner completes')
    if tasks[final].get('status') == 'complete':
        for task_id, task in tasks.items():
            if task.get('kind') != 'physical' and task.get('status') != 'complete':
                errors.append(f'{final}: mathematical task {task_id} incomplete')
        if any(control.get('status') != 'resolved' for control in controls):
            errors.append(f'{final}: unresolved regression controls')
    return errors


def render_csv(ledger):
    stream = io.StringIO(newline='')
    fields = ledger['summary_fields']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n', extrasaction='ignore')
    writer.writeheader()
    writer.writerows(ledger['tasks'])
    return stream.getvalue()


def render_rows(ledger):
    rows = []
    for task in ledger['tasks']:
        values = [
            task['id'],
            task['depends_on'] or '-',
            task['findings'],
            task['action'],
            task['exit_evidence'],
        ]
        rows.append('| ' + ' | '.join(values) + ' |')
    return '\n'.join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--write-summaries', action='store_true')
    parser.add_argument('--check-ready', help='Validate prerequisites before starting this task')
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding='utf-8'))
    if args.check_ready:
        if args.write_summaries:
            parser.error('--check-ready cannot write summaries')
        ledger = copy.deepcopy(ledger)
        selected = next((t for t in ledger['tasks'] if t['id'] == args.check_ready), None)
        if selected is None:
            parser.error('unknown task requested')
        if selected['status'] == 'complete':
            parser.error('task already complete; cannot restart without invalidating evidence')
        selected['status'] = 'implementing'
    errors = validate(ledger, args.ledger.parent)
    if not errors:
        outputs = []
        if args.csv:
            outputs.append((args.csv, render_csv(ledger)))
        if args.plan:
            text = args.plan.read_text(encoding='utf-8')
            pattern = r'(?m)^\| P00 \|[^\n]*(?:\n\| P\d+ \|[^\n]*)*'
            replacement, count = re.subn(pattern, lambda _: render_rows(ledger), text)
            if count != 1:
                errors.append('plan must contain exactly one action matrix')
            else:
                outputs.append((args.plan, replacement))
        if not errors:
            for path, content in outputs:
                if args.write_summaries:
                    path.write_text(content, encoding='utf-8', newline='\n')
                elif path.read_text(encoding='utf-8') != content:
                    errors.append(f'derived summary drift: {path}')
    print(json.dumps({'valid': not errors, 'errors': errors}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
