import asyncio
from minecraft_tools import get_online_players


async def main():
    players = await get_online_players()

    print(players)


asyncio.run(main())