from dataclasses import dataclass
import logging


@dataclass
class BanlistEntry:
    account: str
    ip: str
    reason: str
    expires: str

    @classmethod
    def parse(cls, line):
        account, ip, reason, expires = [field.strip() for field in line.split(",")]
        return cls(account, ip, reason, expires)


async def query_banlist(client):
    bans = [
        message.decode()
        async for message in client.write_script_and_read_responses(
            "getSecurity().printBans()"
        )
    ]
    bans = bans[3:-1]
    bans = [BanlistEntry.parse(ban) for ban in bans]
    bans = {ban.account: ban for ban in bans}
    return bans


async def query_playerlist(client):
    players = [
        message.decode()
        async for message in client.write_script_and_read_responses(
            "getSecurity().printPlayerSeclevs()"
        )
    ]
    return players


def common_init_stuff():
    logging.basicConfig(level=logging.INFO)
