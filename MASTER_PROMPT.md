# MASTER PROMPT — Quantum-Aware Secure Communication System (QSTCS v3)

> **Paste this entire prompt into any AI coding assistant (GPT-4/5, Claude, Gemini).**
> It assumes the assistant has access to the `Sansyuh06/Comms` repository.

---

## ROLE

You are a senior full-stack systems engineer, cryptography expert, and hackathon coach.
Produce complete, working, copy-pasteable code for every file requested below.
Use Python 3.10+. Do not use placeholder stubs — every function must be fully implemented.

---

## 1 — REPO CONTEXT (What Already Exists)

The repository `Sansyuh06/Comms` is a Python project with the following structure:

```
Sansyuh06/Comms/
├── quantum_engine/
│   ├── __init__.py
│   └── bb84_simulator.py      # BB84 QKD simulation (Alice, Bob, Eve)
├── kms/
│   ├── __init__.py
│   └── key_management_service.py  # KeyManagementService class
├── devices/
│   ├── __init__.py
│   └── client.py              # SoldierDevice class (AES-256-GCM encrypt/decrypt)
├── gateway/
│   ├── __init__.py
│   └── network_gateway.py     # NetworkGateway class (in-memory message routing)
├── dashboard/
│   ├── __init__.py
│   └── dashboard_ui.py        # Streamlit SOC monitoring dashboard
├── tests/
│   ├── test_bb84.py
│   ├── test_kms_devices.py
│   └── test_system.py
├── main.py                    # Console demo (all components in-process)
├── requirements.txt
└── README.md
```

### What each module already does (reuse these, do NOT rewrite from scratch):

| Module | Key Class / Function | What It Does |
|--------|---------------------|--------------|
| `quantum_engine/bb84_simulator.py` | `simulate_bb84(num_bits, eve_present, eve_intercept_rate, noise_level) → (bytes, float, bool)` | Full BB84 simulation: Alice/Bob bit generation, optional Eve intercept-resend, sifting, QBER computation, 256-bit key extraction. Returns `(shared_key_bytes, qber_float, attack_detected_bool)`. Threshold constant: `QBER_SECURITY_THRESHOLD = 0.11`. |
| `kms/key_management_service.py` | `KeyManagementService` | Calls `simulate_bb84()`, validates QBER, derives 256-bit AES key via HKDF-SHA256, tracks sessions, metrics, link status (GREEN/YELLOW/RED). Key methods: `get_fresh_key(device_id, force_eve_attack) → bytes`, `check_link_health() → dict`, `reset_for_demo()`. Thread-safe. |
| `devices/client.py` | `SoldierDevice` | Requests key from KMS (currently direct Python call), encrypts with AES-256-GCM (12-byte random nonce, 128-bit tag), produces JSON packet `{sender, recipient, nonce_hex, ciphertext_hex, timestamp}`, decrypts incoming packets. |
| `gateway/network_gateway.py` | `NetworkGateway` | Registers devices, routes opaque ciphertext packets to per-recipient queues, zero-knowledge design. Methods: `register_device()`, `route_message()`, `get_pending_messages()`. |
| `dashboard/dashboard_ui.py` | Streamlit app | SOC dashboard: link status indicator, QBER gauge, key issuance tracker, interactive message send/receive, BB84 demo. Uses `st.session_state` to hold KMS, SoldierDevices. |

### Critical limitation (what needs to change):

**Currently everything runs in a single Python process.** `SoldierDevice` holds a direct object reference to `KeyManagementService`. `NetworkGateway` is a local in-memory queue. Nothing goes over the network. The D-Link router is not involved at all.

---

## 2 — TARGET ARCHITECTURE (What We Are Building)

### Goal
A working, networked quantum-aware secure chat where two users on separate machines chat over Wi-Fi through a **D-Link DSL-2750U** modem/router, and the router **actively blocks traffic** when the quantum channel is compromised.

### Component Diagram

