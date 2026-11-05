# Minecraft MCP Agent

Control a Minecraft bot by chatting with Claude. This project connects [Claude Desktop](https://claude.ai/download) to a [Mineflayer](https://github.com/PrismarineJS/mineflayer) bot through a self-written [MCP](https://modelcontextprotocol.io) server, so you can type things like *"teleport to 199 64 207 and place three cobblestone blocks in front of you"* and watch the bot do it.

## Features

Claude gets these tools:

| Tool | What it does |
|---|---|
| `place_block(block, x, y, z)` | Places a block (e.g. `cobblestone`) at exact coordinates. Finds a solid neighboring block to click against and checks reach and inventory first. |
| `break_block(x, y, z)` | Breaks the block at the given coordinates. |
| `let_claude_talk(message)` | Makes the bot say something in chat. A message starting with `/` runs as a command (this is how teleporting works, see [Setup](#4-give-the-bot-permissions)). |
| `list_players()` | Lists players currently online (uses the Minecraft management server, see [Setup](#2-enable-the-minecraft-management-server-only-for-list_players)). |

Errors come back to Claude as readable messages (e.g. "No cobblestone in inventory"), so it can understand what went wrong and adjust.

## How it works

Claude Desktop and the bot are two separate programs, so they talk over a small local HTTP connection:

```
You type in Claude Desktop
        |
        v   MCP over stdio
  mcp_server.py        (launched by Claude Desktop)
        |
        v   HTTP POST to 127.0.0.1:8765
  bot.py listener      (you run this yourself)
        |
        v   Python <-> JavaScript bridge
  Mineflayer bot  -->  Minecraft server
```

## Project structure

| File | Purpose |
|---|---|
| `bot.py` | Creates the Mineflayer bot and runs a local HTTP listener. Each request names an action (`place_block`, `break_block`, `say`) that the bot carries out. Also contains a few in-game chat commands (`hello`, `place`). |
| `mcp_server.py` | The MCP server (FastMCP, stdio). Defines the tools Claude sees and forwards them to the bot. |
| `minecraft_client.py` | Helpers: `send_to_bot()` (HTTP to the bot) and `call_minecraft()` (websocket to the Minecraft management server). |
| `minecraft_tools.py` | Wrapper functions around the management server, e.g. `get_online_players()`. |
| `test.py` | Standalone check that the management-server connection works. |

## Requirements

- A Minecraft Java Edition server you control (a local single-player world opened to LAN also works for the bot itself)
- Python 3.10+
- [Node.js](https://nodejs.org) (Mineflayer is a JavaScript library; the `javascript` Python package bridges to it)
- [Claude Desktop](https://claude.ai/download)

## Setup

### 1. Install

```bash
git clone <your-repo-url>
cd <your-repo-folder>

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install mcp httpx websockets javascript
```

The `javascript` package installs Mineflayer and `vec3` automatically the first time `bot.py` runs (this needs Node.js and an internet connection).

### 2. Enable the Minecraft management server (only for `list_players`)

Only the `list_players` tool uses this. If you don't need it, skip this step and delete that tool.

Enable the management server in your server's `server.properties`, and set a secret and port. Property names and availability depend on your Minecraft version, so check your version's documentation. Then update `minecraft_client.py`:

```python
MINECRAFT_URL = "ws://localhost:25585"   # match your management server host and port
SECRET = "..."                           # match your management server secret
```

**Never commit your secret.** Load it from an environment variable instead:

```python
import os
SECRET = os.environ["MC_MGMT_SECRET"]
```

Then set it in the Claude Desktop config (step 5) under `"env"`. If you ever pushed a real secret to GitHub, generate a new one.

### 3. Point the bot at your server

In `bot.py`, edit the bot settings:

```python
bot = mineflayer.createBot({
    'host': 'localhost',      # your server address
    'username': 'PythonBot',  # the bot's in-game name
    # 'port': 25565,          # add this if your server isn't on the default port
})
```

If you open a single-player world to LAN, Minecraft picks a random port each time, so set `'port'` to the one shown in chat. If you rename the bot, use the new name in the commands below.

### 4. Give the bot permissions

Run these in the server console, or in game as an operator:

```
/op PythonBot
/gamemode creative PythonBot
```

- **Operator (`/op`)** is required for `/tp` and `/setblock`-style commands sent through `let_claude_talk`. Without it, the server silently refuses them.
- **Creative mode** gives the bot flying and instant block breaking, and means it won't run out of blocks. If you stay in survival, give the bot the blocks it should place, for example `/give PythonBot cobblestone 64`. `place_block` fails with "No <block> in inventory" otherwise.

### 5. Connect Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add your server. **Use your own absolute paths**, with doubled backslashes on Windows:

```json
{
  "mcpServers": {
    "minecraft-tools": {
      "command": "C:\\path\\to\\your\\project\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\your\\project\\mcp_server.py"],
      "env": { "MC_MGMT_SECRET": "your-secret-here" }
    }
  }
}
```

On macOS/Linux, `command` is `.venv/bin/python` with its full path. This project was built and tested on Windows.

### 6. Run it

Start things in this order:

1. Start your Minecraft server / world.
2. Run `python bot.py` and wait for `Bot listener running on http://127.0.0.1:8765`.
3. Fully quit and reopen Claude Desktop (from the system tray, not just closing the window).

Then ask Claude something like:

> Place a cobblestone block at 100 64 200.

> Teleport to 199 64 207, then place three cobblestone blocks in a row starting at 199 64 210.

## What to change when you set this up

| Where | What | Why |
|---|---|---|
| `minecraft_client.py` | `SECRET` (use an env var), `MINECRAFT_URL` | Management server credentials and address (only for `list_players`) |
| `bot.py` | `host`, `username`, optional `port` | Which server the bot joins and what it's called |
| `bot.py` | `HOST`, `PORT` (default `127.0.0.1:8765`) | Where the bot's listener runs |
| `minecraft_client.py` | `BOT_URL` | Must match the listener's host and port in `bot.py` |
| `claude_desktop_config.json` | Python path and `mcp_server.py` path | Your own install location |
| In game | `/op` and `/gamemode creative` for the bot | Needed for commands and flying; see step 4 |
| In game | Give the bot the blocks it will place (survival only) | `place_block` uses real inventory items |

## When to restart what

| You changed | Restart |
|---|---|
| `bot.py` | `bot.py` only |
| `mcp_server.py`, `minecraft_client.py`, `minecraft_tools.py` | Claude Desktop (fully quit, then reopen) |
| Minecraft server settings | The Minecraft server |

## Troubleshooting

| Problem | Likely cause |
|---|---|
| Tools don't show up in Claude | `mcp_server.py` isn't calling `mcp.run(transport="stdio")`, the package isn't installed in that venv, or Claude Desktop wasn't fully restarted. Check `%APPDATA%\Claude\logs\mcp-server-minecraft-tools.log`. |
| "Can't reach the bot. Is bot.py running?" | Start `bot.py` first and wait for the listener message. |
| `Unknown action: ...` | `bot.py` is running an old version, or the action isn't in the `ACTIONS` dict. Restart `bot.py`. |
| "Target is X blocks away" | The bot only places and breaks within about 4.5 blocks. Teleport it closer first. |
| "No solid adjacent block to place against" | Minecraft places blocks by clicking an existing block's face, so the target must touch a solid block. |
| "Target is already occupied by ..." | Something is there. Break it first. Decorations like `leaf_litter` or tall grass also count as occupied. |
| A teleport or command seems to do nothing | The bot isn't an operator. Run `/op PythonBot`. |
| An error right after a teleport | The bot's position needs a moment to update. Retry. |
| Don't print to stdout in `mcp_server.py` | With stdio transport, stdout is the protocol channel. Use `logging` or `print(..., file=sys.stderr)`. |

## Security notes

- The bot's listener only binds to `127.0.0.1` and has no authentication. Don't expose that port to a network.
- Keep your management-server secret out of the repo. Add anything that holds secrets to `.gitignore`.
- `let_claude_talk` can send any slash command the bot is allowed to run. Only give the bot operator rights on a server you're comfortable letting Claude control.

## Known limitations and ideas

- Placement and breaking work at exact coordinates within reach; the bot doesn't walk or pathfind yet. A `move_to` tool using `mineflayer-pathfinder` would fix that.
- Replaceable blocks (leaf litter, tall grass, snow layers) are treated as occupied.
- Each block is one tool call. A fill tool (line, wall, box) would make bigger builds much faster.
- `speak_in_chat` in `minecraft_tools.py` is unfinished and unused; `let_claude_talk` handles chat through the bot instead.
