# =====================================================================
# bot.py
# Runs the Mineflayer bot AND a small local web server. The MCP server
# (mcp_server.py) sends this web server JSON requests, and the matching
# "action" function below carries them out in the Minecraft world.
# =====================================================================

# 'require' loads JavaScript (Node) libraries into Python via the bridge.
# 'On' attaches a Python function to a JavaScript event (like "chat").
from javascript import require, On
import json      # encode/decode the JSON messages sent over HTTP
import math      # sin/cos for the in-game 'place' command
# These two build the tiny web server that receives requests from the MCP server:
#   BaseHTTPRequestHandler = the class that decides what to do with each request
#   ThreadingHTTPServer    = the server itself; handles each request on its own thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time      # used for time.sleep() pauses

# Load the Mineflayer JavaScript library (the thing that controls the bot)
mineflayer = require('mineflayer')
# Load vec3, the JavaScript class Mineflayer uses for (x, y, z) positions
vec3_module = require('vec3')
Vec3 = vec3_module.Vec3   # shortcut so we can write Vec3(x, y, z)
# Load the pathfinder plugin (navigation: routes, jumping, going around walls)
pathfinder_module = require('mineflayer-pathfinder')
pathfinder = pathfinder_module.pathfinder   # the plugin itself, passed to bot.loadPlugin()
Movements = pathfinder_module.Movements     # rules for how the bot may move (jump, break blocks, etc.)
goals = pathfinder_module.goals             # goal types, e.g. goals.GoalBlock(x, y, z)

# Create the bot and connect it to a Minecraft server running on this computer.
# It joins as a player named "PythonBot".
bot = mineflayer.createBot({
    'host': 'localhost',
    'username': 'PythonBot',
})

# Load the pathfinder plugin ONCE, right after the bot is created.
# This is what adds bot.pathfinder (it doesn't exist until this runs).
bot.loadPlugin(pathfinder)


# Movements needs the bot's Minecraft data, which is only ready once the bot
# has joined the world. So we set it up when the 'spawn' event fires
# instead of immediately.
@On(bot, 'spawn')
def on_spawn(*args):
    bot.pathfinder.setMovements(Movements(bot))

# ---------- In-game chat commands (unchanged behavior) ----------
# These respond to people typing in Minecraft chat. They are separate from
# the MCP/HTTP path further down.

# Runs every time any chat message appears in the game.
# 'this' is required by the bridge; 'username' is who spoke; 'message' is what they said.
@On(bot, 'chat')
def on_chat(this, username, message, *args):
    # Ignore the bot's own messages so it doesn't react to itself
    if username == bot.username:
        return

    # Typing "hello" in game makes the bot greet the speaker
    if message == 'hello':
        bot.chat(f"Hello, {username}!")

    # Typing "place" makes the bot place a block in front of itself
    if message == 'place':
        try:
            # Look through the bot's inventory for the first matching block
            item_to_place = None
            for item in bot.inventory.items():
                if 'cobblestone' in item.name or 'dirt' in item.name or 'netherite_block' in item.name:
                    item_to_place = item
                    break

            # Nothing usable in the inventory, so tell the player and stop
            if item_to_place is None:
                bot.chat("I don't have any cobblestone or dirt to place.")
                return

            # Put that block in the bot's hand (placing requires holding it)
            bot.equip(item_to_place, 'hand')

            # yaw = which way the bot is facing (in radians).
            # These two lines convert it to a step of -1, 0 or 1 along x and z,
            # which is "one block in front of the bot".
            yaw = bot.entity.yaw
            dx = round(-math.sin(yaw))
            dz = round(-math.cos(yaw))

            # The ground block one step ahead and one block down from the bot's feet
            ref_block_pos = bot.entity.position.offset(dx, -1, dz)
            reference_block = bot.blockAt(ref_block_pos)

            # blockAt returns nothing if that area isn't loaded
            if not reference_block:
                bot.chat("I can't detect a ground block there.")
                return

            # Click the TOP face (Vec3(0, 1, 0) = up) of the ground block.
            # The new block appears on top of it.
            bot.placeBlock(reference_block, Vec3(0, 1, 0))
            bot.chat("Block placed successfully!")
        # If anything above fails, report the error in game chat
        except Exception as e:
            bot.chat(f"Failed to place block: {str(e)}")
            

    if message == 'break':
        try:
            if (bot.targetDigBlock):
                bot.chat(f"already digging!")
            else:
                target = bot.blockAt(bot.entity.position.offset(0, -1, 0))
                if (target and bot.canDigBlock(target)):
                    bot.dig(target)
        # If anything above fails, report the error in game chat
        except Exception as e:
            bot.chat(f"Failed to dig block: {str(e)}")

        