```
┌─────────────────┐         Wi-Fi (LAN)         ┌─────────────────┐
│  Client Alpha   │◄──────────────────────────►│  Client Bravo   │
│  (client_app.py)│     WebSocket to Chat Srv   │  (client_app.py)│
│  AES-GCM enc/dec│                              │  AES-GCM enc/dec│
└────────┬────────┘                              └────────┬────────┘
         │ HTTP: POST /get_session_key                    │
         │ HTTP: GET  /link_status                        │
         ▼                                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                  KMS Server (kms_server.py)                       │
│           FastAPI app running on port 8000                        │
│  Wraps: KeyManagementService + bb84_simulator                     │
│  Endpoints:                                                       │
│    POST /get_session_key  → runs BB84, returns {key_hex, qber}   │
│    GET  /link_status      → returns {status, qber, ...}          │
│    POST /force_attack     → sets forced Eve mode (demo trigger)  │
│    POST /reset            → resets KMS state                     │
└───────────────────────────────────────────────────────────────────┘
         ▲
         │ HTTP poll: GET /link_status every 3 seconds
         │
┌────────┴────────┐
│  D-Link Router  │
│  (OpenWrt shell)│
│  router_guard.sh│
│  iptables rules │
│  Blocks port    │
│  8765 when RED  │
└─────────────────┘
         ▲
         │ WebSocket traffic on port 8765
         │
┌───────────────────────────────────────────────────────────────────┐
│               Chat Server (chat_server.py)                        │
│       asyncio WebSocket relay on port 8765                        │
│  Zero-knowledge: forwards opaque JSON packets between clients     │
│  Registers users by device_id on connect                          │
│  Broadcasts to recipient or all                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Data Flows

1. **Key Establishment**: Client → `POST /get_session_key` → KMS runs BB84 sim → validates QBER → HKDF → returns `{key_hex, qber, status}`.
2. **Messaging**: Client A encrypts plaintext with AES-256-GCM → sends JSON over WebSocket → Chat Server relays → Client B receives → decrypts.
3. **Router Enforcement**: Router shell script polls `GET /link_status` every 3s. If `status=RED`, it inserts `iptables -A FORWARD -p tcp --dport 8765 -j DROP`. If `status=GREEN`, it removes that rule. The Chat Server runs on port 8765, so all chat traffic physically transits the router, and when rules drop it, both clients experience real connection failures.

### Trust & Threat Model (reviewer-friendly)

| Entity | Trust Level | Justification |
|--------|-------------|---------------|
| KMS Server | **Fully trusted** | Holds all key material. Runs BB84 internally. Must be on a secured host. |
| Chat Server | **Untrusted** | Only sees ciphertext. Compromise yields no plaintext. Defense-in-depth. |
| Router | **Policy enforcer** | Doesn't hold keys. Enforces allow/block based on KMS status. Compromise = loss of blocking, not key leakage. |
| Wi-Fi channel | **Untrusted** | All messages are AES-256-GCM encrypted. Passive/active Wi-Fi attacks are irrelevant. |
| Eve (quantum) | **Adversary** | Intercept-resend attack on simulated quantum channel. Detected via QBER > 11%. Router physically isolates network. |

---

## 3 — IMPLEMENTATION TASKS (follow this order exactly)

### TASK 1: Update `requirements.txt`

Replace the existing file with:

```
# QSTCS v3 - Quantum-Aware Secure Communication System
# Core
cryptography>=42.0.0
numpy>=1.26.0

# Networking
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
websockets>=12.0
httpx>=0.27.0

# Dashboard
streamlit>=1.32.0

# Optional: PQC hybrid (extra credit)
# pqcrypto>=0.1.0
```

---

### TASK 2: Create `kms_server.py` (FastAPI KMS — root of repo)

**File location:** `kms_server.py` in the repository root.

**Requirements:**
- Import and instantiate `KeyManagementService` from `kms/key_management_service.py`.
- Wrap it in a FastAPI app with CORS enabled for `*`.
- Implement these exact endpoints:

```
POST /get_session_key
  Request body:  {"device_id": "string", "force_attack": false}
  Logic:         Call kms.get_fresh_key(device_id, force_eve_attack=force_attack)
  Success response 200: {"key_hex": "<64-char hex>", "qber": 0.03, "status": "GREEN"}
  Attack response 200:  {"error": "QKD link compromised...", "qber": 0.25, "status": "RED"}
  (Do NOT raise HTTP errors for attacks — return status RED so the client can handle it gracefully)

GET /link_status
  Logic:    Call kms.check_link_health()
  Response: {"status": "GREEN"|"YELLOW"|"RED", "qber": 0.03, "total_keys_issued": 2, "attacks_detected": 0, "active_sessions": 2}

POST /force_attack
  Logic:    Trigger a BB84 run with force_eve_attack=True to flip KMS to RED
  Response: {"status": "RED", "qber": <float>}

