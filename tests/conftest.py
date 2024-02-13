# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Provide an async_mysql fixture."""

import getpass

import pytest_mysql  # type: ignore[import-untyped]
import pytest_mysql.factories  # type: ignore[import-untyped]

mysql_my_proc = pytest_mysql.factories.mysql_proc(
    port=None,
    user=getpass.getuser(),
)
async_mysql = pytest_mysql.factories.mysql('mysql_my_proc', dbname='my')
