# Quantum-Safe Tactical Communication System (QSTCS v3)

A complete end-to-end quantum-aware secure chat system where two users communicate over Wi-Fi through a D-Link DSL-2750U router. Messages are encrypted with quantum-derived AES-256-GCM keys from a BB84 simulator, and the router **actively blocks traffic** when the quantum channel is compromised.

## Architecture

```
┌──────────────┐       Wi-Fi (via D-Link)       ┌──────────────┐
│ Client Alpha │◄──────────────────────────────►│ Client Bravo │
│ AES-256-GCM  │     WebSocket (port 8765)      │ AES-256-GCM  │
└──────┬───────┘                                └──────┬───────┘
       │ HTTP POST /get_session_key                    │
       ▼                                               ▼
┌─────────────────────────────────────────────────────────────┐
│              KMS Server (FastAPI, port 8000)                 │
│   BB84 Simulation → QBER Check → HKDF → AES-256 Key        │
│   Endpoints: /get_session_key, /link_status, /force_attack  │
└─────────────────────────────────────────────────────────────┘
       ▲                        ▲
       │ WebSocket relay        │ HTTP poll (every 3s)
┌──────┴───────┐         ┌─────┴──────────┐
│ Chat Server  │         │  D-Link Router │
│  (port 8765) │         │ router_guard.sh│
│ Zero-knowledge│        │ iptables DROP  │
│ relay         │        │ when RED       │
└──────────────┘         └────────────────┘
```

## Components

| Component | File | Purpose |
|-----------|------|---------|
| BB84 Simulator | `quantum_engine/bb84_simulator.py` | QKD key generation with Eve detection |
| Key Management | `kms/key_management_service.py` | HKDF derivation, session tracking, link health |
| KMS Server | `kms_server.py` | FastAPI REST API wrapping the KMS |
| Chat Server | `chat_server.py` | WebSocket relay (zero-knowledge) |
| Chat Client | `client_app.py` | Terminal chat with AES-256-GCM encryption |
| Router Guard | `router_guard.sh` | iptables gatekeeper on D-Link router |
| Dashboard | `dashboard/dashboard_ui.py` | Streamlit SOC monitoring UI |
| Console Demo | `main.py` | Quick local-only demo (no network) |

## Prerequisites

- Python 3.8+ (Tested with 3.14)
- pip installed
- D-Link DSL-2750U router (or any OpenWrt device) for router integration

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start (Local Demo)

Run everything on one machine for testing:

```bash
# Terminal 1: KMS Server
python kms_server.py

# Terminal 2: Chat Server
python chat_server.py

# Terminal 3: Client Alpha
python client_app.py
# Enter: Soldier_Alpha, Soldier_Bravo, http://localhost:8000, ws://localhost:8765

# Terminal 4: Client Bravo
python client_app.py
# Enter: Soldier_Bravo, Soldier_Alpha, http://localhost:8000, ws://localhost:8765

# Terminal 5: Dashboard
streamlit run dashboard/dashboard_ui.py
```

## Full Demo (Multi-Machine + Router)

### Setup

```
Machine A (192.168.1.100): KMS Server + Chat Server + Dashboard
Machine B (192.168.1.101): Client Alpha
Machine C (192.168.1.102): Client Bravo
Router    (192.168.1.1):   router_guard.sh
```

### Step 1: Start Servers (Machine A)

```bash
# Terminal 1
python kms_server.py

# Terminal 2
python chat_server.py

# Terminal 3
streamlit run dashboard/dashboard_ui.py
```

### Step 2: Deploy Router Guard

```bash
scp router_guard.sh root@192.168.1.1:/tmp/
ssh root@192.168.1.1 "chmod +x /tmp/router_guard.sh && /tmp/router_guard.sh"
```

Edit `KMS_HOST` in the script to match Machine A's IP.

### Step 3: Start Clients

```bash
# Machine B
python client_app.py
# Enter: Soldier_Alpha, Soldier_Bravo, http://192.168.1.100:8000, ws://192.168.1.100:8765

# Machine C
python client_app.py
# Enter: Soldier_Bravo, Soldier_Alpha, http://192.168.1.100:8000, ws://192.168.1.100:8765
```

### Step 4: Demo Flow

1. **Normal Mode**: Chat works, QBER ≈ 2%, Dashboard shows 🟢 GREEN
2. **Attack Mode**: Click "Force Attack" on Dashboard → QBER ≈ 25% → 🔴 RED → Router blocks port 8765 → Clients disconnect
3. **Recovery**: Click "Reset" → 🟢 GREEN → Router allows traffic → Clients reconnect

## Console Demo (Legacy)

```bash
python main.py
```

## Testing

```bash
python -c "import sys, os; sys.path.insert(0, os.getcwd()); import unittest; from tests import test_kms_devices; suite = unittest.TestLoader().loadTestsFromModule(test_kms_devices); unittest.TextTestRunner(verbosity=2).run(suite)"
```

## API Reference

### KMS Server (port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/get_session_key` | Request quantum-derived AES-256 key |
| GET | `/link_status` | Query link health (GREEN/YELLOW/RED) |
| POST | `/force_attack` | Trigger simulated Eve attack |
| POST | `/reset` | Reset KMS state |

Interactive docs: `http://<server>:8000/docs`

## Security Model

- **BB84 Simulator**: Classical emulation of quantum key distribution. Not actual quantum hardware. The simulation accurately models the protocol's security properties including QBER-based eavesdropper detection.
- **AES-256-GCM**: Real, production-grade authenticated encryption. 12-byte nonce, 128-bit authentication tag.
- **HKDF-SHA256**: Standard key derivation for consistent 256-bit output with domain separation.
- **Hybrid PQC** (optional): BB84 key combined with simulated Kyber KEM for hybrid quantum safety.
- **Router enforcement**: Physical network isolation via iptables — not a software flag.

## License

UNCLASSIFIED — For Demonstration and Hackathon Purposes
