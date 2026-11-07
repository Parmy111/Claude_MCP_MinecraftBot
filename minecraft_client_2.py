import json
import httpx
import websockets


MINECRAFT_URL = "ws://localhost:25585"
SECRET = "Placeholder" #Your SECERET should go here.
BOT_URL = "http://127.0.0.1:8765"


async def call_minecraft(method, params=None):
    async with websockets.connect(
        MINECRAFT_URL,
        additional_headers={"Authorization": f"Bearer {SECRET}"}
    ) as websocket:
        request = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            request["params"] = params

        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        return json.loads(response)


async def send_to_bot(action, params):
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(BOT_URL, json={"action": action, "params": params})
        return response.json()

#Tests