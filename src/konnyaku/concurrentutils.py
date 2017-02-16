import asyncio
import functools
import time
import typing


Decorator = typing.Callable[[typing.Callable], typing.Callable]


def throttling(wait: int) -> Decorator:
    def decorator(func: typing.Callable) -> typing.Callable:
        last_called = None
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last_called

            async with lock:
                now = time.monotonic()

                if last_called is not None:
                    delta = now - last_called

                    if delta < wait:
                        await asyncio.sleep(wait - delta)

                try:
                    return await func(*args, **kwargs)
                finally:
                    last_called = time.monotonic()

        return wrapper

    return decorator


def throttling_per(wait: int, concurrency: int, per: typing.Callable) -> Decorator:
    func_queue_map = {}

    def decorator(func: typing.Callable) -> typing.Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            p = per(*args, **kwargs)

            if p not in func_queue_map:
                q = func_queue_map[p] = asyncio.Queue()
                for _ in range(concurrency):
                    q.put_nowait(throttling(wait)(func))

            throttled_func = await func_queue_map[p].get()

            try:
                return await throttled_func(*args, **kwargs)

            finally:
                func_queue_map[p].put_nowait(throttled_func)

        return wrapper

    return decorator
