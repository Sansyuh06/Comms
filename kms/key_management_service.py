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
        port_pool: Optional[list[int]] = None,
        ip_pool: Optional[list[str]] = None,
        network_pool: Optional[list[str]] = None,
    ) -> None:
        self.sessions: Dict[str, SessionRecord] = {}
        self.eve_mode: bool = False
        self.attacks_detected: int = 0
        self.total_sessions: int = 0

        self.last_qber: float = 0.0
        self.last_status: str = "GREEN"
        self.last_attack_detected: bool = False

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

        self._lock = threading.Lock()

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

    def _next_available(self, pool: list, burned: Set) -> Optional:
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

    def create_session(self, client_a: str, client_b: str, use_hybrid: bool) -> Dict[str, object]:
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
            if attack_detected or status == "RED":
                self.attacks_detected += 1

            self.last_qber = qber
            self.last_status = status
            self.last_attack_detected = attack_detected

            self._update_escalation(status)

        return {
            "session_id": session_id,
            "status": status,
            "qber": qber,
            "attack_detected": attack_detected,
            "use_hybrid": use_hybrid,
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

    def get_link_status(self) -> Dict[str, object]:
        with self._lock:
            active_sessions = sum(1 for s in self.sessions.values() if not s.is_control)
            status = self.last_status
            qber = self.last_qber
            attack_count = self.attacks_detected
            eve_mode = self.eve_mode
            escalation_level = self.escalation_level

            label = {
                1: "SAFE",
                2: "TACTICAL RETREAT",
                3: "EMERGENCY",
                4: "LOCKDOWN",
            }.get(escalation_level, "SAFE")

            return {
                "status": status,
                "qber": qber,
                "attacks_detected": attack_count,
                "active_sessions": active_sessions,
                "eve_mode": eve_mode,
                "escalation_level": escalation_level,
                "escalation_label": label,
                "current_port": self.current_port,
                "current_ip": self.current_ip,
                "current_network": self.current_network,
            }

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
            self.last_attack_detected = True
            self._update_escalation("RED")

        return {
            "session_id": session_id,
            "status": "RED",
            "qber": qber,
            "attack_detected": True,
        }
