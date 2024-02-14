# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of asyncmy_vcrlike."""

import asyncmy  # type: ignore[import-untyped]


async def test_mysql(async_mysql: asyncmy.Connection) -> None:
    """Run test."""
    async with async_mysql.cursor() as cur:
        await cur.execute('CREATE TABLE pet (name VARCHAR(20));')
