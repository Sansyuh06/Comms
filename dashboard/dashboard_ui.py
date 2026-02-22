"""
Streamlit Monitoring Dashboard
================================
Quantum-Safe Tactical Communication System v3.1

Network-aware dashboard connecting to the KMS Server via HTTP API.
Displays real-time link health, session info, QBER, and attack controls.

Run with:
    streamlit run dashboard/dashboard_ui.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import httpx
except ImportError:
    st.error("Missing dependency: pip install httpx")
    st.stop()

from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD


# =============================================================================
# CONFIG
# =============================================================================

st.set_page_config(page_title="QSTCS Dashboard", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: bold; color: #1a237e; }
    .sub-header { font-size: 1rem; color: #757575; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# STATE
# =============================================================================

if 'kms_url' not in st.session_state:
    st.session_state.kms_url = "http://localhost:8000"


# =============================================================================
# API HELPERS
# =============================================================================

def api(method, path, **kwargs):
    url = st.session_state.kms_url + path
    try:
        with httpx.Client(timeout=5) as c:
            if method == "GET":
                return c.get(url).json()
            else:
                return c.post(url, **kwargs).json()
    except Exception as e:
        return {"_error": str(e), "status": "OFFLINE"}


# =============================================================================
# HEADER
# =============================================================================

st.markdown('<p class="main-header">🛡️ Quantum-Safe Tactical Communication System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Security Operations Dashboard | v3.1</p>', unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.header("⚙️ Configuration")
    st.session_state.kms_url = st.text_input("KMS URL", st.session_state.kms_url)

    st.divider()
    st.header("🔑 Key Exchange")

    s_init = st.text_input("Initiator", "Soldier_Alpha")
    s_peer = st.text_input("Peer", "Soldier_Bravo")
    pqc = st.toggle("🧬 Hybrid PQC")

    if st.button("Create Session", use_container_width=True):
        r = api("POST", "/create_session", json={"initiator": s_init, "peer": s_peer, "pqc": pqc})
        if "error" in r:
            st.error(f"❌ {r['error']}")
        elif "session_id" in r:
            st.success(f"✅ Session `{r['session_id']}` | QBER={r.get('qber',0):.2%}")
            st.code(r["session_id"])
        else:
            st.warning(str(r))

    st.divider()
    st.header("🚨 Attack Control")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 Eve OFF", use_container_width=True):
            api("POST", "/deactivate_eve")
            st.success("Eve deactivated")
    with col2:
        if st.button("🔴 Eve ON", use_container_width=True):
            api("POST", "/activate_eve")
            st.error("Eve active!")

    if st.button("💥 Trigger Attack", use_container_width=True):
        r = api("POST", "/trigger_attack")
        st.error(f"🔴 Status: {r.get('status')} | QBER: {r.get('qber',0):.2%}")

    if st.button("🔄 Reset", use_container_width=True):
        api("POST", "/reset")
        st.success("System reset → GREEN")


# =============================================================================
# MAIN — LINK STATUS
# =============================================================================

health = api("GET", "/link_status")

if "_error" in health:
    st.error(f"⚠️ KMS offline: {health['_error']}")
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    status = health.get("status", "?")
    if status == "GREEN":
        st.markdown("### 🟢 SECURE")
    elif status == "YELLOW":
        st.markdown("### 🟡 ELEVATED")
    elif status == "RED":
        st.markdown("### 🔴 COMPROMISED")
    else:
        st.markdown("### ⚪ OFFLINE")

with col2:
    st.metric("Keys Issued", health.get("total_keys_issued", 0))

with col3:
    st.metric("Sessions", health.get("total_sessions", 0))

with col4:
    st.metric("Attacks", health.get("attacks_detected", 0))

with col5:
    qber = health.get("qber", 0)
    st.metric("QBER", f"{qber:.1%}" if qber > 0 else "N/A")


# =============================================================================
# ROUTER STATUS
# =============================================================================

st.divider()

if status == "GREEN":
    st.success("**📡 Router:** Port 8765 OPEN — chat traffic flowing through D-Link modem")
elif status == "RED":
    st.error("**📡 Router:** Port 8765 BLOCKED — `iptables -I FORWARD -p tcp --dport 8765 -j DROP`")
    st.warning(f"Eve {'ACTIVE' if health.get('eve_active') else 'was active'} | "
               f"QBER={qber:.2%} exceeds 11% threshold")
elif status == "YELLOW":
    st.warning("**📡 Router:** Port 8765 OPEN — elevated QBER, monitoring")


# =============================================================================
# SESSIONS TABLE
# =============================================================================

st.divider()
st.header("📋 Active Sessions")

sessions = api("GET", "/sessions")
sess_list = sessions.get("sessions", [])

if sess_list:
    for s in sess_list:
        with st.expander(f"Session `{s['session_id']}` — {s['initiator']} ↔ {s['peer']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("QBER", f"{s['qber']:.2%}")
            c2.metric("Status", s["status"])
            c3.metric("Joined", "✓" if s["joined"] else "Waiting")
            c4.metric("PQC", "ON" if s["pqc_enabled"] else "OFF")
            st.caption(f"Created: {s['created_at']}")
else:
    st.info("No active sessions. Create one from the sidebar.")


# =============================================================================
# BB84 VISUALIZATION
# =============================================================================

st.divider()
st.header("🔬 BB84 Protocol")

v1, v2 = st.columns(2)

with v1:
    num_qubits = st.slider("Qubits", 128, 1024, 512, 64)
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🟢 No Eve", use_container_width=True):
            key, qber, _ = simulate_bb84(num_bits=num_qubits, eve_present=False)
            st.success(f"QBER: {qber:.2%}")
            st.code(f"Key: {key.hex()[:32]}...")
    with b2:
        if st.button("🔴 With Eve", use_container_width=True):
            key, qber, _ = simulate_bb84(num_bits=num_qubits, eve_present=True)
            st.error(f"QBER: {qber:.2%} — ATTACK DETECTED")

with v2:
    st.markdown("""
    **BB84 Protocol:**
    1. Alice picks random bits + random bases (Z or X)
    2. Bob measures in random bases
    3. Sift: keep bits where bases matched (~50%)
    4. Compare sample → compute QBER
    5. QBER < 11% → secure key. QBER ≥ 11% → abort.

    **Eve's problem:** Measuring a qubit disturbs it.
    Her interception causes ~25% QBER → always detected.
    """)


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("QSTCS v3.1 | Session-based QKD | AES-256-GCM | Router-enforced isolation")
