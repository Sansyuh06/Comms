"""
KMS Server (FastAPI)
====================
Quantum-Safe Tactical Communication System - Network KMS

This module wraps the existing KeyManagementService in a FastAPI REST API,
enabling networked clients and the router gatekeeper to interact with the
quantum key distribution infrastructure over HTTP.

ENDPOINTS:
----------
  POST /get_session_key  — Request a quantum-derived AES-256 session key
  GET  /link_status      — Query current quantum link health (GREEN/YELLOW/RED)
  POST /force_attack     — Trigger simulated Eve attack (demo only)
  POST /reset            — Reset KMS state for fresh demonstration

SECURITY NOTE:
--------------
The BB84 simulation is a classical emulation of quantum key distribution.
The AES-256-GCM encryption using derived keys is real and production-grade.

Run with:
    python kms_server.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import sys
import os
import socket
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kms.key_management_service import KeyManagementService


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class KeyRequest(BaseModel):
    """Request body for session key generation."""
    device_id: str
    force_attack: bool = False
    pqc: bool = False  # Extra credit: hybrid PQC mode


class KeyResponse(BaseModel):
    """Response for successful key generation."""
    key_hex: str
    qber: float
    status: str
    pqc_enabled: bool = False


class ErrorResponse(BaseModel):
    """Response when key generation fails (attack detected)."""
    error: str
    qber: float
    status: str


class LinkStatusResponse(BaseModel):
    """Response for link health query."""
    status: str
    qber: float
    total_keys_issued: int
    attacks_detected: int
    active_sessions: int


class AttackResponse(BaseModel):
    """Response for forced attack trigger."""
    status: str
    qber: float
    message: str


class ResetResponse(BaseModel):
    """Response for system reset."""
    status: str
    message: str


# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="QSTCS Key Management Service",
    description="Quantum-Safe Tactical Communication System — Networked KMS API",
    version="3.0.0",
)

# Enable CORS for all origins (demo/hackathon setting)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate the KMS (singleton for this server process)
kms = KeyManagementService()


# =============================================================================
# UTILITY
# =============================================================================

def get_lan_ip() -> str:
    """Attempt to discover the LAN IP address of this machine."""
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

@app.post("/get_session_key")
async def get_session_key(request: KeyRequest):
    """
    Generate and issue a quantum-derived session key.

    The KMS runs the BB84 QKD simulation, validates the QBER, derives an
    AES-256 key via HKDF-SHA256, and returns it to the requesting device.

    If an eavesdropper (Eve) is detected (QBER > 11%), key generation is
    blocked and the link status is set to RED.

    Demo key-sharing: The second device to request a key receives the same
    key as the first, enabling encrypted communication between them.
    """
    try:
        pqc_enabled = request.pqc
        key_bytes = kms.get_fresh_key(
            device_id=request.device_id,
            force_eve_attack=request.force_attack,
            pqc_enabled=pqc_enabled
        )

        health = kms.check_link_health()

        print(f"[KMS-API] ✓ Key issued to '{request.device_id}' | "
              f"QBER={health['last_qber']:.2%} | Status={health['status']}")

        return {
            "key_hex": key_bytes.hex(),
            "qber": health["last_qber"],
            "status": health["status"],
            "pqc_enabled": pqc_enabled,
        }

    except Exception as e:
        health = kms.check_link_health()

        print(f"[KMS-API] ✗ Key request BLOCKED for '{request.device_id}' | "
              f"QBER={health['last_qber']:.2%} | Reason: {str(e)[:60]}")

        return {
            "error": str(e),
            "qber": health["last_qber"],
            "status": health["status"],
        }


@app.get("/link_status")
async def link_status():
    """
    Query the current quantum link health.

    Returns the link status (GREEN/YELLOW/RED), last measured QBER,
    total keys issued, attacks detected, and active session count.

    This endpoint is polled by the router gatekeeper script to decide
    whether to allow or block chat traffic through the firewall.
    """
    health = kms.check_link_health()
    return {
        "status": health["status"],
        "qber": health["last_qber"],
        "total_keys_issued": health["total_keys_issued"],
        "attacks_detected": health["attacks_detected"],
        "active_sessions": health["active_sessions"],
    }


@app.post("/force_attack")
async def force_attack():
    """
    Trigger a simulated Eve (eavesdropper) attack.

    This runs a BB84 key exchange with Eve intercepting all qubits,
    causing QBER ≈ 25% and flipping the link status to RED.

    Used during live demonstrations to show how the system detects
    quantum channel compromise and how the router responds.
    """
    try:
        # Clear cached key so the key-sharing logic doesn't short-circuit
        kms._last_key = None
        kms._last_key_device = None
        kms.get_fresh_key("Eve_Attack_Trigger", force_eve_attack=True)
        # Should not reach here — attack should raise exception
        health = kms.check_link_health()
        return {
            "status": health["status"],
            "qber": health["last_qber"],
            "message": "Attack triggered but key was unexpectedly issued",
        }
    except Exception as e:
        health = kms.check_link_health()
        print(f"[KMS-API] ⚠️  ATTACK TRIGGERED | Status={health['status']} | "
              f"QBER={health['last_qber']:.2%}")
        return {
            "status": health["status"],
            "qber": health["last_qber"],
            "message": f"Attack detected: {str(e)[:80]}",
        }


@app.post("/reset")
async def reset_system():
    """
    Reset the KMS to initial state for a fresh demonstration.

    Clears all session records, metrics, and cached keys.
    Link status returns to GREEN.
    """
    kms.reset_for_demo()
    print("[KMS-API] 🔄 System reset complete")
    return {
        "status": "reset_complete",
        "message": "KMS state cleared. Link status: GREEN. Ready for new demo.",
    }


@app.on_event("startup")
async def startup_banner():
    """Print discovery information on server startup."""
    lan_ip = get_lan_ip()
    print()
    print("=" * 70)
    print("  QSTCS Key Management Service — ONLINE")
    print("=" * 70)
    print(f"  Local:    http://127.0.0.1:8000")
    print(f"  LAN:      http://{lan_ip}:8000")
    print(f"  Docs:     http://{lan_ip}:8000/docs")
    print()
    print("  Endpoints:")
    print("    POST /get_session_key  — Request quantum-derived key")
    print("    GET  /link_status      — Query link health (router polls this)")
    print("    POST /force_attack     — Simulate Eve attack (demo)")
    print("    POST /reset            — Reset system state")
    print("=" * 70)
    print()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "kms_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
