# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Provide an async_mysql fixture."""

import getpass
import typing

import asyncmy  # type: ignore[import-untyped]
import pytest
import pytest_mysql  # type: ignore[import-untyped]
import pytest_mysql.config  # type: ignore[import-untyped]
import pytest_mysql.exceptions  # type: ignore[import-untyped]
import pytest_mysql.factories  # type: ignore[import-untyped]
from _pytest.fixtures import FixtureRequest

PROCESS_T: typing.TypeAlias = (
    pytest_mysql.executor.MySQLExecutor
    | pytest_mysql.executor_noop.NoopMySQLExecutor
)


pytest_plugins = 'asyncmy_vcrlike'  # test my own plugin


def _async_mysql(
    process_fixture_name: str,
    passwd: str | None = None,
    dbname: str | None = None,
    charset: str = 'utf8',
    collation: str = 'utf8_general_ci',
) -> typing.Callable[[FixtureRequest], typing.Any]:
    """Client fixture factory for MySQL server. Async."""

    @pytest.fixture()
    async def mysql_fixture(
        request: FixtureRequest,
    ) -> typing.AsyncGenerator[asyncmy.Pool, None]:
        config = pytest_mysql.config.get_config(request)
        mysql_db = dbname or config['dbname']

        # sync
        process: PROCESS_T = request.getfixturevalue(process_fixture_name)
        if not process.running():
            process.start()

        assert process.unixsocket
        connection_kwargs: dict[str, str | int] = {
            'host': process.host,
            'unix_socket': process.unixsocket,
            'user': process.user,
            'password': passwd or config['passwd'],
        }
        pool = await asyncmy.create_pool(**connection_kwargs)

        query_str = (
            f'CREATE DATABASE `{mysql_db}` '
            f'DEFAULT CHARACTER SET {charset} '
            f'DEFAULT COLLATE {collation}'
        )
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f'DROP DATABASE IF EXISTS `{mysql_db}`')
            await cur.execute(query_str)
            await cur.execute(f'USE `{mysql_db}`')

        try:
            yield pool
        finally:
            async with pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute(f'DROP DATABASE IF EXISTS `{mysql_db}`')
            pool.close()
            await pool.wait_closed()

    return mysql_fixture


mysql_my_proc = pytest_mysql.factories.mysql_proc(
    port=None,
    user=getpass.getuser(),
)

async_mysql = _async_mysql('mysql_my_proc', dbname='my')
