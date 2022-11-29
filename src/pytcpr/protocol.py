import functools
import re


class ByteStream:
    """\
    Class for representing and deserializing KAG CBitStream objects.
    Does **not** aim to support bit reads or otherwise non-byte-aligned data.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def __repr__(self):
        return f"ByteStream({self.data})"

    def read_string(self):
        length = self.read_int(2)
        string = self.data[self.pos : self.pos + length].decode()
        self.pos += length
        return string

    def read_int(self, n_bytes):
        value = int.from_bytes(self.data[self.pos : self.pos + n_bytes], "big")
        self.pos += n_bytes
        return value

    @classmethod
    def from_hex(cls, hex):
        return cls(bytes.fromhex(hex))


rpc_matcher = re.compile(r"^@pytcpr!(\w+)~(.*)$")


class rpc:
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func

    def __call__(self, client):
        subscriber = client.subscriber()

        async def wrapper():
            async with subscriber as messages:
                async for message in messages:
                    # TODO: there is really no reason for every single RPC handler to do that.
                    match = rpc_matcher.match(message.decode())
                    if match:
                        method, arg = match.groups()
                        if method == self.func.__name__:
                            await self.func(client, ByteStream.from_hex(arg))

        return wrapper()
