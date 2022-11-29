import asyncio
from detoxify import Detoxify
import logging
import torch

from pytcpr.client import TCPRClient, ServerInfo
from pytcpr.protocol import rpc

from .common import common_init_stuff

common_init_stuff()

torch.set_num_threads(1)

toxic_model = Detoxify("original")


@rpc
async def chat_filter(client, arg):
    user = arg.read_string()
    message = arg.read_string()

    toxicity = toxic_model.predict(message)

    score = (
        toxicity["toxicity"] * 0.15
        + toxicity["severe_toxicity"] * 0.8
        + toxicity["identity_attack"] * 1.0
        + toxicity["insult"] * 0.8
        + toxicity["obscene"] * 0.15
    )

    logging.info(f"msg '{user}': '{message}' ({score})")

    if score > 1.0:
        await client.write_line(f"/msg {user}, watch your tongue!".encode())


async def main():
    client = await TCPRClient.connect(ServerInfo("test", "127.0.0.1", 50303))
    await client.run(password="1337", services=[chat_filter])


asyncio.run(main())
