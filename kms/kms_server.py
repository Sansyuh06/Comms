"""
FastAPI server exposing the KMS API and a minimal status UI.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from kms.key_management_service import KeyManagementService

app = FastAPI(title="Quantum-Aware KMS")

kms = KeyManagementService()


class CreateSessionRequest(BaseModel):
    client_a: str
    client_b: str
    use_hybrid: bool = False


class GetKeyRequest(BaseModel):
    session_id: str
    client_id: str


@app.post("/create_session")
def create_session(req: CreateSessionRequest):
    res = kms.create_session(req.client_a, req.client_b, req.use_hybrid)
    res.pop("key", None)
    return res


@app.post("/get_key")
def get_key(req: GetKeyRequest):
    try:
        return kms.get_key(req.session_id, req.client_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Client not in session")


@app.get("/link_status")
def link_status():
    return kms.get_link_status()


@app.post("/activate_eve")
def activate_eve():
    kms.set_eve_mode(True)
    return {"eve_mode": True}


@app.post("/deactivate_eve")
def deactivate_eve():
    kms.set_eve_mode(False)
    return {"eve_mode": False}


@app.post("/trigger_attack")
def trigger_attack():
    return kms.trigger_attack()


STATUS_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quantum Link Status</title>
  <style>
    :root {
      --green: #1b9e3e;
      --yellow: #e2b203;
      --red: #d62828;
      --ink: #0f172a;
      --bg: #f5f5f0;
    }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top left, #ffffff, var(--bg));
    }
    .wrap {
      max-width: 900px;
      margin: 24px auto;
      padding: 16px 20px 32px;
    }
    .title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .card {
      margin-top: 16px;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #fff;
      padding: 16px;
      box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
    }
    .status {
      font-size: 22px;
      font-weight: 700;
      padding: 6px 12px;
      border-radius: 999px;
      display: inline-block;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .tile {
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 12px;
      background: #f8fafc;
    }
    button {
      border: none;
      border-radius: 10px;
      padding: 10px 14px;
      margin-right: 8px;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-green { background: #c7f9cc; }
    .btn-red { background: #ffccd5; }
    .btn-yellow { background: #fff3bf; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title">
      <h1>Quantum Link Health</h1>
      <div id="status" class="status">UNKNOWN</div>
    </div>

    <div class="card">
      <div class="grid">
        <div class="tile"><strong>QBER</strong><div id="qber">-</div></div>
        <div class="tile"><strong>Eve Mode</strong><div id="eve">-</div></div>
        <div class="tile"><strong>Attacks Detected</strong><div id="attacks">-</div></div>
        <div class="tile"><strong>Escalation</strong><div id="escalation">-</div></div>
        <div class="tile"><strong>Current Port</strong><div id="port">-</div></div>
        <div class="tile"><strong>Current IP</strong><div id="ip">-</div></div>
      </div>

      <div style="margin-top: 16px;">
        <button class="btn-green" onclick="callApi('/activate_eve')">Activate Eve</button>
        <button class="btn-yellow" onclick="callApi('/deactivate_eve')">Deactivate Eve</button>
        <button class="btn-red" onclick="callApi('/trigger_attack')">Trigger Attack</button>
      </div>
    </div>
  </div>

  <script>
    const statusEl = document.getElementById('status');
    const qberEl = document.getElementById('qber');
    const eveEl = document.getElementById('eve');
    const attacksEl = document.getElementById('attacks');
    const escEl = document.getElementById('escalation');
    const portEl = document.getElementById('port');
    const ipEl = document.getElementById('ip');

    const colors = { GREEN: 'var(--green)', YELLOW: 'var(--yellow)', RED: 'var(--red)' };

    async function refresh() {
      const res = await fetch('/link_status');
      const data = await res.json();
      statusEl.textContent = data.status;
      statusEl.style.background = colors[data.status] || '#cbd5f5';
      statusEl.style.color = '#111827';
      qberEl.textContent = (data.qber || 0).toFixed(3);
      eveEl.textContent = data.eve_mode ? 'ON' : 'OFF';
      attacksEl.textContent = data.attacks_detected;
      escEl.textContent = `L${data.escalation_level} - ${data.escalation_label}`;
      portEl.textContent = data.current_port;
      ipEl.textContent = data.current_ip;
    }

    async function callApi(path) {
      await fetch(path, { method: 'POST' });
      await refresh();
    }

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def status_page():
    return HTMLResponse(STATUS_PAGE)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Quantum-aware KMS API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run("kms.kms_server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
