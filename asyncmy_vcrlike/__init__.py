# SPDX-FileCopyrightText: 2024 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Pytest plugin provided by asyncmy_vcrlike."""

import asyncio
import io
import pathlib
import types
import typing

import _pytest
import asyncmy  # type: ignore[import-untyped]
import pytest
import ruamel.yaml
from asyncmy.cursors import Cursor  # type: ignore[import-untyped]

from asyncmy_vcrlike import _aio_fileutils_builtin as aiofileutils

Arg = typing.Any
Args = tuple[Arg, ...] | list[Arg] | dict[str, Arg] | None
Row = typing.Any
ConnCoro = typing.Callable[
    ...,
    typing.Coroutine[typing.Any, typing.Any, typing.Any],
]
PoolFunc = typing.Callable[..., typing.Any]


class _Request(typing.TypedDict):
    query: str
    args: Args


_Response = list[tuple[typing.Any, ...]]


async def _record(
    vcr_path: pathlib.Path,
    request: _Request,
    response: _Response | None,
) -> None:
    with io.StringIO() as sio:
        yaml = ruamel.yaml.YAML(typ='safe')
        yaml.dump([{'request': request, 'response': response}], sio)

        await aiofileutils.makedirs(vcr_path.parent, exist_ok=True)
        await aiofileutils.write_file(
            vcr_path.with_suffix('.tmp'),
            'a',
            sio.getvalue(),
        )


class _LimitedCursor:
    async def executemany(self, query: str, args: Args) -> None:
        raise NotImplementedError

    async def fetchmany(self, size: int | None = None) -> tuple[Row, ...]:
        raise NotImplementedError

    async def fetchone(self) -> Row | None:
        raise NotImplementedError

    async def __aiter__(self) -> typing.AsyncIterator[Row]:
        raise NotImplementedError
        yield

    async def callproc(self, procname: str, args: Args = ()) -> Args:
        raise NotImplementedError


def _recording_versions(
    vcr_path: pathlib.Path,
) -> tuple[type, type, type, ConnCoro, PoolFunc]:
    orig_connect = asyncmy.connect
    orig_create_pool = asyncmy.create_pool

    class RecordingCursor(Cursor, _LimitedCursor):  # type: ignore[misc]
        """Recording version of Cursor."""

        async def execute(self, query: str, args: Args = None) -> None:
            """Execute a query or command to the database (recording)."""
            await super().execute(query, args)
            results = await self.fetchall()
            request: _Request = {'query': query, 'args': args}
            await _record(vcr_path, request, results)
            if self._rows is not None:
                self.scroll(0, mode='absolute')
            # not returning ret that the original execute returns

    class RecordingConnection(asyncmy.Connection):  # type: ignore[misc]
        """Recording version of Connection that provides RecordingCursor."""

        @typing.no_type_check
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            kwargs['cursor_cls'] = RecordingCursor
            super().__init__(*args, **kwargs)

    class RecordingPool(asyncmy.Pool):  # type: ignore[misc]
        """Recording version of Pool that uses RecordingCursor."""

        @typing.no_type_check
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            kwargs['cursor_cls'] = RecordingCursor
            super().__init__(*args, **kwargs)

    @typing.no_type_check
    async def recording_connect(**kwa) -> typing.Any:  # noqa: ANN003, ANN401
        kwa['cursor_cls'] = RecordingCursor
        return orig_connect(**kwa)

    @typing.no_type_check
    def recording_create_pool(**kwa) -> typing.Any:  # noqa: ANN003, ANN401
        kwa['cursor_cls'] = RecordingCursor
        return orig_create_pool(**kwa)

    return (
        RecordingCursor,
        RecordingConnection,
        RecordingPool,
        recording_connect,
        recording_create_pool,
    )


