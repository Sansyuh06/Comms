"""
Key Management Service (KMS)
============================
Quantum-Safe Tactical Communication System

Central authority for cryptographic key lifecycle management. Bridges the
quantum key distribution layer (BB84 simulator) with AES-256-GCM encryption.

SESSION-BASED KEY DISTRIBUTION:
-------------------------------
Keys are issued per (initiator, peer) session pair:
  1. Device A creates a session targeting Device B  →  BB84 runs, key derived
  2. Device B joins the session                     →  gets the same key
Both devices must explicitly participate. No cached key tricks.

SECURITY MODEL:
---------------
- KMS operates within a trusted security perimeter
- All key material exists only in volatile memory
- QBER threshold enforcement prevents compromised key issuance
- Session keys are bound to specific device pairs

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import os
import uuid


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class LinkStatus(Enum):
    """Quantum link health status."""
    GREEN = "GREEN"     # Link secure, keys can be issued
    YELLOW = "YELLOW"   # Elevated QBER, proceed with caution
    RED = "RED"         # Attack detected, key issuance blocked


@dataclass
class Session:
    """A paired key exchange session between two devices."""
    session_id: str
    initiator: str
    peer: str
    key: bytes
    qber: float
    status: LinkStatus
    created_at: datetime
    joined: bool = False          # True once the peer has retrieved the key
    messages_encrypted: int = 0
    pqc_enabled: bool = False


@dataclass
class KMSMetrics:
    """KMS operational metrics for monitoring."""
    total_keys_issued: int = 0
    total_sessions: int = 0
    attacks_detected: int = 0
    active_sessions: int = 0
    last_qber: float = 0.0
    link_status: LinkStatus = LinkStatus.GREEN
    qber_history: list = field(default_factory=list)


# =============================================================================
# KEY MANAGEMENT SERVICE
# =============================================================================

class KeyManagementService:
    """
    Central Key Management Service for QSTCS.

    Handles all key generation, derivation, and distribution for the
    tactical communication network. Keys are managed per session —
    each session pairs exactly two devices.

    Thread Safety:
        All operations are thread-safe using internal locks.

    Usage:
        >>> kms = KeyManagementService()
        >>> session = kms.create_session("Alpha", "Bravo")
        >>> key_a = session['key']
        >>> key_b = kms.join_session(session['session_id'], "Bravo")['key']
        >>> assert key_a == key_b
    """

    def __init__(self, qber_threshold: float = QBER_SECURITY_THRESHOLD):
        self._lock = threading.Lock()
        self._sessions: Dict[str, Session] = {}          # session_id → Session
        self._pair_index: Dict[frozenset, str] = {}       # {dev_a, dev_b} → session_id
        self._metrics = KMSMetrics()
        self._qber_threshold = qber_threshold
        self._eve_active = False  # Global Eve toggle for live attack simulation

        print(f"[KMS] Key Management Service initialized")
        print(f"[KMS] QBER security threshold: {qber_threshold:.1%}")

    # =========================================================================
    # SESSION-BASED KEY EXCHANGE
    # =========================================================================

    def create_session(
        self,
        initiator: str,
        peer: str,
        num_bits: int = 512,
        pqc_enabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new key exchange session between two devices.

        Runs BB84 QKD simulation, validates QBER, derives an AES-256 key
        via HKDF-SHA256, and stores it in a session bound to (initiator, peer).

        Args:
            initiator: Device ID of the session creator
            peer: Device ID of the intended communication partner
            num_bits: Number of qubits for BB84 (default: 512)
            pqc_enabled: If True, apply hybrid PQC key derivation

        Returns:
            Dict with session_id, key (bytes), qber, status

        Raises:
            Exception: If QBER exceeds threshold (attack detected)
            ValueError: If session already exists for this pair
        """
        with self._lock:
            pair_key = frozenset({initiator, peer})

            # Check if an active session already exists for this pair
            if pair_key in self._pair_index:
                existing_id = self._pair_index[pair_key]
                existing = self._sessions[existing_id]
                # Return existing session if peer hasn't joined yet
                if not existing.joined:
                    print(f"[KMS] Session {existing_id[:8]}... already exists "
                          f"for ({initiator}, {peer})")
                    return self._session_to_dict(existing)

            # Determine if Eve is active (global toggle or channel noise)
            eve_present = self._eve_active

            # ---- PHASE 1: BB84 Quantum Key Distribution ----
            print(f"\n[KMS] Creating session: {initiator} ↔ {peer}")
            print(f"[KMS] Executing BB84 protocol ({num_bits} qubits)...")

            raw_key, qber, attack_detected = simulate_bb84(
                num_bits=num_bits,
                eve_present=eve_present,
                eve_intercept_rate=1.0 if eve_present else 0.0
            )

            self._metrics.last_qber = qber
            self._metrics.qber_history.append({
                "timestamp": datetime.now().isoformat(),
                "qber": qber,
                "eve_present": eve_present,
            })
            print(f"[KMS] BB84 complete. QBER = {qber:.2%}")

            # ---- PHASE 2: Security Validation ----
            if attack_detected or qber > self._qber_threshold:
                self._metrics.link_status = LinkStatus.RED
                self._metrics.attacks_detected += 1
                print(f"[KMS] ⚠️  ATTACK DETECTED! QBER = {qber:.2%}")
                print(f"[KMS] Key issuance BLOCKED. Link status: RED")
                raise Exception(
                    f"QKD link compromised! QBER={qber:.1%} exceeds "
                    f"{self._qber_threshold:.0%} threshold. "
                    f"Session for {initiator} ↔ {peer} aborted."
                )

            # Update link status
            if qber < 0.05:
                self._metrics.link_status = LinkStatus.GREEN
            elif qber < self._qber_threshold:
                self._metrics.link_status = LinkStatus.YELLOW

            # ---- PHASE 3: Key Derivation (HKDF-SHA256) ----
            session_id = uuid.uuid4().hex[:16]
            info_str = f"QSTCS-Session-{session_id}-{initiator}-{peer}"

            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=info_str.encode(),
                backend=default_backend()
            )
            session_key = hkdf.derive(raw_key)

            # ---- PHASE 3b: Hybrid PQC (optional) ----
            if pqc_enabled:
                kyber_shared_secret = os.urandom(32)
                hybrid_input = session_key + kyber_shared_secret

                hybrid_hkdf = HKDF(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=None,
                    info=b"QSTCS-Hybrid-PQC",
                    backend=default_backend()
                )
                session_key = hybrid_hkdf.derive(hybrid_input)
                print(f"[KMS] 🧬 Hybrid PQC derivation applied")

            # ---- PHASE 4: Store Session ----
            session = Session(
                session_id=session_id,
                initiator=initiator,
                peer=peer,
                key=session_key,
                qber=qber,
                status=self._metrics.link_status,
                created_at=datetime.now(),
                pqc_enabled=pqc_enabled,
            )

            self._sessions[session_id] = session
            self._pair_index[pair_key] = session_id
            self._metrics.total_sessions += 1
            self._metrics.total_keys_issued += 1
            self._metrics.active_sessions = sum(
                1 for s in self._sessions.values() if s.status != LinkStatus.RED
            )

            print(f"[KMS] ✓ Session {session_id} created")
            print(f"[KMS]   {initiator} ↔ {peer} | QBER={qber:.2%}")
            print(f"[KMS]   Key: {session_key.hex()[:32]}...")

            return self._session_to_dict(session)

    def join_session(self, session_id: str, device_id: str) -> Dict[str, Any]:
        """
        Join an existing session and retrieve the shared key.

        The peer device calls this to get the same key that was generated
        when the session was created.

        Args:
            session_id: The session ID returned by create_session
            device_id: Device ID of the joining party

        Returns:
            Dict with key (bytes), qber, status

        Raises:
            ValueError: If session not found or device is not the expected peer
        """
        with self._lock:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self._sessions[session_id]

            # Validate the device is the expected peer (or the initiator re-fetching)
            if device_id != session.peer and device_id != session.initiator:
                raise ValueError(
                    f"Device '{device_id}' is not a participant in session {session_id}. "
                    f"Expected '{session.initiator}' or '{session.peer}'."
                )

            if session.status == LinkStatus.RED:
                raise Exception(
                    f"Session {session_id} was invalidated due to quantum link compromise"
                )

            session.joined = True
            self._metrics.total_keys_issued += 1

            print(f"[KMS] ✓ '{device_id}' joined session {session_id}")
            return self._session_to_dict(session)

    def get_session_by_pair(self, device_a: str, device_b: str) -> Optional[Dict[str, Any]]:
        """Look up the active session between two devices."""
        with self._lock:
            pair_key = frozenset({device_a, device_b})
            if pair_key in self._pair_index:
                session_id = self._pair_index[pair_key]
                session = self._sessions[session_id]
                if session.status != LinkStatus.RED:
                    return self._session_to_dict(session)
            return None

    # =========================================================================
    # BACKWARD COMPATIBILITY — get_fresh_key (used by main.py, tests)
    # =========================================================================

    def get_fresh_key(
        self,
        device_id: str,
        force_eve_attack: bool = False,
        num_bits: int = 512,
        pqc_enabled: bool = False,
        peer_id: str = "_broadcast_"
    ) -> bytes:
        """
        Legacy interface: generate a key for a device.

        For backward compatibility with main.py and tests. Internally
        creates or joins a session with the given peer_id.
        """
        # Temporarily enable Eve if forced
        old_eve = self._eve_active
        if force_eve_attack:
            self._eve_active = True

        try:
            # Check if a session exists that this device can join
            pair_key = frozenset({device_id, peer_id})
            with self._lock:
                if pair_key in self._pair_index:
                    sid = self._pair_index[pair_key]
                    session = self._sessions[sid]
                    if not session.joined and device_id == session.peer:
                        session.joined = True
                        self._metrics.total_keys_issued += 1
                        print(f"[KMS] ✓ '{device_id}' joined existing session {sid}")
                        return session.key

            # Create new session
            result = self.create_session(
                initiator=device_id,
                peer=peer_id,
                num_bits=num_bits,
                pqc_enabled=pqc_enabled,
            )
            return result['key']

        finally:
            self._eve_active = old_eve

    # =========================================================================
    # EVE / ATTACK CONTROL
    # =========================================================================

    def activate_eve(self) -> None:
        """Activate the eavesdropper on the quantum channel."""
        with self._lock:
            self._eve_active = True
            print("[KMS] ⚠️  Eve is now ACTIVE on the quantum channel")

    def deactivate_eve(self) -> None:
        """Deactivate the eavesdropper."""
        with self._lock:
            self._eve_active = False
            print("[KMS] ✓ Eve deactivated")

    @property
    def eve_active(self) -> bool:
        return self._eve_active

    def trigger_attack(self) -> Dict[str, Any]:
        """
        Run a BB84 exchange with Eve active to flip link status to RED.

        Returns the resulting QBER and status.
        """
        self._eve_active = True
        try:
            self.create_session(
                initiator="_attack_probe_",
                peer="_attack_target_",
                num_bits=512,
            )
            # Shouldn't reach here
            health = self.check_link_health()
            return {"status": health["status"], "qber": health["last_qber"]}
        except Exception:
            health = self.check_link_health()
            return {
                "status": health["status"],
                "qber": health["last_qber"],
                "attacks_detected": health["attacks_detected"],
            }

    # =========================================================================
    # MONITORING
    # =========================================================================

    def check_link_health(self) -> Dict[str, Any]:
        """Get current link health status and metrics."""
        with self._lock:
            return {
                'status': self._metrics.link_status.value,
                'total_keys_issued': self._metrics.total_keys_issued,
                'total_sessions': self._metrics.total_sessions,
                'attacks_detected': self._metrics.attacks_detected,
                'active_sessions': self._metrics.active_sessions,
                'last_qber': self._metrics.last_qber,
                'eve_active': self._eve_active,
                'qber_history': list(self._metrics.qber_history[-20:]),
            }

    def list_sessions(self) -> list:
        """List all active sessions (no key material exposed)."""
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "initiator": s.initiator,
                    "peer": s.peer,
                    "qber": s.qber,
                    "status": s.status.value,
                    "joined": s.joined,
                    "created_at": s.created_at.isoformat(),
                    "pqc_enabled": s.pqc_enabled,
                }
                for s in self._sessions.values()
            ]

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session and revoke its key."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.status = LinkStatus.RED
                # Remove from pair index
                pair_key = frozenset({session.initiator, session.peer})
                self._pair_index.pop(pair_key, None)
                del self._sessions[session_id]
                self._metrics.active_sessions = sum(
                    1 for s in self._sessions.values() if s.status != LinkStatus.RED
                )
                print(f"[KMS] Session {session_id} invalidated")
                return True
            return False

    def reset(self) -> None:
        """Reset all KMS state."""
        with self._lock:
            self._sessions.clear()
            self._pair_index.clear()
            self._metrics = KMSMetrics()
            self._eve_active = False
            print("[KMS] All state cleared")

    # Legacy alias
    def reset_for_demo(self) -> None:
        self.reset()

    # =========================================================================
    # INTERNALS
    # =========================================================================

    def _session_to_dict(self, session: Session) -> Dict[str, Any]:
        """Convert a Session to a response dict."""
        return {
            "session_id": session.session_id,
            "key": session.key,
            "key_hex": session.key.hex(),
            "qber": session.qber,
            "status": session.status.value,
            "initiator": session.initiator,
            "peer": session.peer,
            "joined": session.joined,
            "pqc_enabled": session.pqc_enabled,
        }


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Key Management Service — Verification")
    print("=" * 60)

    kms = KeyManagementService()

    # Test 1: Create session
    print("\n[TEST 1] Create session Alpha ↔ Bravo")
    print("-" * 40)
    session = kms.create_session("Alpha", "Bravo")
    print(f"  Session ID: {session['session_id']}")
    print(f"  Key (hex): {session['key_hex'][:32]}...")
    print(f"  QBER: {session['qber']:.2%}")
    print(f"  Status: {session['status']}")

    # Test 2: Peer joins
    print("\n[TEST 2] Bravo joins session")
    print("-" * 40)
    joined = kms.join_session(session['session_id'], "Bravo")
    print(f"  Keys match: {session['key'] == joined['key']}")
    print(f"  Joined: {joined['joined']}")

    # Test 3: Attack detection
    print("\n[TEST 3] Attack detection")
    print("-" * 40)
    result = kms.trigger_attack()
    print(f"  Status: {result['status']}")
    print(f"  QBER: {result['qber']:.2%}")
    print(f"  Attacks: {result['attacks_detected']}")

    # Test 4: Health
    print("\n[TEST 4] Link health")
    print("-" * 40)
    health = kms.check_link_health()
    for k, v in health.items():
        if k != 'qber_history':
            print(f"  {k}: {v}")