POST /reset
  Logic:    Call kms.reset_for_demo()
  Response: {"status": "reset_complete"}
```

- Add a `__main__` block: `uvicorn.run(app, host="0.0.0.0", port=8000)`
- Print the server URL and LAN IP on startup for easy discovery.

**Important:** The KMS holds a `_last_key` for demo key-sharing between two devices (device A gets a fresh key, device B gets the same key). This existing behavior must be preserved so both clients end up with the same symmetric key.

---

### TASK 3: Create `chat_server.py` (WebSocket Relay — root of repo)

**File location:** `chat_server.py` in the repository root.

**Requirements:**
- Use the `websockets` library (asyncio).
- Listen on `0.0.0.0:8765`.
- Maintain a dict `connected_clients: Dict[str, websocket]` keyed by `device_id`.
- On connect, the client sends a registration message: `{"type": "register", "device_id": "Soldier_Alpha"}`.
- On receiving a chat message, the server parses the JSON to extract `recipient`:
  - If `recipient` is in `connected_clients`, forward the entire JSON to that specific websocket.
  - Otherwise, print a warning (recipient offline).
- The server NEVER inspects `ciphertext`, `nonce`, or `key` fields. It is a dumb relay.
- Print connection/disconnection/routing events to the console for demo visibility.

**Message format the server relays (opaque):**
```json
{
  "type": "chat",
  "sender": "Soldier_Alpha",
  "recipient": "Soldier_Bravo",
  "nonce": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "ciphertext": "4a8f2c1e9d3b7a...",
  "timestamp": 1700000000
}
```

---

### TASK 4: Create `client_app.py` (Interactive Chat Client — root of repo)

**File location:** `client_app.py` in the repository root.

**Requirements:**
- A terminal-based interactive chat client.
- On startup, prompt for:
  - `device_id` (e.g., "Soldier_Alpha" or "Soldier_Bravo")
  - `kms_url` (default: `http://192.168.1.100:8000`)
  - `chat_url` (default: `ws://192.168.1.100:8765`)
- **Key fetching**: Use `httpx` to call `POST /get_session_key` with the device_id. Parse the response and store `key_hex` locally as bytes. If `status == RED`, print a warning and do not proceed with chat.
- **Encryption/Decryption**: Reuse the exact AES-256-GCM logic from `devices/client.py`:
  - Encrypt: `AESGCM(key).encrypt(os.urandom(12), plaintext.encode(), None)` → package as `{type, sender, recipient, nonce_hex, ciphertext_hex, timestamp}`.
  - Decrypt: Parse incoming JSON → `AESGCM(key).decrypt(nonce_bytes, ciphertext_bytes, None)`.
- **WebSocket connection**: Use `websockets` to connect to the chat server.
  - Send registration message on connect.
  - Run two concurrent async tasks:
    1. **Sender loop**: Read lines from stdin → encrypt → send JSON over websocket.
    2. **Receiver loop**: Listen for incoming messages → decrypt → print plaintext with sender info.
- Print a clear UI showing sent/received messages, key status, and connection state.
- Handle disconnections gracefully (e.g., when router blocks port 8765, catch the exception and print "Connection lost — quantum channel may be compromised").

---

### TASK 5: Create `router_guard.sh` (Router Gatekeeper Script)

**File location:** `router_guard.sh` in the repository root.

**Target runtime:** D-Link DSL-2750U running OpenWrt or stock Linux with BusyBox (use `wget` not `curl`).

**Requirements:**
- Configuration variables at the top:
  ```bash
  KMS_HOST="192.168.1.100"   # IP of the machine running kms_server.py
  KMS_PORT="8000"
  CHAT_PORT="8765"           # Port used by chat_server.py
  POLL_INTERVAL=3            # Seconds between polls
  ```
- Infinite loop:
  1. Poll `http://$KMS_HOST:$KMS_PORT/link_status` using `wget -qO-`.
  2. Parse the JSON response to extract the `status` field. On BusyBox, use simple `grep` / `sed` pattern matching (e.g., `grep -o '"status":"[^"]*"' | cut -d'"' -f4`). Do NOT assume `jq` is available.
  3. **If status is RED and the DROP rule is not yet active:**
     - `iptables -I FORWARD -p tcp --dport $CHAT_PORT -j DROP`
     - `iptables -I FORWARD -p tcp --sport $CHAT_PORT -j DROP`
     - Print `[GUARD] QUANTUM BREACH — Chat traffic BLOCKED`
  4. **If status is GREEN and the DROP rule is currently active:**
     - `iptables -D FORWARD -p tcp --dport $CHAT_PORT -j DROP`
     - `iptables -D FORWARD -p tcp --sport $CHAT_PORT -j DROP`
     - Print `[GUARD] Quantum link secure — Chat traffic ALLOWED`
  5. **If status hasn't changed**, do nothing (avoid spamming iptables).
  6. Sleep for `$POLL_INTERVAL` seconds.
