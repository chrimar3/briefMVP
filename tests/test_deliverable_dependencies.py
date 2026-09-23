from copy import deepcopy

import pytest
from conftest import make_review_run

from pipeline import gates, handover, revisions


def setup_rows(tmp_path):
    run = make_review_run(tmp_path)
    brief = revisions.load(run/'brief.json')
    row = revisions.load(run/'agency_inputs.json')['deliverables'][0]
    first, second = deepcopy(row), deepcopy(row)
    first.update(id='master', dependencies=[], deadline='2026-09-20')
    second.update(id='crop', dependencies=['master'], deadline='2026-09-21')
    specs = revisions.load(gates.CONFIG_DIR/'channel_specs.json')
    return [first, second], specs, brief


def test_valid_dependencies(tmp_path):
    rows, specs, brief = setup_rows(tmp_path)
    assert not handover.validate(rows, specs, brief)


@pytest.mark.parametrize('issue', ['unknown', 'self', 'cycle', 'late', 'duplicate'])
def test_invalid_dependencies_block_handover(tmp_path, issue):
    rows, specs, brief = setup_rows(tmp_path)
    if issue == 'unknown':
        rows[1]['dependencies'] = ['missing']
    if issue == 'self':
        rows[1]['dependencies'] = ['crop']
    if issue == 'cycle':
        rows[0]['dependencies'] = ['crop']
    if issue == 'late':
        rows[0]['deadline'] = '2026-09-22'
    if issue == 'duplicate':
        rows[1]['dependencies'] = ['master', 'master']
    assert any('dependenc' in p for p in handover.validate(rows, specs, brief))
