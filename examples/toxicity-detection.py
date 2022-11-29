import asyncio
from detoxify import Detoxify
import logging
import torch

from pytcpr.client import TCPRClient, ServerInfo
from pytcpr.router import Router
from pytcpr.events import ChatMessage, chat_handler

from common import common_init_stuff

common_init_stuff()

torch.set_num_threads(1)

toxic_model = Detoxify("original")
toxicity_kinds = ["severe_toxicity", "identity_attack", "insult"]

router = Router()


@router.event(chat_handler)
async def chat_filter(client: TCPRClient, message: ChatMessage):
    scores = toxic_model.predict(message.message)
    score = max(scores[kind] for kind in toxicity_kinds)

    logging.info(f"{message} has a toxicity score of {score:.2f}")

    if score > 0.5:
        await client.write_line(
            f"/msg {message.account_name}, watch your tongue!".encode()
        )


@router.log_subscriber()
async def log_consumer(_client: TCPRClient, message):
    logging.info(f"Received message: {message}")


async def main():
    client = await TCPRClient.connect(ServerInfo("test", "127.0.0.1", 50303))
    await client.run(password="1337", router=router)


asyncio.run(main())