- Use a state variable (`CURRENT_STATE`) to track GREEN/RED and avoid redundant iptables calls.
- Add a cleanup trap (`trap cleanup EXIT`) that removes the DROP rules on script exit.
- Print timestamped log lines for every state change.

**How to deploy:**
```bash
# From a machine with SSH access to the router:
scp router_guard.sh root@192.168.1.1:/tmp/
ssh root@192.168.1.1 "chmod +x /tmp/router_guard.sh && /tmp/router_guard.sh"
```

---

### TASK 6: Update `dashboard/dashboard_ui.py` (Network-Aware Dashboard)

**Modify the existing Streamlit dashboard** to:
1. Add a `KMS_URL` config field in the sidebar (default `http://localhost:8000`).
2. Replace all direct `kms.get_fresh_key()` calls with `httpx.post(KMS_URL + "/get_session_key", json={...})`.
3. Replace `kms.check_link_health()` with `httpx.get(KMS_URL + "/link_status").json()`.
4. Add a new section: **"Router Status"** showing whether the router guard is active (poll `/link_status` and display the last known status).
5. Add a **"Force Attack"** button that calls `POST /force_attack` on the KMS to trigger RED status for demo purposes.
6. Add a **"Reset System"** button that calls `POST /reset`.
7. Keep all existing BB84 visualization and styling.

---

### TASK 7 (EXTRA CREDIT): Hybrid PQC Key Derivation

In `kms/key_management_service.py`, add an optional **Kyber-style hybrid** step:
- After BB84 produces `raw_key` (32 bytes), generate a second 32-byte key from a simulated Kyber KEM encapsulation (for the prototype, use `os.urandom(32)` as the Kyber shared secret, clearly labeled as a placeholder).
- Combine: `hybrid_input = bb84_key + kyber_key` (64 bytes).
- Pass `hybrid_input` through HKDF-SHA256 (length=32, info=`"QSTCS-Hybrid-PQC"`) to produce the final session key.
- Add a `pqc_enabled: bool = False` parameter to `get_fresh_key()`. When True, use hybrid derivation.
- Update the KMS API `POST /get_session_key` to accept an optional `pqc: true` field.
- This clearly demonstrates the concept of hybrid key derivation (classical QKD + PQC lattice) even though we simulate Kyber.

---

## 4 — DEMO SCENARIO (Step-by-Step)

### Setup (3 terminals + 1 router SSH session)

```
Machine A (server, e.g., IP 192.168.1.100):
  Terminal 1: python kms_server.py           # Starts KMS on :8000
  Terminal 2: python chat_server.py          # Starts Chat Server on :8765
  Terminal 3: streamlit run dashboard/dashboard_ui.py  # Dashboard on :8501

Machine B (soldier device, e.g., IP 192.168.1.101):
  Terminal 1: python client_app.py           # Soldier_Alpha

Machine C (soldier device, e.g., IP 192.168.1.102):
  Terminal 1: python client_app.py           # Soldier_Bravo

Router (D-Link DSL-2750U, IP 192.168.1.1):
  SSH session: /tmp/router_guard.sh          # Gatekeeper polling
```

### Demo Script

**ACT 1 — Normal Secure Communication (2 minutes)**

1. Start KMS server, Chat server, Dashboard.
2. Copy and start `router_guard.sh` on the router. Terminal shows:
   ```
   [GUARD] 2026-02-23 05:00:00 | Polling KMS at 192.168.1.100:8000...
   [GUARD] 2026-02-23 05:00:01 | Status: GREEN — Chat traffic ALLOWED
   ```
3. On Machine B, start `client_app.py` as `Soldier_Alpha`. It:
   - Calls `POST /get_session_key` → receives 256-bit key, QBER ≈ 2%.
   - Connects to Chat Server WebSocket.
   - Prints: `[Alpha] ✓ Quantum key established (QBER=2.0%) | Status: GREEN`
