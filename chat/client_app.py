"""
Terminal chat client with AES-GCM encryption and KMS integration.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Dict

import httpx
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    if not value and default is not None:
        return default
    return value


def _bool_prompt(text: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{text} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value.startswith("y")


def _kms_post(kms_base: str, path: str, payload: Dict[str, object]) -> Dict[str, object]:
    url = f"{kms_base}{path}"
    response = httpx.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def _kms_get(kms_base: str, path: str) -> Dict[str, object]:
    url = f"{kms_base}{path}"
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


async def _fetch_status(kms_base: str):
    try:
        return await asyncio.to_thread(_kms_get, kms_base, "/link_status")
    except Exception as exc:
        print(f"[status] failed: {exc}")
        return None


async def chat_loop(user_id: str, peer_id: str, session_id: str, aes_key: bytes, ws_url: str, kms_base: str):
    if "?" in ws_url:
        ws_url = f"{ws_url}&user_id={user_id}"
    else:
        ws_url = f"{ws_url}?user_id={user_id}"

    aesgcm = AESGCM(aes_key)

    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected. Type messages, /status, or /quit.")

            async def sender():
                while True:
                    text = await asyncio.to_thread(input, "")
                    text = text.strip()
                    if not text:
                        continue

                    if text == "/quit":
                        await websocket.close()
                        return

                    if text == "/status":
                        status = await _fetch_status(kms_base)
                        if status:
                            print(
                                f"[link] {status['status']} qber={status['qber']:.3f} "
                                f"eve={status.get('eve_mode') or status.get('eve_active', False)} level={status['escalation_level']}"
                            )
                        continue

                    nonce = os.urandom(12)
                    ct = aesgcm.encrypt(nonce, text.encode("utf-8"), None)
                    ciphertext, tag = ct[:-16], ct[-16:]

                    payload = {
                        "session_id": session_id,
                        "from": user_id,
                        "to": peer_id,
                        "nonce": base64.b64encode(nonce).decode("ascii"),
                        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                        "tag": base64.b64encode(tag).decode("ascii"),
                        "timestamp": int(time.time()),
                    }
                    await websocket.send(json.dumps(payload))

            async def receiver():
                async for raw in websocket:
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if data.get("from") == user_id:
                        continue

                    try:
                        nonce = base64.b64decode(data["nonce"])
                        ciphertext = base64.b64decode(data["ciphertext"])
                        tag = base64.b64decode(data["tag"])
                        plaintext = aesgcm.decrypt(nonce, ciphertext + tag, None)
                        print(f"[{data.get('from')}] > {plaintext.decode('utf-8')}")
                    except Exception as exc:
                        print(f"[decrypt] failed: {exc}")

            send_task = asyncio.create_task(sender())
            recv_task = asyncio.create_task(receiver())
            done, pending = await asyncio.wait(
                [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    except Exception as exc:
        print(
            "Connection failed. If the router is in RED/LOCKDOWN, "
            "chat traffic may be blocked."
        )
        print(f"Details: {exc}")


def main():
    user_id = _prompt("User id")
    peer_id = _prompt("Peer id")
    kms_base = _prompt("KMS base URL", "http://192.168.1.100:8000").rstrip("/")
    ws_url = _prompt("Chat WebSocket URL", "ws://192.168.1.100:8765")

    create_new = _bool_prompt("Create new session", True)
    use_hybrid = False

    if create_new:
        use_hybrid = _bool_prompt("Use hybrid (BB84 + PQC stub)", False)
        resp = _kms_post(
            kms_base,
            "/create_session",
            {"client_a": user_id, "client_b": peer_id, "use_hybrid": use_hybrid},
        )
        session_id = resp["session_id"]
        print(
            f"Session {session_id} created. status={resp['status']} qber={resp['qber']:.3f}"
        )
    else:
        session_id = _prompt("Existing session_id")

    key_resp = _kms_post(
        kms_base,
        "/get_key",
        {"session_id": session_id, "client_id": user_id},
    )
    aes_key = base64.b64decode(key_resp["aes_key_b64"])

    asyncio.run(chat_loop(user_id, peer_id, session_id, aes_key, ws_url, kms_base))


if __name__ == "__main__":
    main()
