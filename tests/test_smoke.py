# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of asyncmy_vcrlike."""

import pathlib

import asyncmy  # type: ignore[import-untyped]
import asyncmy.cursors  # type: ignore[import-untyped]
import pytest


@pytest.mark.vcr()  # that's it, that's everything needed
async def test_fetchall(async_mysql: asyncmy.Pool) -> None:
    """Test .fetchall recording/replaying."""
    async with async_mysql.acquire() as conn, conn.cursor() as cur:
        await cur.execute('CREATE TABLE t (i int, s varchar(50))')
        await cur.execute('INSERT INTO t VALUES (%s, %s)', (2, 'b'))
        await cur.execute('INSERT INTO t VALUES (%s, %s)', (1, 'a'))
        await cur.execute('SELECT * FROM t ORDER BY i ASC')
        assert await cur.fetchall() == ((1, 'a'), (2, 'b'))

    _assert_cassette(cur, 'test_fetchall')


@pytest.mark.vcr()
async def test_fetchone(async_mysql: asyncmy.Pool) -> None:
    """Test .fetchone recording/replaying."""
    async with async_mysql.acquire() as conn, conn.cursor() as cur:
        await cur.execute('CREATE TABLE o (i int, s varchar(50))')
        await cur.execute('INSERT INTO o VALUES (%s, %s)', (2, 'b'))
        await cur.execute('INSERT INTO o VALUES (%s, %s)', (1, 'a'))
        await cur.execute('SELECT * FROM o ORDER BY i ASC')
        assert await cur.fetchone() == (1, 'a')
        assert await cur.fetchone() == (2, 'b')
        assert await cur.fetchone() is None

    _assert_cassette(cur, 'test_fetchone')


def _assert_cassette(
    cur: asyncmy.cursors.Cursor,
    test_name: str,
) -> None:
    assert cur.__class__ is asyncmy.cursors.Cursor
    assert cur.__class__.__name__ in {
        'RecordingCursor',
        'ReplayingStubCursor',
    }
    recording = cur.__class__.__name__ == 'RecordingCursor'
    p = pathlib.Path(
        'tests',
        'cassettes',
        'test_smoke',
        f'{test_name}.asyncmy.{"tmp" if recording else "yml"}',
    )
    assert p.exists()
