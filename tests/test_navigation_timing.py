"""Isolated ASGI/SQLite behavior tests: no main import or operational DB."""
import asyncio
import time

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from headend.services.navigation_timing import NavigationTimingMiddleware


def run_request(app, headers=(), path='/api/test'):
    async def run():
        messages = []
        async def send(message): messages.append(message)
        async def receive(): return {'type': 'http.request', 'body': b'', 'more_body': False}
        await app({'type': 'http', 'path': path, 'headers': list(headers)}, receive, send)
        return messages
    return asyncio.run(run())


def test_disabled_or_unmarked_requests_unchanged():
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 403, 'headers': [(b'x-existing', b'kept')]})
        await send({'type': 'http.response.body', 'body': b'denied'})
    engine = create_engine('sqlite://')
    for enabled, headers in [(False, [(b'x-tlp-diagnostics', b'1')]), (True, [])]:
        result = run_request(NavigationTimingMiddleware(app, engine, enabled), headers)
        assert result[0]['headers'] == [(b'x-existing', b'kept')]
        assert result[1]['body'] == b'denied'


def test_sql_in_worker_and_response_unchanged(caplog):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    async def app(scope, receive, send):
        def query():
            with engine.connect() as conn: conn.execute(text("SELECT 'secret-not-logged'"))
        await asyncio.to_thread(query)
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'cache-control', b'private')]})
        await send({'type': 'http.response.body', 'body': b'unchanged'})
    with caplog.at_level('INFO'):
        result = run_request(NavigationTimingMiddleware(app, engine, True), [(b'x-tlp-diagnostics', b'1')])
    header = dict(result[0]['headers'])[b'server-timing'].decode()
    assert 'sql_count;dur=1' in header and 'trace;desc=' in header
    assert dict(result[0]['headers'])[b'cache-control'] == b'private'
    assert result[1]['body'] == b'unchanged'
    assert 'secret-not-logged' not in caplog.text and '/api/test' not in caplog.text


def test_loop_block_and_denial_are_measured_without_bypassing_auth():
    async def app(scope, receive, send):
        time.sleep(.12)
        await send({'type': 'http.response.start', 'status': 401, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'unauthorized'})
    result = run_request(NavigationTimingMiddleware(app, create_engine('sqlite://'), True), [(b'x-tlp-diagnostics', b'1')])
    header = dict(result[0]['headers'])[b'server-timing'].decode()
    lag = float(header.split('loop_lag;dur=')[1].split(',')[0])
    assert lag >= 50
    assert result[0]['status'] == 401 and result[1]['body'] == b'unauthorized'


def test_concurrent_requests_have_separate_sql_counts_and_cleanup():
    async def scenario():
        engine = create_engine('sqlite://')
        gate = asyncio.Event()
        async def app(scope, receive, send):
            if scope['path'] == '/api/query':
                with engine.connect() as conn: conn.execute(text('SELECT 1'))
                gate.set()
                await asyncio.sleep(.01)
            else:
                await gate.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        wrapped = NavigationTimingMiddleware(app, engine, True)
        async def call(path):
            messages = []
            async def send(msg): messages.append(msg)
            await wrapped({'type': 'http', 'path': path, 'headers': [(b'x-tlp-diagnostics', b'1')]}, None, send)
            return dict(messages[0]['headers'])[b'server-timing']
        query, other = await asyncio.gather(call('/api/query'), call('/api/other'))
        assert b'sql_count;dur=1' in query
        assert b'sql_count;dur=0' in other
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(scenario())


def test_exception_propagates_and_request_context_is_reset():
    from headend.services.navigation_timing import _current
    async def scenario():
        async def fail(scope, receive, send):
            raise RuntimeError('expected failure')
        wrapped = NavigationTimingMiddleware(fail, create_engine('sqlite://'), True)
        try:
            await wrapped({'type': 'http', 'path': '/api/test', 'headers': [(b'x-tlp-diagnostics', b'1')]}, None, None)
        except RuntimeError as error:
            assert str(error) == 'expected failure'
        else:
            raise AssertionError('middleware swallowed exception')
        assert _current.get() is None
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(scenario())
