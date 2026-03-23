# How This Works (Quantum-Aware Secure Chat)

This file explains the architecture and the exact steps to run the demo end-to-end.

## 1) Big-picture flow
1. **BB84 simulator** generates a raw key and a QBER value.
2. **KMS** derives an AES-256-GCM key (HKDF-SHA256) and exposes APIs.
3. **Chat clients** fetch the key from KMS and encrypt messages end-to-end.
4. **Chat server** relays ciphertext only (never decrypts).
5. **Router guard** polls KMS link status and applies firewall rules.
6. **Escalation** rotates ports/IPs/networks or locks down when QBER is high.

## 2) Components and responsibilities
- `quantum_engine/bb84_simulator.py`
  - Simulates BB84: random bases, sifting, QBER.
  - If `eve=True`, QBER rises to ~20?30% (intercept-resend effect).

- `kms/key_management_service.py`
  - Keeps session state in memory.
  - Derives AES-256-GCM keys using HKDF.
  - Tracks link health and escalation level.

- `kms/kms_server.py`
  - FastAPI API endpoints:
    - `POST /create_session`
    - `POST /get_key`
    - `GET /link_status`
    - `POST /activate_eve`, `POST /deactivate_eve`, `POST /trigger_attack`
  - Hosts a simple status UI at `/`.

- `chat/chat_server.py`
  - WebSocket relay. It never decrypts.

- `chat/client_app.py`
  - Terminal client. Encrypts/decrypts with AES-256-GCM.

- `chat/client_gui.py`
  - GUI client (Tkinter). Same crypto flow as terminal client.

- `router/router_guard.sh`
  - Polls `/link_status` and manipulates firewall rules.
  - Rotates ports at Level 1.
  - Switches IP at Level 2 (simulated/logged).
  - Switches network at Level 3 (simulated/logged).
  - Locks down at Level 4.

## 3) Prerequisites
- Python 3.10+ on the main laptop.
- Install dependencies:
  ```bash
  python -m pip install -r requirements.txt
  ```
- A LAN/Wi?Fi network (example):
  - Router: `192.168.1.1`
  - Laptop (KMS + chat): `192.168.1.100`

If your IPs differ, update:
- `router/router_guard.sh` (KMS_HOST, PRIMARY_IP, BACKUP_IP)
- Defaults inside the clients (or enter IPs at runtime)

## 4) Run the demo (step-by-step)
### Option A: One-command launcher
```bash
python start_all.py
```
This starts KMS, chat server, and two GUI clients.

### Option B: Manual start
1. **Start KMS**
   ```bash
   python -m kms.kms_server --host 0.0.0.0 --port 8000
   ```
   UI: `http://<laptop_ip>:8000/`

2. **Start chat server**
   ```bash
   python -m chat.chat_server --host 0.0.0.0 --port 8765
   ```

3. **Start router guard** (Linux/OpenWrt box or VM)
   ```bash
   sh router/router_guard.sh
   ```
   It uses `iptables` and may need root.

4. **Start two clients** (Alice + Bob)
   - GUI:
     ```bash
     python -m chat.client_gui
     ```
   - Terminal:
     ```bash
     python -m chat.client_app
     ```

## 5) Normal (GREEN) demo
1. In the client, choose **Create new session**.
2. Start sending messages. QBER stays low.
3. Use **Link Status** (GUI) or `/status` (terminal) to see QBER.

## 6) Attack demo (Eve)
- Use the KMS UI buttons **Activate Eve** or **Trigger Attack**.
- Or call APIs:
  ```bash
  curl -X POST http://<laptop_ip>:8000/activate_eve
  curl -X POST http://<laptop_ip>:8000/trigger_attack
  ```

Expected results:
- QBER rises.
- Status flips to RED.
- Router guard blocks the port and rotates/escalates.
- Clients may disconnect and need to reconnect.

## 7) Escalation ladder (what it means)
- **Level 1 (SAFE)**: burn port ? rotate to next.
- **Level 2 (TACTICAL RETREAT)**: all ports burned ? switch IP (simulated).
- **Level 3 (EMERGENCY)**: all IPs burned ? switch network (simulated).
- **Level 4 (LOCKDOWN)**: full stop.

The KMS reports `escalation_level` and the router guard enforces firewall rules.

## 8) Troubleshooting
- If clients cannot connect:
  - Check KMS is reachable at `http://<ip>:8000/`.
  - Check chat server is listening on `ws://<ip>:8765`.
  - Check router guard logs and whether it is blocking ports.
- If you see `RED` repeatedly, the router guard will rotate ports/IPs.
  Update your client?s WS URL if the port/IP changes.

## 9) Security notes (for demo context)
- The router is treated as untrusted; encryption is end?to?end between clients.
- For simplicity, KMS returns the AES key to clients over LAN.
- This is a prototype/demo of quantum?aware signaling, not production-grade.
