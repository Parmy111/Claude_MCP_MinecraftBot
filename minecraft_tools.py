from minecraft_client import call_minecraft

async def get_online_players():
    response = await call_minecraft("minecraft:players")

    players = response["result"]

    return [player["name"] for player in players]

async def speak_in_chat():
    speak = await call_minecraft("minecraft:say")


