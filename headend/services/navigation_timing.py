"""Opt-in request timings; no SQL text, URL, user identity or request bodies logged."""
import asyncio
import contextvars
import logging
import os
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import event

log = logging.getLogger(__name__)


@dataclass
class Timing:
    sql_ms: float = 0.0
    sql_count: int = 0
    loop_lag_ms: float = 0.0


_current = contextvars.ContextVar('navigation_timing', default=None)


def _before_execute(conn, cursor, statement, parameters, context, executemany):
    if _current.get() is not None:
        context._navigation_started = time.perf_counter()


def _after_execute(conn, cursor, statement, parameters, context, executemany):
    timing = _current.get()
    started = getattr(context, '_navigation_started', None)
    if timing is not None and started is not None:
        timing.sql_ms += (time.perf_counter() - started) * 1000
        timing.sql_count += 1


class NavigationTimingMiddleware:
    """ASGI pass-through. Enable at deployment with TIMELAPSE_NAV_DIAGNOSTICS=1.

    Diagnosed requests also need X-TLP-Diagnostics: 1. SQL measures successful
    cursor execution only, not connection checkout, result fetch or ORM mapping.
    app ends at response headers. loop_lag is sampled during this request only.
    """
    def __init__(self, app, engine, enabled=None):
        self.app = app
        self.enabled = os.getenv('TIMELAPSE_NAV_DIAGNOSTICS') == '1' if enabled is None else enabled
        if self.enabled and not event.contains(engine, 'before_cursor_execute', _before_execute):
            event.listen(engine, 'before_cursor_execute', _before_execute)
            event.listen(engine, 'after_cursor_execute', _after_execute)

    async def __call__(self, scope, receive, send):
        if (not self.enabled or scope['type'] != 'http'
                or not scope.get('path', '').startswith('/api/')
                or (b'x-tlp-diagnostics', b'1') not in scope.get('headers', [])):
            return await self.app(scope, receive, send)
        timing = Timing()
        token = _current.set(timing)
        trace = uuid.uuid4().hex
        started = time.perf_counter()
        deadline = started + .05

        async def sample():
            nonlocal deadline
            while True:
                await asyncio.sleep(max(0, deadline - time.perf_counter()))
                now = time.perf_counter()
                timing.loop_lag_ms = max(timing.loop_lag_ms, (now - deadline) * 1000)
                deadline = now + .05

        sampler = asyncio.create_task(sample())

        async def timed_send(message):
            if message['type'] == 'http.response.start':
                now = time.perf_counter()
                elapsed = (now - started) * 1000
                # Include a stall that prevented the sampler from resuming before headers.
                lag = max(timing.loop_lag_ms, max(0, now - deadline) * 1000)
                value = (f'app;dur={elapsed:.2f}, sql;dur={timing.sql_ms:.2f}, '
                         f'sql_count;dur={timing.sql_count}, loop_lag;dur={lag:.2f}, '
                         f'trace;desc="{trace}"').encode('ascii')
                message = dict(message)
                message['headers'] = list(message.get('headers', [])) + [(b'server-timing', value)]
                log.info('navdiag trace=%s status=%s app_ms=%.2f sql_ms=%.2f sql_count=%d loop_lag_ms=%.2f',
                         trace, message['status'], elapsed, timing.sql_ms, timing.sql_count, lag)
            await send(message)

        try:
            await self.app(scope, receive, timed_send)
        finally:
            sampler.cancel()
            try:
                await sampler
            except asyncio.CancelledError:
                pass
            _current.reset(token)