4. On Machine C, start `client_app.py` as `Soldier_Bravo`. Same flow (gets same shared key via demo key-sharing).
5. Alpha types a message → encrypted → sent via WebSocket through the router → Bravo receives → decrypts → displays plaintext.
6. Dashboard shows: 🟢 GREEN, QBER 2%, 2 keys issued, 0 attacks.

**ACT 2 — Quantum Attack Detection & Network Isolation (2 minutes)**

7. On the Dashboard, click **"Force Attack"** button (calls `POST /force_attack`).
8. KMS runs BB84 with Eve → QBER ≈ 25% → Status flips to **RED**.
9. Dashboard shows: 🔴 RED, QBER 25%, 1 attack detected.
10. Router guard detects RED on next poll:
    ```
    [GUARD] 2026-02-23 05:02:03 | Status: RED — QUANTUM BREACH DETECTED!
    [GUARD] 2026-02-23 05:02:03 | Executing: iptables -I FORWARD -p tcp --dport 8765 -j DROP
    [GUARD] 2026-02-23 05:02:03 | Chat traffic BLOCKED at network layer
    ```
11. Alpha tries to send a message → WebSocket fails / times out → Client prints:
    ```
    [Alpha] ❌ Connection lost — quantum channel compromised. Awaiting re-key.
    ```
12. Bravo also loses connection.
13. **The modem/router has physically isolated the communication channel.** This is not a software flag — the packets are being dropped at the kernel firewall level on the router itself.

**ACT 3 — Recovery (1 minute)**

14. Click **"Reset System"** on Dashboard → calls `POST /reset` → KMS resets to GREEN.
15. Router guard detects GREEN:
    ```
    [GUARD] 2026-02-23 05:03:06 | Status: GREEN — Quantum link restored
    [GUARD] 2026-02-23 05:03:06 | Removing firewall block. Chat traffic ALLOWED.
    ```
16. Clients reconnect, re-key, resume chatting.

---

## 5 — CODE QUALITY & HACKATHON REQUIREMENTS

- **Clean separation**: Crypto logic stays in `quantum_engine/` and `kms/`. Networking in `kms_server.py`, `chat_server.py`. Client logic in `client_app.py`. Router in `router_guard.sh`.
- **Honest security claims**: The BB84 is a classical simulation, not actual quantum hardware. State this clearly in code comments and presentations. The security value is the architecture and the AES-GCM encryption — that part is real and production-grade.
- **All print statements should be descriptive** for live demo readability (judges will see terminals).
- **Error handling**: Every network call should have try/except with meaningful messages.
- **README.md**: Update to document the new multi-machine setup, demo instructions, and architecture diagram.

---

## 6 — FILE CHECKLIST

When complete, the repo should contain:

```
Sansyuh06/Comms/
├── quantum_engine/
│   ├── __init__.py          (keep)
│   └── bb84_simulator.py    (keep — no changes needed)
├── kms/
│   ├── __init__.py          (keep)
│   └── key_management_service.py  (MODIFY: add hybrid PQC option)
├── devices/
│   ├── __init__.py          (keep)
│   └── client.py            (keep — used as reference, logic reused in client_app.py)
├── gateway/
│   ├── __init__.py          (keep)
│   └── network_gateway.py   (keep — superseded by chat_server.py but kept for tests)
├── dashboard/
│   ├── __init__.py          (keep)
│   └── dashboard_ui.py      (MODIFY: network-aware, talks to KMS API)
├── tests/                    (keep all existing tests)
├── main.py                   (keep — still works as local-only demo)
├── kms_server.py             (NEW — FastAPI KMS)
├── chat_server.py            (NEW — WebSocket relay)
├── client_app.py             (NEW — interactive chat client)
├── router_guard.sh           (NEW — router gatekeeper script)
├── requirements.txt          (MODIFY — add fastapi, uvicorn, websockets, httpx)
└── README.md                 (MODIFY — updated setup and demo instructions)
```

---

## 7 — EXECUTION ORDER

Implement in this exact order:
1. `requirements.txt` (TASK 1)
2. `kms_server.py` (TASK 2)
3. `chat_server.py` (TASK 3)
4. `client_app.py` (TASK 4)
5. `router_guard.sh` (TASK 5)
6. `dashboard/dashboard_ui.py` modifications (TASK 6)
7. Hybrid PQC in `kms/key_management_service.py` (TASK 7, if time permits)
8. `README.md` update with full demo instructions

**Generate the complete code for each file in order. Do not use placeholders or TODOs.**
