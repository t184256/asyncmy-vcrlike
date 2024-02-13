# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of asyncmy_vcrlike."""

import MySQLdb.connections  # type: ignore[import-untyped]


def test_mysql(async_mysql: MySQLdb.connections.Connection) -> None:
    """Run test."""
    cur = async_mysql.cursor()
    cur.execute('CREATE TABLE pet (name VARCHAR(20), owner VARCHAR(20));')
    async_mysql.commit()
    cur.close()
