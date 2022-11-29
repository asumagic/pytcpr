import asyncio
import logging
import uuid
import re
import functools
from dataclasses import dataclass

from .mqueue import MultiSubscriberQueue
from .parsing import timestamp_matcher


@dataclass
class ServerInfo:
    name: str
    """User-friendly name for the server, used in logs, but of no semantic importance."""

    host: str
    """Host or IPv4 address to the TCPR server to connect to."""

    port: int
    """Port of the TCPR server to connect to. Defined to `sv_port` on KAG servers."""


class TCPRError(Exception):
    """\
    Error specific to TCPR low-level connectivity."""

    pass


class AuthenticationError(TCPRError):
    """\
    Error raised when the TCPR client has failed to authenticate.
    This is generally raised unconditionally when the server dropped the connection during authentication."""

    pass


class SanitizerError(TCPRError):
    """\
    Error raised at serialization/deserialization when a outbound/inbound message is found to be broken."""

    pass


class log_consumer:
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func

    def __call__(self, client):
        subscriber = client.subscriber()

        async def wrapper():
            async with subscriber as messages:
                await self.func(client, messages)

        return wrapper()


uuid_generator = uuid.uuid4


def make_random_challenge():
    return f"@pytcpr~{uuid_generator()}"


protocol_sanitizer = re.compile(b"\n|\r|\x00")


class TCPRClient:
    def __init__(self, server_info: ServerInfo, reader, writer):
        self.info = server_info
        self._reader = reader
        self._writer = writer
        self._mqueue = MultiSubscriberQueue()

    @classmethod
    async def connect(cls, server_info: ServerInfo):
        logging.info(f"Initiating connection to {server_info.host}:{server_info.port}")
        reader, writer = await asyncio.open_connection(
            server_info.host, server_info.port
        )
        logging.info(f"Connected to {server_info.host}:{server_info.port}")

        client = cls(server_info, reader, writer)

        return client

    async def _auth(self, password):
        await self.write_line(password)
        await self.ping()
        logging.info("Authentication successful")

    async def ping(self):
        ping_challenge = make_random_challenge().encode()
        pong_script = f"tcpr('{ping_challenge}')".encode()

        logging.debug(f"Submitting ping challenge: {ping_challenge}")

        try:
            await asyncio.wait_for(
                self.write_line_and_block_until_message(pong_script, ping_challenge), 15
            )
        except asyncio.TimeoutError as e:
            raise ConnectionResetError("Server did not respond to ping") from e

        logging.debug(f"Ping challenge {ping_challenge} passed")

    async def run(self, password, services):
        service_coros = [service(self) for service in services]
        sink_task = asyncio.create_task(self._read_and_dispatch_messages())

        authed = False

        async def client_flow():
            global authed

            await self._auth(password.encode())
            authed = True

            await asyncio.gather(*service_coros)

        try:
            await asyncio.gather(client_flow(), sink_task)
        except ConnectionResetError as e:
            if not authed:
                raise AuthenticationError(
                    "Server rejected us during auth: wrong password?"
                ) from e
            raise
        finally:
            logging.info("Shutting down")

            for service_coro in service_coros:
                service_coro.close()

            sink_task.cancel()

    async def _read_and_dispatch_messages(self):
        try:
            while True:
                message = await self._read_line()

                # FIXME: I believe we're not doing the right thing with handling server disconnects
                # on _read_line.
                # if len(message) == 0:
                #     raise ConnectionResetError("Server closed connection")

                await self._mqueue.submit(message)
        except:
            self._mqueue.terminate()
            raise

    def subscriber(self):
        return self._mqueue.subscriber()

    async def write_line_and_read_messages(self, line: bytes):
        """Write a line and read all messages after sending the line.

        Note that this may yield messages that were sent before the line was sent.
        This is only useful when future responses can be recognized by their content (e.g. pings).

        Use write_script_and_read_response() if you need accurate responses."""

        async with self.subscriber() as messages:
            await self.write_line(line)
            async for message in messages:
                yield message

    async def write_line_and_block_until_message(self, line: bytes, expected: bytes):
        async for message in self.write_line_and_read_messages(line):
            if message == expected:
                break

    async def write_script_and_read_responses(self, script: str):
        script = script.replace("\n", "")

        challenge = make_random_challenge()
        script = f"string __c='{challenge}';tcpr(__c);{{{script};}};tcpr(__c);"

        encoded_challenge = challenge.encode()

        found_challenge = False

        async for message in self.write_line_and_read_messages(script.encode()):
            if message == encoded_challenge:
                if not found_challenge:
                    # first challenge: start reading response
                    found_challenge = True
                else:
                    # second challenge: stop reading response
                    break
            else:
                if found_challenge:
                    yield message

    def sanitize(self, line: bytes):
        if protocol_sanitizer.search(line) is not None:
            raise ValueError(f"Line {line} contains illegal characters!!")

    async def _read_line(self) -> bytes:
        text = await self._reader.readline()

        # Remove newline. we always use \n, so the server will never send \r\n
        # See write_line() comments for rationale
        text = text[:-1]

        # remove timestamp if present
        text = timestamp_matcher.sub(b"", text, 1)

        try:
            self.sanitize(text)
        except ValueError as e:
            raise SanitizerError(f"Server sent illegal line: {text}") from e

        return text

    async def write_line(self, line: bytes):
        try:
            self.sanitize(line)
        except ValueError as e:
            raise SanitizerError(f"Client sent illegal line: {line}") from e

        if len(line) + 1 >= 16384:
            raise SanitizerError(
                f"Line {line[:100]}... is too long. "
                f"The TCPR server has a 16383 byte limit on received messages, including the newline."
            )

        # NOTE: KAG TCPR supports both `\r\n` and `\n` line endings.
        # The client decides which one shall be used during the entire session:
        # The server will use the line break encoding used at authentication time.
        # This function is used by `_auth()`, and we're deciding to use `\n` everywhere.

        logging.debug(f"Writing line: {line}")
        self._writer.write(line)
        self._writer.write(b"\n")
        await self._writer.drain()
