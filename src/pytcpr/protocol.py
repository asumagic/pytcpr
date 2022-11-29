from dataclasses import dataclass

from typing import List, Type

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


class Serialized:
    @classmethod
    def from_bytestream(cls, stream: ByteStream):
        return cls()


@dataclass
class EventType:
    name: str
    args: List[Type[Serialized]]
