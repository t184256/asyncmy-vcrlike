# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Provide an async_mysql fixture."""

import getpass
import typing

import MySQLdb  # type: ignore[import-untyped]
import pytest
import pytest_mysql  # type: ignore[import-untyped]
import pytest_mysql.config  # type: ignore[import-untyped]
import pytest_mysql.exceptions  # type: ignore[import-untyped]
import pytest_mysql.factories  # type: ignore[import-untyped]
from _pytest.fixtures import FixtureRequest
from MySQLdb import Connection, ProgrammingError

PROCESS_T: typing.TypeAlias = (
    pytest_mysql.executor.MySQLExecutor
    | pytest_mysql.executor_noop.NoopMySQLExecutor
)


mysql_my_proc = pytest_mysql.factories.mysql_proc(
    port=None,
    user=getpass.getuser(),
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

    def _connect(
        connect_kwargs: dict[str, typing.Any],
        query_str: str,
        mysql_db: str,
    ) -> MySQLdb.Connection:
        """Apply given query to a  given MySQLdb connection."""
        mysql_conn: MySQLdb.Connection = Connection(**connect_kwargs)
        try:
            mysql_conn.query(query_str)
        except ProgrammingError as e:
            if 'database exists' in str(e):
                msg = f'Database {mysql_db} already exists.'
                raise pytest_mysql.exceptions.DatabaseExists(msg) from e
            raise
        return mysql_conn

    @pytest.fixture()
    def mysql_fixture(
        request: FixtureRequest,
    ) -> typing.Generator[MySQLdb.Connection, None, None]:
        """Client fixture for MySQL server.

        #. Get config.
        #. Try to import MySQLdb package.
        #. Connect to mysql server.
        #. Create database.
        #. Use proper database.
        #. Drop database after tests.

        :param request: fixture request object

        :returns: connection to database
        """
        config = pytest_mysql.config.get_config(request)
        process: PROCESS_T = request.getfixturevalue(process_fixture_name)
        if not process.running():
            process.start()

        mysql_user = process.user
        mysql_passwd = passwd or config['passwd']
        mysql_db = dbname or config['dbname']

        connection_kwargs: dict[str, str | int] = {
            'host': process.host,
            'user': mysql_user,
            'passwd': mysql_passwd,
        }
        if process.unixsocket:
            connection_kwargs['unix_socket'] = process.unixsocket
        else:
            connection_kwargs['port'] = process.port

        query_str = (
            f'CREATE DATABASE `{mysql_db}` '
            f'DEFAULT CHARACTER SET {charset} '
            f'DEFAULT COLLATE {collation}'
        )
        mysql_conn: MySQLdb.Connection = _connect(
            connection_kwargs,
            query_str,
            mysql_db,
        )
        mysql_conn.query(f'USE `{mysql_db}`')
        yield mysql_conn

        # clean up after test that forgot to fetch selected data
        if not mysql_conn.open:
            mysql_conn = Connection(**connection_kwargs)
        mysql_conn.store_result()
        mysql_conn.query(f'DROP DATABASE IF EXISTS `{mysql_db}`')
        mysql_conn.close()

    return mysql_fixture


async_mysql = _async_mysql('mysql_my_proc', dbname='my')
