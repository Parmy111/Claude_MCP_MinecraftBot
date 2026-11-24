# Minecraft MCP Agent

Chat with Claude and have it act inside Minecraft. This project connects [Claude Desktop](https://claude.ai/download) to a [Mineflayer](https://github.com/PrismarineJS/mineflayer) bot through a self-written [MCP](https://modelcontextprotocol.io) server, so you can type things like *"walk to 100 64 200 and place three cobblestone blocks in front of you"* and watch the bot do it.

**The goal:** a build buddy. Something that can help you construct things alongside you, or take over a whole build on the side while you do something else. The current version can place and break blocks, walk to coordinates, and run server commands. It is good at small jobs and still awkward at large ones (see [Challenges](#challenges-i-ran-into) and [Still to implement](#still-to-implement)).

## Contents

- [Tools Claude gets](#tools-claude-gets)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Setup](#setup)
- [What's new](#whats-new)
- [Challenges I ran into](#challenges-i-ran-into)
- [Still to implement](#still-to-implement)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

## Tools Claude gets

| Tool | What it does |
|---|---|
| `place_block(block, x, y, z)` | Places a block (e.g. `cobblestone`) at exact coordinates. Checks that the spot is empty and in reach, finds a solid neighbor to click against, and gives the bot the block with `/give` if it is missing from the inventory. |
| `break_block(x, y, z)` | Breaks the block at the given coordinates (must be within reach). |
| `move_to(x, y, z)` | Walks the bot to a position using pathfinding (jumps, goes around obstacles). Waits until the bot arrives or times out. |
| `let_claude_talk(message)` | Makes the bot say something in chat. A message starting with `/` runs as a command, which is how teleporting, `/setblock` and `/fill` work. |
| `list_players()` | Lists the players currently online (uses the Minecraft management server, see setup step 2). |

Errors come back to Claude as readable messages (for example "Target is already occupied by stone"), so Claude can understand what went wrong and adjust.

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

Each request names an `action` (`place_block`, `break_block`, `move_to`, `say`). `bot.py` looks the action up in its `ACTIONS` table, runs it, and replies with `{"ok": true, "result": ...}` or `{"ok": false, "error": ...}`.

To add a new capability: write an `action_...` function in `bot.py`, add it to `ACTIONS`, then add a matching `@mcp.tool()` in `mcp_server.py`.

## Project structure

| File | Purpose |
|---|---|
| `bot.py` | Creates the Mineflayer bot (with the pathfinder plugin) and runs the local HTTP listener. Contains the actions, plus a few in-game chat commands (`hello`, `place`, `break`). |
| `mcp_server.py` | The MCP server (FastMCP, stdio). Defines the tools Claude sees and forwards them to the bot. |
| `minecraft_client.py` | Helpers: `send_to_bot()` (HTTP to the bot, 90 s timeout) and `call_minecraft()` (websocket to the management server). |
| `minecraft_client_2.py` | Copy of the client with a placeholder secret and a shorter timeout. Not imported by anything. Useful as a repo-safe template. |
| `minecraft_tools.py` | Wrapper functions around the management server, e.g. `get_online_players()`. |
| `test.py` | Standalone check that the management-server connection works. |

## Requirements

- A Minecraft Java Edition server you control (a single-player world opened to LAN also works for the bot itself)
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

The `javascript` package installs Mineflayer and `vec3` the first time `bot.py` runs. `mineflayer-pathfinder` is also needed for `move_to`; if it is not installed automatically, run `npm install mineflayer-pathfinder` in the folder the bridge uses. This needs Node.js and an internet connection.

### 2. Enable the Minecraft management server (only for `list_players`)

Only `list_players` uses this. If you don't need it, skip this step and delete that tool.

Enable the management server in `server.properties` and set a secret and port. Property names depend on your Minecraft version, so check its documentation. Then update `minecraft_client.py`:

```python
MINECRAFT_URL = "ws://localhost:25585"   # your management server host and port
SECRET = "..."                           # your management server secret
```

Do not commit a real secret. Load it from an environment variable instead:

```python
import os
SECRET = os.environ["MC_MGMT_SECRET"]
```

Then set it in the Claude Desktop config (step 5) under `"env"`. If a real secret was ever pushed to GitHub, generate a new one.

### 3. Point the bot at your server

In `bot.py`:

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

- **Operator** is required for `/tp`, `/setblock`, `/fill` and `/give` sent through `let_claude_talk`. Without it, the server silently refuses them.
- **Creative mode** gives flying and instant block breaking, and `place_block` can `/give` itself whatever it needs. In survival, give the bot the blocks it should place, for example `/give PythonBot cobblestone 64`.

### 5. Connect Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the server. Use your own absolute paths, with doubled backslashes on Windows:

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

On macOS and Linux, `command` is the full path to `.venv/bin/python`. This project was built and tested on Windows.

### 6. Run it

Start things in this order:

1. Start your Minecraft server or world.
2. Run `python bot.py` and wait for `Bot listener running on http://127.0.0.1:8765`.
3. Fully quit and reopen Claude Desktop (from the system tray, not just closing the window).

Then try:

> Place a cobblestone block at 100 64 200.

> Walk to 199 64 207, then place three cobblestone blocks in a row starting at 199 64 210.

### What to restart after a change

| You changed | Restart |
|---|---|
| `bot.py` | `bot.py` only |
| `mcp_server.py`, `minecraft_client.py`, `minecraft_tools.py` | Claude Desktop (fully quit, then reopen) |
| Minecraft server settings | The Minecraft server |

## What's new

- **`move_to` tool.** The bot can now walk to coordinates using `mineflayer-pathfinder`. The plugin and its movement rules are set up once when the bot spawns. Before this, the only way to move the bot was a `/tp` command through chat.
- **Auto-give for missing blocks.** If the bot does not have the block it is asked to place, `place_block` runs `/give` and waits for the inventory to update before placing.
- **Slash commands through chat.** `let_claude_talk` runs any command the bot is allowed to run, which gave Claude access to `/tp`, `/setblock` and `/fill` for bigger jobs.
- **Safer actions with clear errors.** Every action now validates its inputs and reports specific problems: unloaded area, occupied target, out of reach, nothing to break, no solid block to place against.
- **A first large build.** A two-story spruce cabin (about 900 blocks, reconstructed from reference screenshots) was used as a stress test. It worked as a proof of concept and showed where the design runs out of room (next section).

## Challenges I ran into

- **Movement is asynchronous.** `setGoal` returns immediately instead of waiting for the bot to arrive, and `isMoving()` can briefly read false while a path is still being computed. `move_to` now polls the distance to the target and cancels the goal if it times out.
- **Position is not ready right after a teleport.** Reading the bot's position immediately after `/tp` can fail with a `distanceTo` error. `place_block` waits briefly when the position is missing.
- **Minecraft's placement rules.** Blocks can only be placed by clicking the face of an existing block, so the target must touch something solid, and it must be within about 4.5 blocks of the bot. Replaceable blocks such as tall grass, leaf litter and snow layers count as "occupied", which blocks placement.
- **Bridging Python and JavaScript.** Mineflayer is JavaScript, so everything goes through the `javascript` bridge, and the HTTP listener handles each request on its own thread while calling into that bridge.
- **Commands give no feedback.** When Claude sends `/tp` or `/fill` through chat, the tool only reports that the message was sent. Claude cannot tell whether the server ran it or refused it (for example, because the bot is not an operator).
- **Claude cannot see the world.** There is no tool to read the bot's position or the block at a coordinate, so Claude needs coordinates from you and cannot verify or repair its own work.
- **One block per call does not scale.** Every `place_block` is a separate round trip through Claude. That is fine for tens of blocks and impractical for a 900-block house. Using `/fill` and `/setblock` through chat is a workaround, but without feedback it is blind.
- **Block states cannot be set.** `place_block` takes only a block id, so stairs, doors, trapdoors and logs cannot be given a direction. The `/setblock` command can (for example `spruce_stairs[facing=east]`).
- **Keeping secrets out of the repo.** The management-server secret was hardcoded in `minecraft_client.py`. It needs to move to an environment variable (see to-do list).

## Still to implement

**Tools Claude needs to build well**

- [ ] `get_position()` so Claude can build relative to the bot instead of asking for coordinates.
- [ ] `get_block(x, y, z)` and a region scan, so Claude can check and repair what it built.
- [ ] `run_command(cmd)` that returns the server's response, replacing the blind chat-based commands.
- [ ] `fill(block, x1, y1, z1, x2, y2, z2)` for walls, floors and boxes in a single call.
- [ ] `build_blueprint(...)`: Claude sends a compact list of cuboids and single blocks (with block states), and `bot.py` loops over them, moves the bot, and places everything itself. This is the main fix for the scaling problem.
- [ ] Block-state support in `place_block` (stairs facing, door halves, trapdoors, log axis).
- [ ] Treat replaceable blocks (tall grass, snow layers) as placeable, or break them first.

**Buddy features**

- [ ] Follow a player and stay nearby.
- [ ] Respond to in-game chat requests so you do not have to alt-tab to Claude Desktop.
- [ ] Background jobs: start a build, report progress, and be able to pause or cancel it.
- [ ] Survival support: collect or request materials, manage the inventory, build scaffolding.
- [ ] Undo: remember what was changed in a build so it can be reverted.

**Cleanup**

- [ ] Load `SECRET` from an environment variable (README already describes this, the code does not do it yet). Rotate the secret if it was ever committed.
- [ ] Wire up `fly_to_location` in `bot.py` (it exists but is not in `ACTIONS`).
- [ ] Fix the `move_to` timeout message: the code waits up to 75 seconds but the error says 30.
- [ ] Update the `break_block` tool description in `mcp_server.py`; it still says "break the block in front of you" but the tool breaks the block at the given coordinates.
- [ ] Finish or remove `speak_in_chat` in `minecraft_tools.py`.
- [ ] Add a lock so two requests cannot drive the bot at the same time.
- [ ] Remove or merge `minecraft_client_2.py`.

## Troubleshooting

| Problem | Likely cause |
|---|---|
| Tools don't show up in Claude | `mcp_server.py` isn't calling `mcp.run(transport="stdio")`, the packages aren't installed in that venv, or Claude Desktop wasn't fully restarted. Check `%APPDATA%\Claude\logs\mcp-server-minecraft-tools.log`. |
| "Can't reach the bot. Is bot.py running?" | Start `bot.py` first and wait for the listener message. |
| `Unknown action: ...` | `bot.py` is running an old version, or the action isn't in `ACTIONS`. Restart `bot.py`. |
| "Target is X blocks away" | Placing and breaking only work within about 4.5 blocks. Use `move_to` first. |
| "No solid adjacent block to place against" | The target must touch a solid block, because Minecraft places by clicking an existing block's face. |
| "Target is already occupied by ..." | Something is there. Break it first. Decorations like tall grass count as occupied. |
| "Timed out; couldn't reach ..." | The pathfinder couldn't find a route, or the destination is blocked or far away. Try a nearer or open spot. |
| A teleport or command seems to do nothing | The bot isn't an operator. Run `/op PythonBot`. |
| An error right after a teleport | The bot's position needs a moment to update. Retry. |
| Don't print to stdout in `mcp_server.py` | With stdio transport, stdout is the protocol channel. Use `logging` or `print(..., file=sys.stderr)`. |

## Security notes

- The bot's listener binds to `127.0.0.1` only and has no authentication. Do not expose that port to a network.
- Keep the management-server secret out of the repo, and add anything that holds secrets to `.gitignore`.
- `let_claude_talk` can send any slash command the bot is allowed to run. Only give the bot operator rights on a server you are comfortable letting Claude control.
