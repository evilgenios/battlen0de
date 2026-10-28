"""Static checks on the migration scripts themselves — no database needed.

test_revision_ids_fit_in_the_alembic_version_column exists because
0002_fix_email_unique_index initially failed against a real database with
`StringDataRightTruncation: value too long for type character varying(32)`
— alembic's own bookkeeping table (`alembic_version.version_num`) is
VARCHAR(32) by default, and a revision id longer than that fails at the
very last statement of an otherwise-successful migration. It's transactional
DDL, so that specific failure rolled back cleanly with no partial state —
but there's no reason to rely on that safety net when it's a five-second
check to prevent the mistake entirely.
"""

from __future__ import annotations

import ast
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'

# alembic_version.version_num's default column width (see
# alembic.runtime.migration.MigrationContext / the CREATE TABLE emitted for
# alembic_version in migrations/versions/0001_initial_schema.py's own
# --sql output).
ALEMBIC_VERSION_COLUMN_WIDTH = 32


def _migration_files():
    return sorted(p for p in VERSIONS_DIR.glob('*.py') if p.name != '__init__.py')


def _module_level_assignments(tree: ast.Module) -> dict:
    """Maps top-level names to their literal values, handling both plain
    (`x = ...`) and annotated (`x: str = ...`) assignments — alembic's
    revision.py.mako template generates annotated ones
    (`revision: str = ...`), which a plain `ast.Assign`-only walk misses
    entirely."""
    values = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            values[node.target.id] = ast.literal_eval(node.value)
    return values


def _revision_id(path: Path) -> str:
    values = _module_level_assignments(ast.parse(path.read_text(encoding='utf-8')))
    if 'revision' not in values:
        raise AssertionError(f'{path}: no module-level `revision = ...` assignment found')
    return values['revision']


def test_at_least_one_migration_exists():
    assert _migration_files(), 'expected at least migrations/versions/0001_initial_schema.py'


def test_revision_ids_fit_in_the_alembic_version_column():
    for path in _migration_files():
        revision_id = _revision_id(path)
        assert len(revision_id) <= ALEMBIC_VERSION_COLUMN_WIDTH, (
            f'{path.name}: revision id {revision_id!r} is {len(revision_id)} characters, '
            f'longer than alembic_version.version_num\'s {ALEMBIC_VERSION_COLUMN_WIDTH}-character column — '
            'this migration will fail at its final UPDATE statement even if every DDL '
            'operation in it succeeds. Shorten the revision id (and the filename, by '
            'convention).'
        )


def test_revision_chain_is_linear_and_starts_from_none():
    """Every `down_revision` points at a real revision id in this
    directory, exactly one migration has down_revision=None (the root),
    and there are no branches/forks — this whole codebase assumes one
    linear history."""
    revisions = {}
    for path in _migration_files():
        values = _module_level_assignments(ast.parse(path.read_text(encoding='utf-8')))
        assert 'revision' in values, path
        assert 'down_revision' in values, path
        revisions[values['revision']] = values['down_revision']

    roots = [rev for rev, down in revisions.items() if down is None]
    assert len(roots) == 1, f'expected exactly one root migration, found: {roots}'

    for rev, down in revisions.items():
        if down is not None:
            assert down in revisions, f'{rev}: down_revision {down!r} does not match any revision id on disk'

    # No two migrations may share the same down_revision (that would be a fork).
    down_revisions = [d for d in revisions.values() if d is not None]
    assert len(down_revisions) == len(set(down_revisions)), 'multiple migrations share a down_revision (a fork)'
