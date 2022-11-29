import asyncio

class MultisubscriberQueue:
    def __init__(self):
        self.subscribers = set()

    def _subscribe(self):
        subscriber = CancellableSubscriber(asyncio.Queue())
        self.subscribers.add(subscriber)
        return subscriber

    def _unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)

    def subscriber(self):
        return MessageSubscriber(self)

    async def submit(self, message):
        for subscriber in self.subscribers:
            await subscriber.queue.put(message)

    def terminate(self):
        for subscriber in self.subscribers:
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


class MessageSubscriber:
    def __init__(self, mqueue: MultisubscriberQueue):
        self.mqueue = mqueue
        self.subscription = self.mqueue._subscribe()

    async def __aenter__(self):
        return self.subscription

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        self.mqueue._unsubscribe(self.subscription)