import asyncio
import aiotools
from collections import defaultdict
import functools

import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import TCPRClient

from .protocol import ByteStream, EventType
from .parsing import event_matcher


def event_handler_wrapper(func, message_types):
    @functools.wraps(func)
    async def wrapper(client: "TCPRClient", payload: ByteStream):
        if message_types is not None:
            messages = [
                message_type.from_bytestream(payload) for message_type in message_types
            ]
            await func(client, *messages)
        else:
            await func(client, payload)

    return wrapper


class EventRouter:
    def __init__(self):
        self._handlers = defaultdict(list)

    def register(self, event_type: EventType):
        def wrapper(func):
            self._handlers[event_type.name].append(
                event_handler_wrapper(func, event_type.args)
            )

        return wrapper

    async def handle_message(self, client: "TCPRClient", line: bytes):
        match = event_matcher.match(line.decode())
        if match is None:
            return

        event_name, encoded_payload = match.groups()
        stream = ByteStream.from_hex(encoded_payload)

        try:
            matching_handlers = self._handlers[event_name]
        except KeyError:
            logging.warning(f"Received event '{event_name}' with no matching handler")
            return

        await asyncio.gather(
            *[event_handler(client, stream) for event_handler in matching_handlers]
        )


class Router:
    def __init__(self):
        self._event_router = EventRouter()
        self._log_subscribers = []

    def event(self, event_type: EventType):
        return self._event_router.register(event_type)

    def log_subscriber(self):
        def wrapper(func):
            self._log_subscribers.append(func)

        return wrapper

    def __call__(self, client: "TCPRClient"):
        subscriber = client.subscriber()

        async def wrapper():
            async with aiotools.PersistentTaskGroup() as tg:
                async with subscriber as messages:
                    async for message in messages:
                        for sub in [
                            self._event_router.handle_message,
                            *self._log_subscribers,
                        ]:
                            tg.create_task(sub(client, message))

        return wrapper()
