"""
WebSocket chat relay server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict
from urllib.parse import urlparse, parse_qs

import websockets

logging.basicConfig(level=logging.INFO, format="[chat_server] %(message)s")


class ChatServer:
    def __init__(self) -> None:
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}

    async def handler(self, websocket: websockets.WebSocketServerProtocol, path: str):
        user_id = self._user_id_from_path(path)
        if not user_id:
            user_id = await self._read_hello(websocket)
            if not user_id:
                await websocket.close()
                return

        await self._register(user_id, websocket)

        try:
            async for message in websocket:
                await self._handle_message(user_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._unregister(user_id, websocket)

    def _user_id_from_path(self, path: str) -> str | None:
        parsed = urlparse(path)
        qs = parse_qs(parsed.query or "")
        if "user_id" in qs and qs["user_id"]:
            return qs["user_id"][0]
        return None

    async def _read_hello(self, websocket: websockets.WebSocketServerProtocol) -> str | None:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
        except asyncio.TimeoutError:
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if isinstance(data, dict) and "user_id" in data:
            return str(data["user_id"])
        return None

    async def _register(self, user_id: str, websocket: websockets.WebSocketServerProtocol):
        if user_id in self.clients:
            try:
                await self.clients[user_id].close()
            except Exception:
                pass
        self.clients[user_id] = websocket
        logging.info("User connected: %s", user_id)

    async def _unregister(self, user_id: str, websocket: websockets.WebSocketServerProtocol):
        current = self.clients.get(user_id)
        if current is websocket:
            self.clients.pop(user_id, None)
            logging.info("User disconnected: %s", user_id)

    async def _handle_message(self, from_user: str, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logging.info("Invalid JSON from %s", from_user)
            return

        if not isinstance(data, dict):
            return

        to_user = data.get("to")
        session_id = data.get("session_id")
        timestamp = data.get("timestamp")

        logging.info("Relay session=%s from=%s to=%s ts=%s", session_id, from_user, to_user, timestamp)

        if to_user and to_user in self.clients:
            await self.clients[to_user].send(json.dumps(data))
            return

        for user_id, ws in list(self.clients.items()):
            if user_id != from_user:
                try:
                    await ws.send(json.dumps(data))
                except Exception:
                    pass


def main():
    import argparse

    parser = argparse.ArgumentParser(description="WebSocket chat relay server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ChatServer()

    async def runner():
        async with websockets.serve(server.handler, args.host, args.port):
            logging.info("Chat server listening on %s:%s", args.host, args.port)
            await asyncio.Future()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
