"""
Key Management Service (KMS) core logic for the quantum-aware secure chat demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Optional
import base64
import os
import threading
import time
import uuid

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from quantum_engine.bb84_simulator import run_bb84_session

LOW_QBER_THRESHOLD = 0.05
SECURE_QBER_THRESHOLD = 0.11


@dataclass
class SessionRecord:
    session_id: str
    key: bytes
    qber: float
    status: str
    clients: Set[str]
    created_at: float
    compromised: bool
    use_hybrid: bool
    pqc_secret: Optional[bytes]
    is_control: bool = False


class KeyManagementService:
    def __init__(
        self,
        port_pool: Optional[list] = None,
        ip_pool: Optional[list] = None,
        network_pool: Optional[list] = None,
    ) -> None:
        self.sessions: Dict[str, SessionRecord] = {}
        self.eve_mode: bool = False
        self.attacks_detected: int = 0
        self.total_sessions: int = 0
        self.total_keys_issued: int = 0

        self.last_qber: float = 0.0
        self.last_status: str = "GREEN"
        self.last_attack_detected: bool = False

        # legacy attribute used by some tests
        self.link_status: str = "GREEN"

        self.escalation_level: int = 1

        self.port_pool = port_pool or [1919, 1920, 1921, 1922, 1923, 1924, 1925]
        self.ip_pool = ip_pool or ["192.168.1.100", "192.168.1.150"]
        self.network_pool = network_pool or ["192.168.1.0/24", "192.168.2.0/24"]

        self.current_port = self.port_pool[0]
        self.current_ip = self.ip_pool[0]
        self.current_network = self.network_pool[0]

        self.burned_ports: Set[int] = set()
        self.burned_ips: Set[str] = set()
        self.burned_networks: Set[str] = set()

        # shared demo key: the last successfully issued key so a second
        # device can retrieve the same key without a new BB84 round
        self._last_key: Optional[bytes] = None

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _status_from_qber(self, qber: float, attack_detected: bool) -> str:
        if attack_detected or qber >= SECURE_QBER_THRESHOLD:
            return "RED"
        if qber < LOW_QBER_THRESHOLD:
            return "GREEN"
        return "YELLOW"

    def _derive_aes_key(self, raw_key: bytes, pqc_secret: Optional[bytes]) -> bytes:
        material = raw_key + (pqc_secret or b"")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"bb84-demo-aes-key",
        )
        return hkdf.derive(material)

    def _next_available(self, pool: list, burned: Set) -> Optional[object]:
        for item in pool:
            if item not in burned:
                return item
        return None

    def _update_escalation(self, status: str) -> None:
        if status != "RED":
            return

        if self.escalation_level == 1:
            self.burned_ports.add(self.current_port)
            next_port = self._next_available(self.port_pool, self.burned_ports)
            if next_port is not None:
                self.current_port = next_port
                return
            self.escalation_level = 2
            self.burned_ports.clear()
            self.current_port = self.port_pool[0]
            return

        if self.escalation_level == 2:
            self.burned_ips.add(self.current_ip)
            next_ip = self._next_available(self.ip_pool, self.burned_ips)
            if next_ip is not None:
                self.current_ip = next_ip
                return
            self.escalation_level = 3
            self.burned_ips.clear()
            self.current_ip = self.ip_pool[0]
            return

        if self.escalation_level == 3:
            self.burned_networks.add(self.current_network)
            next_net = self._next_available(self.network_pool, self.burned_networks)
            if next_net is not None:
                self.current_network = next_net
                return
            self.escalation_level = 4

    # ------------------------------------------------------------------
    # session-based API (used by kms/kms_server.py and test_e2e.py)
    # ------------------------------------------------------------------

    def create_session(
        self,
        client_a: str = None,
        client_b: str = None,
        use_hybrid: bool = False,
        # aliases used by root kms_server.py and dashboard
        initiator: str = None,
        peer: str = None,
        pqc_enabled: bool = False,
    ) -> Dict[str, object]:
        # resolve aliased parameter names
        client_a = client_a or initiator or "unknown_a"
        client_b = client_b or peer or "unknown_b"
        use_hybrid = use_hybrid or pqc_enabled

        session_id = uuid.uuid4().hex
        bb84 = run_bb84_session(session_id, num_bits=256, eve=self.eve_mode, rng_seed=None)

        raw_key: bytes = bb84["raw_key"]
        qber: float = float(bb84["qber"])
        attack_detected: bool = bool(bb84["attack_detected"])

        pqc_secret = os.urandom(32) if use_hybrid else None
        aes_key = self._derive_aes_key(raw_key, pqc_secret)
        status = self._status_from_qber(qber, attack_detected)

        record = SessionRecord(
            session_id=session_id,
            key=aes_key,
            qber=qber,
            status=status,
            clients={client_a, client_b},
            created_at=time.time(),
            compromised=status == "RED",
            use_hybrid=use_hybrid,
            pqc_secret=pqc_secret,
            is_control=False,
        )

        with self._lock:
            self.sessions[session_id] = record
            self.total_sessions += 1
            self.total_keys_issued += 1
            if attack_detected or status == "RED":
                self.attacks_detected += 1

            self.last_qber = qber
            self.last_status = status
            self.link_status = status
            self.last_attack_detected = attack_detected

            if status != "RED":
                self._last_key = aes_key

            self._update_escalation(status)

        if status == "RED":
            raise Exception(f"Quantum channel compromised — QBER={qber:.2%}. Session aborted.")

        return {
            "session_id": session_id,
            "key": aes_key,
            "key_hex": aes_key.hex(),
            "status": status,
            "qber": qber,
            "attack_detected": attack_detected,
            "use_hybrid": use_hybrid,
            "initiator": client_a,
            "peer": client_b,
            "pqc_enabled": use_hybrid,
        }

    def join_session(self, session_id: str, device_id: str) -> Dict[str, object]:
        with self._lock:
            record = self.sessions.get(session_id)
        if record is None:
            raise ValueError(f"Unknown session_id: {session_id}")
        # allow any device to join for demo purposes
        record.clients.add(device_id)
        return {
            "session_id": session_id,
            "key": record.key,
            "key_hex": record.key.hex(),
            "status": record.status,
            "qber": record.qber,
            "joined": True,
        }

    def get_key(self, session_id: str, client_id: str) -> Dict[str, object]:
        with self._lock:
            record = self.sessions.get(session_id)
            if record is None:
                raise KeyError("unknown session")
            if client_id not in record.clients:
                raise PermissionError("client not in session")
            aes_key = record.key

        return {
            "session_id": session_id,
            "client_id": client_id,
            "aes_key_b64": base64.b64encode(aes_key).decode("ascii"),
            "algorithm": "AES-256-GCM",
        }

    # ------------------------------------------------------------------
    # legacy / simple key API (used by devices/client.py, main.py, tests)
    # ------------------------------------------------------------------

    def get_fresh_key(
        self,
        device_id: str,
        peer_id: str = "_broadcast_",
        pqc_enabled: bool = False,
        force_eve_attack: bool = False,
    ) -> bytes:
        """
        Simple one-call key retrieval used by SoldierDevice and main.py.

        If force_eve_attack is True the key exchange runs with Eve present;
        a compromised channel raises an exception.

        The *second* device that calls get_fresh_key without force_eve_attack
        receives the same key as the first device (shared demo-key semantics).
        """
        old_eve = self.eve_mode
        if force_eve_attack:
            self.eve_mode = True

        try:
            session_id = uuid.uuid4().hex
            bb84 = run_bb84_session(session_id, num_bits=256, eve=self.eve_mode, rng_seed=None)
        finally:
            if force_eve_attack:
                self.eve_mode = old_eve

        raw_key: bytes = bb84["raw_key"]
        qber: float = float(bb84["qber"])
        attack_detected: bool = bool(bb84["attack_detected"])
        status = self._status_from_qber(qber, attack_detected)

        with self._lock:
            self.last_qber = qber
            self.last_status = status
            self.link_status = status
            self.last_attack_detected = attack_detected
            if attack_detected or status == "RED":
                self.attacks_detected += 1

        if attack_detected or status == "RED":
            raise Exception(
                f"Quantum channel compromised — QBER={qber:.2%}. Key not issued."
            )

        pqc_secret = os.urandom(32) if pqc_enabled else None
        aes_key = self._derive_aes_key(raw_key, pqc_secret)

        with self._lock:
            self.total_keys_issued += 1
            # store so the second device can retrieve the same key
            if self._last_key is None:
                self._last_key = aes_key
            else:
                # second caller gets the existing shared key
                aes_key = self._last_key

        return aes_key

    # ------------------------------------------------------------------
    # Eve / attack control
    # ------------------------------------------------------------------

    @property
    def eve_active(self) -> bool:
        return self.eve_mode

    def activate_eve(self) -> None:
        with self._lock:
            self.eve_mode = True

    def deactivate_eve(self) -> None:
        with self._lock:
            self.eve_mode = False

    def set_eve_mode(self, on: bool) -> None:
        with self._lock:
            self.eve_mode = on

    def trigger_attack(self) -> Dict[str, object]:
        session_id = f"attack-{uuid.uuid4().hex[:8]}"
        bb84 = run_bb84_session(session_id, num_bits=256, eve=True, rng_seed=None)

        qber: float = float(bb84["qber"])
        attack_detected: bool = bool(bb84["attack_detected"])
        if not attack_detected:
            qber = SECURE_QBER_THRESHOLD
            attack_detected = True

        aes_key = self._derive_aes_key(os.urandom(32), None)
        record = SessionRecord(
            session_id=session_id,
            key=aes_key,
            qber=qber,
            status="RED",
            clients={"system"},
            created_at=time.time(),
            compromised=True,
            use_hybrid=False,
            pqc_secret=None,
            is_control=True,
        )

        with self._lock:
            self.sessions[session_id] = record
            self.attacks_detected += 1
            self.last_qber = qber
            self.last_status = "RED"
            self.link_status = "RED"
            self.last_attack_detected = True
            self._update_escalation("RED")

        return {
            "session_id": session_id,
            "status": "RED",
            "qber": qber,
            "attack_detected": True,
            "attacks_detected": self.attacks_detected,
        }

    # ------------------------------------------------------------------
    # health / status
    # ------------------------------------------------------------------

    def check_link_health(self) -> Dict[str, object]:
        with self._lock:
            return {
                "status": self.last_status,
                "last_qber": self.last_qber,
                "total_keys_issued": self.total_keys_issued,
                "total_sessions": self.total_sessions,
                "attacks_detected": self.attacks_detected,
                "active_sessions": sum(1 for s in self.sessions.values() if not s.is_control),
                "eve_active": self.eve_mode,
            }

    def get_link_status(self) -> Dict[str, object]:
        with self._lock:
            active_sessions = sum(1 for s in self.sessions.values() if not s.is_control)
            label = {
                1: "SAFE",
                2: "TACTICAL RETREAT",
                3: "EMERGENCY",
                4: "LOCKDOWN",
            }.get(self.escalation_level, "SAFE")

            return {
                "status": self.last_status,
                "qber": self.last_qber,
                "attacks_detected": self.attacks_detected,
                "active_sessions": active_sessions,
                "eve_mode": self.eve_mode,
                "escalation_level": self.escalation_level,
                "escalation_label": label,
                "current_port": self.current_port,
                "current_ip": self.current_ip,
                "current_network": self.current_network,
            }

    def list_sessions(self) -> list:
        with self._lock:
            return [
                {
                    "session_id": s,
                    "status": r.status,
                    "qber": r.qber,
                    "clients": list(r.clients),
                }
                for s, r in self.sessions.items()
                if not r.is_control
            ]

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self.sessions.clear()
            self.eve_mode = False
            self.attacks_detected = 0
            self.total_sessions = 0
            self.total_keys_issued = 0
            self.last_qber = 0.0
            self.last_status = "GREEN"
            self.link_status = "GREEN"
            self.last_attack_detected = False
            self.escalation_level = 1
            self.burned_ports.clear()
            self.burned_ips.clear()
            self.burned_networks.clear()
            self.current_port = self.port_pool[0]
            self.current_ip = self.ip_pool[0]
            self.current_network = self.network_pool[0]
            self._last_key = None

    def reset_for_demo(self) -> None:
        self.reset()