# ---------- Actions callable from the MCP server ----------
# Each action takes a 'params' dict (the data Claude's tool sent), does
# something with the bot, and returns a string. Raising an error here makes
# the HTTP handler send back {"ok": false, "error": ...}.

# Block names that count as "empty space"
AIR = {"air", "cave_air", "void_air"}
# The 6 directions around a block: down, up, east, west, south, north.
# Used to find a solid block next to the target to click against.
NEIGHBORS = [(0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]


# Action: make the bot say something in chat
# (a message starting with "/" runs as a command, which is how /tp works)
def action_say(params):
    message = params.get("message")
    if not message:
        raise ValueError("'message' is required")
    bot.chat(str(message))
    return f"Said: {message}"


# Action: place a block at exact coordinates
def action_place_block(params):
    # Which block to place, e.g. "cobblestone"
    block_name = params.get("block")
    # If the bot's position isn't available yet (e.g. right after a teleport),
    # wait a tenth of a second. This is your fix for the 'distanceTo' error.
    if bot.entity.position is None: #is buffer
        time.sleep(0.1)
    if not block_name:
        raise ValueError("'block' is required, e.g. 'cobblestone'")
    # Read x, y, z and make sure they're integers; otherwise report a clear error
    try:
        x, y, z = int(params["x"]), int(params["y"]), int(params["z"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("'x', 'y' and 'z' are required integers")

    # Turn the coordinates into a Vec3 position object
    target = Vec3(x, y, z)

    # CHECK 1: is the destination a valid, empty spot?
    target_block = bot.blockAt(target)
    if not target_block:
        raise ValueError("Target is outside the loaded world")
    if target_block.name not in AIR:
        raise ValueError(f"Target is already occupied by {target_block.name}")

    # CHECK 2: is it within the bot's reach?
    # The +0.5 offsets aim at the middle of the block, not its corner.
    dist = bot.entity.position.distanceTo(target.offset(0.5, 0.5, 0.5))
    if dist > 4.5:
        raise ValueError(f"Target is {dist:.1f} blocks away; must be within ~4.5")

    # CHECK 3: does the bot have that block in its inventory?
    # If not, ask the server to give it one (works in creative / with operator rights).
    # Small helper that searches the inventory and returns the item, or None.
    def find_item():
        for candidate in bot.inventory.items():
            if candidate.name == block_name:
                return candidate
        return None

    item = find_item()
    if item is None:
        # Not in inventory: type the /give command in chat
        bot.chat(f"/give {bot.username} {block_name} 1")
        # The server needs a moment to run the command and update the inventory,
        # so wait (up to ~2 seconds) and re-check instead of using it immediately.
        # Re-searching also gives us a real item object, which equip() requires.
        for _ in range(20):
            time.sleep(0.5)
            item = find_item()
            if item is not None:
                break
    # Still nothing: the give didn't work (not an operator, or a bad block name)
    if item is None:
        raise ValueError(
            f"No {block_name} in inventory and /give didn't work (is the bot an operator, and is the block name valid?)")


    # Minecraft can only place a block by clicking the face of an EXISTING block.
    # So check each of the 6 neighbors of the target and use the first solid one.
    for dx, dy, dz in NEIGHBORS:
        ref = bot.blockAt(target.offset(dx, dy, dz))
        # Solid means: exists, isn't air, and isn't liquid
        if ref and ref.name not in AIR and ref.name not in ("water", "lava"):
            # The face to click points from that neighbor back toward the target,
            # so it's the opposite of the offset we just used.
            face = Vec3(-dx, -dy, -dz)
            bot.equip(item, "hand")        # hold the block
            bot.placeBlock(ref, face)      # click the face; block appears at the target
            return f"Placed {block_name} at ({x}, {y}, {z})"

    # Went through all 6 neighbors and found nothing solid to click against
    raise ValueError("No solid adjacent block to place against (target is floating in air)")

#Action: break the block at a specific point.
def action_break_block(params):
    try:
        x, y, z = int(params["x"]), int(params["y"]), int(params["z"])
    except (KeyError, TypeError, ValueError):
            raise ValueError("'x', 'y' and 'z' are required integers")
    
    if bot.targetDigBlock:
        raise ValueError("Already digging a block")
    
    target = bot.blockAt(Vec3(x, y, z))
    # FIX: blockAt can return nothing (unloaded area), and there's nothing to break in air
    if not target or target.name in AIR:
        raise ValueError("There's no block to break there")
    if bot.entity.position.distanceTo(Vec3(x + 0.5, y + 0.5, z + 0.5)) > 4.5:
        raise ValueError("Target is out of reach (must be within ~4.5 blocks)")

    name = target.name        # save it before the block changes
    bot.dig(target)
    return f"Broke {name} at ({x}, {y}, {z})"

#The point of this action is to walk the bot to a specific location using pathfinding.
def action_move(params):
    # FIX: three separate int() conversions (int() with 3 arguments is invalid)
    try:
        x, y, z = int(params["x"]), int(params["y"]), int(params["z"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("'x', 'y' and 'z' are required integers")

    # FIX: actually call isMoving(). Before, the method itself was tested, which is always true.
    if bot.pathfinder.isMoving():
        raise ValueError("Already moving!")

    # (Plugin loading and Movements setup now happen once at startup, above.)
    goal = goals.GoalBlock(x, y, z)
    bot.pathfinder.setGoal(goal)   # starts moving and returns immediately

    # FIX: setGoal doesn't wait, so wait here until the bot arrives or we time out.
    # We check distance to the target instead of isMoving(), because isMoving()
    # can read false for a moment while the path is still being calculated.
    target_center = Vec3(x + 0.5, y + 0.5, z + 0.5)
    start = time.time()
    while time.time() - start < 75:
        if bot.entity.position.distanceTo(target_center) < 1.5:
            return f"Arrived at ({x}, {y}, {z})"
        time.sleep(0.25)

    # Took too long: cancel the goal so the bot stops trying, then report it
    bot.pathfinder.setGoal(None)
    raise ValueError(f"Timed out; couldn't reach ({x}, {y}, {z}) within 30 seconds")



# Action: fly the bot to coordinates (needs creative mode).
# NOTE: this is not in the ACTIONS dict below yet, so nothing can call it.
def fly_to_location(params):
    # Read and validate x, y, z, same as in action_place_block
    try:
        x, y, z = int(params["x"]), int(params["y"]), int(params["z"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("'x', 'y' and 'z' are required integers")
    target = Vec3(x, y, z)
    bot.creative.flyTo(target)     # fly to the target position
    bot.creative.stopFlying()      # then stop flying and drop back to normal movement



# The routing table: maps the "action" name in an incoming request to the
# Python function that handles it. To add a new capability, write a function
# above and add a line here.
ACTIONS = {
    "say": action_say,
    "place_block": action_place_block,
    "break_block": action_break_block,
    "move_to": action_move
}


# ---------- HTTP listener ----------
# The small web server that mcp_server.py talks to.

# 127.0.0.1 means "this computer only", so nothing else on the network can reach it
HOST = "127.0.0.1"
PORT = 8765   # the port; must match BOT_URL in minecraft_client.py


# Defines how to handle each incoming request
class BotHandler(BaseHTTPRequestHandler):
    # Called for every POST request
    def do_POST(self):
        try:
            # Read the request body: Content-Length says how many bytes to read
            length = int(self.headers.get("Content-Length", 0))
            # Convert the JSON text into a Python dict
            body = json.loads(self.rfile.read(length) or b"{}")

            # Look up which function handles the requested action
            action = body.get("action")
            handler = ACTIONS.get(action)
            # Unknown action name: reply with 400 (bad request)
            if handler is None:
                self._reply(400, {"ok": False, "error": f"Unknown action: {action}"})
                return

            # Run the action with its parameters and send back the result
            result = handler(body.get("params", {}))
            self._reply(200, {"ok": True, "result": result})
        # Any error inside an action becomes a readable error message for Claude
        except Exception as e:
            self._reply(500, {"ok": False, "error": str(e)})

    # Helper that sends a JSON response back to the caller
    def _reply(self, status, payload):
        data = json.dumps(payload).encode()          # dict -> JSON text -> bytes
        self.send_response(status)                   # HTTP status code (200, 400, 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)                       # the response body itself

    # Overrides the default behavior of printing a log line for every request
    def log_message(self, *args):
        pass


# Create the web server on our host/port using the handler above
server = ThreadingHTTPServer((HOST, PORT), BotHandler)
print(f"Bot listener running on http://{HOST}:{PORT}")
# Run forever. This blocks, which also keeps the whole script alive.
server.serve_forever()