def _replaying_stub_versions(  # noqa: C901
    vcr_path: pathlib.Path,
) -> tuple[type, type, type, ConnCoro, PoolFunc]:
    orig_connect = asyncmy.connect

    class ReplayingStubCursor(_LimitedCursor):
        """Replaying stub of Cursor."""

        @typing.no_type_check
        def __init__(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        async def _load_recording(self) -> None:
            if not hasattr(self, '_recording'):
                recording = await aiofileutils.read_file(vcr_path, 'r')
                yaml = ruamel.yaml.YAML(typ='safe')
                self._recording = list(yaml.load(recording))

        async def execute(self, query: str, args: Args = None) -> None:
            try:
                await self._load_recording()
            except (GeneratorExit, asyncio.CancelledError):
                return

            request = {
                'query': query,
                'args': list(args) if args is not None else None,
            }
            for i, r in enumerate(self._recording):
                if request == r['request']:
                    self._recording.pop(i)
                    self._response = r['response']
                    break
            else:
                msg = 'no matching response in recording'
                raise RuntimeError(msg)
            # not returning ret that the original execute returns

        def _assert_response(self) -> None:
            if not hasattr(self, '_recording'):
                msg = 'no loaded recording, execute a cached response'
                raise RuntimeError(msg)
            if not hasattr(self, '_response'):
                msg = 'no loaded response, execute a cached response'
                raise RuntimeError(msg)

        async def fetchall(self) -> tuple[Row, ...]:
            self._assert_response()
            r = tuple(tuple(row) for row in self._response)
            self._response.clear()
            return r

        async def fetchone(self) -> Row | None:
            self._assert_response()
            if self._response:
                return tuple(self._response.pop(0))
            return None

        async def close(self) -> None:
            pass

        async def __aenter__(self: typing.Self) -> typing.Self:
            return self

        async def __aexit__(
            self: typing.Self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: types.TracebackType | None,
        ) -> bool | None:
            return None

    class ReplayingStubConnection:
        """Replaying stub of Connection."""

        @typing.no_type_check
        @classmethod
        async def connect(
            cls,
            *a,  # noqa: ANN002, ARG003
            **kwa,  # noqa: ANN003, ARG003
        ) -> typing.Self:
            return cls()

        @typing.no_type_check
        async def close(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        @typing.no_type_check
        async def execute(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            curr = self.cursor()
            return curr.execute(*a, **kwa)

        @typing.no_type_check
        def cursor(  # noqa: PLR6301
            self,
            *a,  # noqa: ARG002, ANN002
            **kwa,  # noqa: ARG002, ANN003
        ) -> None:
            return ReplayingStubCursor()

        @typing.no_type_check
        async def commit(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self: typing.Self) -> typing.Self:
            return self

        async def __aexit__(
            self: typing.Self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: types.TracebackType | None,
        ) -> bool | None:
            return None

    @typing.no_type_check
    class ReplayingStubPool:
        """Replaying stub of Pool."""

        @typing.no_type_check
        def __init__(
            self,
            minsize: int = 1,
            maxsize: int = 10,
            pool_recycle: int = 3600,
            echo: bool = False,  # noqa: FBT001, FBT002
            **kwargs,  # noqa: ANN003
        ) -> typing.Self:
            pass

        @typing.no_type_check
        def close(self) -> None:
            pass

        @typing.no_type_check
        def terminate(self) -> None:
            pass

        @typing.no_type_check
        async def wait_closed(self) -> None:
            pass

        @typing.no_type_check
        def acquire(self):  # noqa: ANN202
            async def coro() -> ReplayingStubConnection:
                return ReplayingStubConnection()

            return asyncmy.contexts._PoolAcquireContextManager(  # noqa: SLF001
                coro(),
                self,
            )

        @typing.no_type_check
        def release(self, conn) -> None:  # noqa: ANN001, ARG002, PLR6301
            async def coro() -> None:
                pass

            return coro()

        async def __aenter__(self: typing.Self) -> typing.Self:
            return self

        async def __aexit__(
            self: typing.Self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: types.TracebackType | None,
        ) -> bool | None:
            return None

    @typing.no_type_check
    async def replaying_connect(**kwa) -> typing.Any:  # noqa: ANN003, ANN401
        kwa['cursor_cls'] = ReplayingStubCursor
        return orig_connect(**kwa)

    @typing.no_type_check
    def replaying_create_pool(**kwa) -> typing.Any:  # noqa: ANN003, ANN401
        kwa['cursor_cls'] = ReplayingStubCursor

        async def cp() -> ReplayingStubPool:
            return ReplayingStubPool(**kwa)

        return asyncmy.contexts._PoolContextManager(cp())  # noqa: SLF001

    return (
        ReplayingStubCursor,
        ReplayingStubConnection,
        ReplayingStubPool,
        replaying_connect,
        replaying_create_pool,
    )


# We're gonna extend pytest-recording
# with this fixture that replaces asyncmy internals
# with either recording or playback versions
# depending on the mode and presence of cassettes
@pytest.fixture(autouse=True)
def _asyncmy_vcrlike(
    request: _pytest.fixtures.SubRequest,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> typing.Iterator[None]:
    """Caches/replays asyncio asyncmy SQL access for vcr-decorated tests."""
    vcr_path = pathlib.Path(
        vcr_cassette_dir,
        default_cassette_name + '.asyncmy.yml',
    )
    under_vcr = list(request.node.iter_markers(name='vcr'))
    rewrite = record_mode == 'rewrite'
    vcr_path_exists = pathlib.Path(vcr_path).exists()

    original_versions = (
        asyncmy.cursors.Cursor,
        asyncmy.Connection,
        asyncmy.Pool,
        asyncmy.connect,
        asyncmy.create_pool,
    )

    @typing.no_type_check
    def replace(cu, co, pl, ct, cp) -> None:  # noqa: ANN001
        asyncmy.cursors.Cursor = cu
        asyncmy.Connection = co
        asyncmy.pool = pl
        asyncmy.connect = ct
        asyncmy.create_pool = cp

    if not under_vcr:
        yield  # don't record anything, don't stub out anything
    elif rewrite or not vcr_path_exists:
        # record queries and results
        replace(*_recording_versions(vcr_path))
        outfile = vcr_path.with_suffix('.tmp')
        outfile.unlink(missing_ok=True)
        yield  # record
        if outfile.exists():
            outfile.rename(vcr_path)
    else:
        # replay queries and results
        _orig_co = asyncmy.Connection
        _orig_cp = asyncmy.Pool
        replace(*_replaying_stub_versions(vcr_path))

        yield  # replay

    replace(*original_versions)


__all__: list[str] = []
