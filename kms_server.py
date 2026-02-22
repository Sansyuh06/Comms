"""
KMS Server (FastAPI)
====================
Quantum-Safe Tactical Communication System — Network KMS

REST API for the Key Management Service. All key operations go through
session-based pairing: one device creates a session, the other joins it.

ENDPOINTS:
----------
  POST /create_session    — Create a paired key exchange session (runs BB84)
  POST /join_session      — Join an existing session and get the shared key
  GET  /link_status       — Query quantum link health (GREEN/YELLOW/RED)
  GET  /sessions          — List active sessions (no key material)
  POST /activate_eve      — Turn on eavesdropper (quantum channel attack)
  POST /deactivate_eve    — Turn off eavesdropper
  POST /trigger_attack    — Run one BB84 probe with Eve to flip status to RED
  POST /reset             — Clear all state

Run with:
    python kms_server.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import sys
import os
import socket
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kms.key_management_service import KeyManagementService


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateSessionRequest(BaseModel):
    initiator: str
    peer: str
    pqc: bool = False

class JoinSessionRequest(BaseModel):
    session_id: str
    device_id: str

class LegacyKeyRequest(BaseModel):
    """Backward compat for simple key requests."""
    device_id: str
    peer_id: str = "_broadcast_"
    force_attack: bool = False
    pqc: bool = False


# =============================================================================
# APPLICATION
# =============================================================================

app = FastAPI(
    title="QSTCS Key Management Service",
    description="Session-based quantum key distribution API",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kms = KeyManagementService()


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.post("/create_session")
async def create_session(req: CreateSessionRequest):
    """
    Create a key exchange session between two devices.

    Runs BB84 QKD, validates QBER, derives AES-256 key via HKDF.
    Returns the session ID and key to the initiator.
    The peer must call /join_session to get the same key.
    """
    try:
        result = kms.create_session(
            initiator=req.initiator,
            peer=req.peer,
            pqc_enabled=req.pqc,
        )
        return {
            "session_id": result["session_id"],
            "key_hex": result["key_hex"],
            "qber": result["qber"],
            "status": result["status"],
            "initiator": result["initiator"],
            "peer": result["peer"],
            "pqc_enabled": result["pqc_enabled"],
        }
    except Exception as e:
        health = kms.check_link_health()
        return {
            "error": str(e),
            "qber": health["last_qber"],
            "status": health["status"],
        }


@app.post("/join_session")
async def join_session(req: JoinSessionRequest):
    """
    Join an existing session and retrieve the shared key.

    The peer device calls this with the session_id from /create_session.
    """
    try:
        result = kms.join_session(req.session_id, req.device_id)
        return {
            "session_id": result["session_id"],
            "key_hex": result["key_hex"],
            "qber": result["qber"],
            "status": result["status"],
            "joined": result["joined"],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/get_session_key")
async def get_session_key(req: LegacyKeyRequest):
    """
    Simplified key request (backward compatible).

    Creates or joins a session for the device and its peer.
    """
    try:
        old_eve = kms.eve_active
        if req.force_attack:
            kms.activate_eve()

        key_bytes = kms.get_fresh_key(
            device_id=req.device_id,
            peer_id=req.peer_id,
            pqc_enabled=req.pqc,
        )

        if req.force_attack:
            if not old_eve:
                kms.deactivate_eve()

        health = kms.check_link_health()
        return {
            "key_hex": key_bytes.hex(),
            "qber": health["last_qber"],
            "status": health["status"],
        }
    except Exception as e:
        health = kms.check_link_health()
        return {
            "error": str(e),
            "qber": health["last_qber"],
            "status": health["status"],
        }


@app.get("/link_status")
async def link_status():
    """Current quantum link health. Polled by the router gatekeeper."""
    health = kms.check_link_health()
    return {
        "status": health["status"],
        "qber": health["last_qber"],
        "total_keys_issued": health["total_keys_issued"],
        "total_sessions": health["total_sessions"],
        "attacks_detected": health["attacks_detected"],
        "active_sessions": health["active_sessions"],
        "eve_active": health["eve_active"],
    }


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (key material is NOT included)."""
    return {"sessions": kms.list_sessions()}


@app.post("/activate_eve")
async def activate_eve():
    """Turn on the eavesdropper. All future BB84 exchanges will detect Eve."""
    kms.activate_eve()
    return {"eve_active": True, "message": "Eve is now intercepting the quantum channel."}


@app.post("/deactivate_eve")
async def deactivate_eve():
    """Turn off the eavesdropper."""
    kms.deactivate_eve()
    return {"eve_active": False, "message": "Eve deactivated. Quantum channel clear."}


@app.post("/trigger_attack")
async def trigger_attack():
    """
    Run a single BB84 probe with Eve active.
    Flips the link status to RED so the router can block traffic.
    """
    result = kms.trigger_attack()
    return {
        "status": result["status"],
        "qber": result["qber"],
        "attacks_detected": result.get("attacks_detected", 0),
        "message": "Attack detected — link status RED. Router will block chat traffic.",
    }


@app.post("/reset")
async def reset_system():
    """Clear all sessions, metrics, and Eve state."""
    kms.reset()
    return {"status": "reset_complete", "message": "All state cleared. Link GREEN."}


@app.on_event("startup")
async def startup_banner():
    lan_ip = get_lan_ip()
    print()
    print("=" * 70)
    print("  QSTCS Key Management Service v3.1 — ONLINE")
    print("=" * 70)
    print(f"  Local:  http://127.0.0.1:8000")
    print(f"  LAN:    http://{lan_ip}:8000")
    print(f"  Docs:   http://{lan_ip}:8000/docs")
    print()
    print("  Session-based key distribution:")
    print("    POST /create_session   — Initiator creates session (runs BB84)")
    print("    POST /join_session     — Peer joins and gets shared key")
    print("    GET  /link_status      — Router polls this for GREEN/RED")
    print("    POST /activate_eve     — Turn on eavesdropper")
    print("    POST /trigger_attack   — Force RED status")
    print("    POST /reset            — Clear everything")
    print("=" * 70)
    print()


if __name__ == "__main__":
    uvicorn.run("kms_server:app", host="0.0.0.0", port=8000, log_level="info")
