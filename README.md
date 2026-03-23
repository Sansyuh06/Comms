# Quantum-Aware Secure Chat (BB84 Demo)

## What this project is
Two people chat securely over Wi-Fi through a normal home router.
Instead of RSA/ECDH, a lightweight BB84-style simulator generates shared secrets.
The system watches quantum-link health (QBER) and reacts to attacks by rotating ports/IPs,
then escalating to network changes or lockdown. This shows how networks can become
"quantum-aware" without replacing existing hardware.

## Repo layout
- quantum_engine/bb84_simulator.py - BB84 simulator with QBER + attack detection
- kms/key_management_service.py - KMS core logic and escalation tracking
- kms/kms_server.py - FastAPI server + status UI
- chat/chat_server.py - WebSocket relay (no decryption)
- chat/client_app.py - Terminal client with AES-256-GCM
- chat/client_gui.py - Tkinter GUI client with AES-256-GCM
- router/router_guard.sh - Router guard script (OpenWrt-style simulation)

## Setup
1. Install dependencies:
   python -m pip install -r requirements.txt

2. Configure IPs
   Example LAN:
   - Router: 192.168.1.1
   - Laptop (KMS + chat server): 192.168.1.100

   If your LAN uses different addresses, update:
   - router/router_guard.sh (KMS_HOST, PRIMARY_IP, BACKUP_IP)
   - chat/client_app.py defaults (KMS base URL, WS URL) or enter them at runtime.

## Run (demo sequence)
1. Start KMS (API + status UI):
   python -m kms.kms_server --host 0.0.0.0 --port 8000

   Status UI: http://192.168.1.100:8000/

2. Start chat relay:
   python -m chat.chat_server --host 0.0.0.0 --port 8765

3. Start router guard (Linux/OpenWrt box or VM):
   sh router/router_guard.sh

   Note: The script uses iptables and may require root privileges.
   It simulates port/IP/network escalation; IP changes are logged and conceptual.

4. Start two clients (Alice and Bob):
   python -m chat.client_app
   python -m chat.client_app

## One-command launcher
Start KMS, chat server, and two GUI clients:
python start_all.py

Options:
- --no-gui (skip GUI clients)
- --clients N (number of GUI windows to open)

## GUI chat client (optional)
If you prefer a GUI, run:
python -m chat.client_gui

## Normal GREEN demo
1. Create a new session (client will call /create_session).
2. Chat normally. QBER should be low and status stays GREEN.
3. Use /status inside the client to view link health.

## Trigger Eve / attack demo
Option A (UI): click Activate Eve or Trigger Attack at http://192.168.1.100:8000/
Option B (CLI):
- Activate Eve: curl -X POST http://192.168.1.100:8000/activate_eve
- Trigger attack: curl -X POST http://192.168.1.100:8000/trigger_attack

Expected behavior:
- QBER rises toward 20-30%.
- Status flips to RED.
- Router guard blocks the current port and rotates/escalates.
- Clients may lose the connection and must reconnect to the new port/IP.

## Escalation ladder (summary)
Level 1 (SAFE): rotate and burn ports after repeated RED signals.
Level 2 (TACTICAL RETREAT): all ports burned -> switch IP and reuse fresh ports.
Level 3 (EMERGENCY): all IPs burned -> switch network/subnet (conceptual).
Level 4 (LOCKDOWN): full stop, manual intervention required.

KMS computes escalation_level and router_guard enforces firewall rules.
Higher-level actions (IP or network change) are logged in the guard script
and are simulated to keep the demo lightweight.

## Notes
- This is a demo; keys are returned to clients via the KMS API for simplicity.
- The router is treated as untrusted; encryption is end-to-end between clients.
- If websockets fail to connect, check the router guard status and link health.
