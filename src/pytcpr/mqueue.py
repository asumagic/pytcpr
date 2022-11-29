import asyncio


class MultiSubscriberQueue:
    """\
    A queue allowing multiple "subscribers" to consume the same stream of data in parallel.
    Subscribers can be added and removed on the fly."""

    def __init__(self):
        self._subscribers = set()

    def _subscribe(self):
        subscriber = CancellableSubscriber(asyncio.Queue())
        self._subscribers.add(subscriber)
        return subscriber

    def _unsubscribe(self, subscriber):
        self._subscribers.remove(subscriber)

    def subscriber(self):
        return MessageSubscriptionManager(self)

    async def submit(self, message):
        for subscriber in self._subscribers:
            await subscriber.queue.put(message)

    def terminate(self):
        for subscriber in self._subscribers:
            subscriber.cancel()


class QueueAsyncIterator:
    """Asynchronous iterator yielding elements from a queue or CancellableSubscriber."""

    def __init__(self, subscriber):
        self.subscriber = subscriber

    async def __anext__(self):
        return await self.subscriber.get()


class CancellableSubscriber:
    """\
    Queue subscriber that will cancel the task when the end of the queue is reached.
    The end of the queue is marked by cancel() by pushing a None value.
    Can be iterated over with `async for`."""

    def __init__(self, queue):
        self.queue = queue

    async def get(self):
        payload = await self.queue.get()

        if payload is None:
            raise asyncio.CancelledError()

        return payload

    def __aiter__(self):
        return QueueAsyncIterator(self)

    def cancel(self):
        self.queue.put_nowait(None)


class MessageSubscriptionManager:
    """Context manager for message subscription."""

    def __init__(self, mqueue: MultiSubscriberQueue):
        self.mqueue = mqueue

    async def __aenter__(self):
        self._subscription = self.mqueue._subscribe()
        return self._subscription

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        self.mqueue._unsubscribe(self._subscription)
