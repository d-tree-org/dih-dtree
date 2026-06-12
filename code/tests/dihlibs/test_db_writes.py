"""Write-path tests for dihlibs.db.DB.

Covers the contract that exec() COMMITS and surfaces RETURNING rows, and that
the insert()/upsert() helpers build correct SQL and round-trip. Regression
guard for the dihlibs 0.0.98 footgun where a write sent through query() was
silently rolled back on connection close (the row vanished while the sequence
advanced -> downstream 'row N not found').

Uses a throwaway file-based SQLite database so the suite needs no external
service. SQLite (3.35+) supports both RETURNING and ON CONFLICT ... DO UPDATE,
which is all these helpers rely on; a file (not :memory:) is used so the
separate connections opened by exec()/query() see each other's committed data.
"""
import os
import tempfile

import pytest

from dihlibs.db import DB


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = DB(connection_url=f"sqlite:///{path}")
    database.exec("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, hits INTEGER)")
    yield database
    os.remove(path)


def test_exec_commits_plain_insert(db):
    # rowcount back, and the row is visible from query() -- a SEPARATE
    # connection -- which only holds if exec() committed rather than rolled back.
    assert db.exec(
        "INSERT INTO t (id, name) VALUES (:id, :name)", {"id": 1, "name": "a"}
    ) == 1
    assert db.query("SELECT name FROM t WHERE id = :id", {"id": 1}) == [{"name": "a"}]


def test_exec_returns_returning_rows(db):
    rows = db.exec("INSERT INTO t (name) VALUES (:name) RETURNING id", {"name": "x"})
    assert rows == [{"id": 1}]


def test_exec_supports_bracket_placeholders(db):
    # _bind still rewrites the [name] placeholder style for exec().
    assert db.exec("INSERT INTO t (id, name) VALUES ([id], [name])",
                   {"id": 7, "name": "b"}) == 1
    assert db.query("SELECT name FROM t WHERE id = [id]", {"id": 7}) == [{"name": "b"}]


def test_insert_helper_returns_id(db):
    assert db.insert("t", {"name": "y"}, returning="id") == [{"id": 1}]


def test_insert_helper_without_returning_gives_rowcount(db):
    assert db.insert("t", {"id": 5, "name": "z"}) == 1
    assert db.query("SELECT name FROM t WHERE id = :id", {"id": 5}) == [{"name": "z"}]


def test_upsert_inserts_then_updates_on_conflict(db):
    db.upsert("t", {"id": 1, "name": "a", "hits": 1}, conflict="id")
    db.upsert("t", {"id": 1, "name": "b", "hits": 2}, conflict="id",
              update=["name", "hits"])
    assert db.query("SELECT name, hits FROM t WHERE id = :id", {"id": 1}) == [
        {"name": "b", "hits": 2}
    ]


def test_upsert_default_update_covers_non_conflict_columns(db):
    db.upsert("t", {"id": 1, "name": "a", "hits": 1}, conflict="id")
    db.upsert("t", {"id": 1, "name": "c", "hits": 9}, conflict="id")
    assert db.query("SELECT name, hits FROM t WHERE id = :id", {"id": 1}) == [
        {"name": "c", "hits": 9}
    ]


def test_upsert_do_nothing_leaves_existing_row(db):
    db.insert("t", {"id": 1, "name": "a", "hits": 1})
    db.upsert("t", {"id": 1, "name": "b", "hits": 2}, conflict="id", update=[])
    assert db.query("SELECT name, hits FROM t WHERE id = :id", {"id": 1}) == [
        {"name": "a", "hits": 1}
    ]


def test_upsert_returning(db):
    row = db.upsert("t", {"id": 1, "name": "a", "hits": 1}, conflict="id",
                    returning="id")
    assert row == [{"id": 1}]
