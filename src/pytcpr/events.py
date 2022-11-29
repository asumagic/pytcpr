from dataclasses import dataclass

from .protocol import ByteStream, EventType, Serialized


@dataclass
class ChatMessage(Serialized):
    account_name: str
    message: str

    @classmethod
    def from_bytestream(cls, stream: ByteStream):
        return ChatMessage(
            account_name = stream.read_string(),
            message = stream.read_string()
        )


chat_handler = EventType("chat", [ChatMessage])
