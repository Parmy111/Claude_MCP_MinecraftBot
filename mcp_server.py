import httpx
from mcp.server.fastmcp import FastMCP
from minecraft_tools import get_online_players
from minecraft_client import send_to_bot

mcp = FastMCP("minecraft-tools")


@mcp.tool()
async def list_players() -> str:
    """List all players currently online in the Minecraft world."""
    players = await get_online_players()
    if not players:
        return "No players are currently online."
    return ", ".join(players)


@mcp.tool()
async def let_claude_talk(message: str) -> str:
    """Make the bot say a message in Minecraft chat."""
    try:
        resp = await send_to_bot("say", {"message": message})
    except httpx.ConnectError:
        return "Can't reach the bot. Is bot.py running?"
    return resp["result"] if resp["ok"] else f"Failed: {resp['error']}"


@mcp.tool()
async def place_block(block: str, x: int, y: int, z: int) -> str:
    """Place a block in the Minecraft world using the bot.

    block: Minecraft block id, e.g. 'cobblestone' or 'oak_planks'.
    x, y, z: integer coordinates of the empty spot to fill. Must be within
    about 4.5 blocks of the bot and adjacent to at least one solid block.
    """
    try:
        resp = await send_to_bot("place_block", {"block": block, "x": x, "y": y, "z": z})
    except httpx.ConnectError:
        return "Can't reach the bot. Is bot.py running?"
    return resp["result"] if resp["ok"] else f"Failed: {resp['error']}"

@mcp.tool()
async def break_block(x: int, y: int, z: int) -> str:
    """Break the block infront of you and then end this task:
    If you are unable to do this due to the bot not having creative throw an error"""
    try:
        resp = await send_to_bot("break_block", {"x": x, "y": y, "z": z})
    except httpx.ConnectError:
        return "Can't reach the bot. Is bot.py running?"
    return resp["result"] if resp["ok"] else f"Failed: {resp['error']}"

#Claude ──MCP/stdio──▶ mcp_server.py ──HTTP (httpx)──▶ bot.py ──bridge──▶ Mineflayer ──▶ Minecraft
if __name__ == "__main__":
    mcp.run(transport="stdio")