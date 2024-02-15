# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of asyncmy_vcrlike."""

import pathlib

import asyncmy  # type: ignore[import-untyped]
import asyncmy.cursors  # type: ignore[import-untyped]
import pytest


@pytest.mark.vcr()  # that's it, that's everything needed
async def test_fetchall() -> None:
    """Test .fetchall recording/replaying."""
    pass


@pytest.mark.vcr()
async def test_fetchone() -> None:
    """Test .fetchone recording/replaying."""
    pass


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
