import logging

from pytcpr.client import log_consumer


@log_consumer
async def log_everything(_client, messages):
    async for message in messages:
        logging.info(message.decode())
