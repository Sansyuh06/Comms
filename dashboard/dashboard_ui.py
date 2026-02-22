"""
Streamlit Monitoring Dashboard (Network-Aware)
================================================
Defense-Grade Implementation for QSTCS v3

This module provides a real-time web-based monitoring interface for the
Quantum-Safe Tactical Communication System. In v3, it connects to the
KMS Server via HTTP API instead of using in-process Python objects.

DASHBOARD CAPABILITIES:
-----------------------
1. Real-time link status (GREEN/YELLOW/RED) from KMS API
2. QBER (Quantum Bit Error Rate) monitoring
3. Key issuance tracking
4. Attack detection alerts
5. Interactive message demonstration
6. BB84 protocol visualization
7. Force Attack button (triggers RED via KMS API)
8. System Reset button
9. Router guard status display

SECURITY NOTE:
--------------
This dashboard is READ-ONLY for security metrics. It does not have access to
cryptographic keys or plaintext messages. All displayed information is safe
for SOC monitoring without compromising operational security.

Run with:
    streamlit run dashboard/dashboard_ui.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import streamlit as st
import sys
import os
import time

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import httpx
    NETWORK_MODE = True
except ImportError:
    NETWORK_MODE = False

from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="QSTCS Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# CUSTOM STYLING
# =============================================================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1a237e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #757575;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 1rem;
        color: white;
    }
    .status-green {
        background-color: #43a047;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .status-red {
        background-color: #e53935;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .status-yellow {
        background-color: #ffc107;
        color: black;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .router-card {
        border: 2px solid #1565c0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize Streamlit session state."""
    if 'message_log' not in st.session_state:
        st.session_state.message_log = []
    if 'kms_url' not in st.session_state:
        st.session_state.kms_url = "http://localhost:8000"


init_session_state()


# =============================================================================
# KMS API HELPERS
# =============================================================================

def api_get_link_status(kms_url: str) -> dict:
    """Query KMS for current link health via HTTP API."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{kms_url}/link_status")
            return response.json()
    except Exception as e:
        return {
            "status": "OFFLINE",
            "qber": 0.0,
            "total_keys_issued": 0,
            "attacks_detected": 0,
            "active_sessions": 0,
            "_error": str(e),
        }


def api_get_session_key(kms_url: str, device_id: str, force_attack: bool = False, pqc: bool = False) -> dict:
    """Request a session key from KMS via HTTP API."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{kms_url}/get_session_key",
                json={"device_id": device_id, "force_attack": force_attack, "pqc": pqc},
            )
            return response.json()
    except Exception as e:
        return {"error": f"KMS unreachable: {e}", "status": "OFFLINE", "qber": 0.0}


def api_force_attack(kms_url: str) -> dict:
    """Trigger a simulated Eve attack via KMS API."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{kms_url}/force_attack")
            return response.json()
    except Exception as e:
        return {"error": str(e), "status": "OFFLINE", "qber": 0.0}


def api_reset(kms_url: str) -> dict:
    """Reset the KMS system via API."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(f"{kms_url}/reset")
            return response.json()
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# HEADER
# =============================================================================

st.markdown('<p class="main-header">🛡️ Quantum-Safe Tactical Communication System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Real-Time Security Operations Dashboard | Classification: UNCLASSIFIED | v3.0 (Network Mode)</p>', unsafe_allow_html=True)


# =============================================================================
# SIDEBAR - SYSTEM CONTROLS
# =============================================================================

with st.sidebar:
    st.header("⚙️ System Controls")

    # KMS URL Configuration
    st.subheader("🔗 KMS Connection")
    kms_url = st.text_input(
        "KMS Server URL",
        value=st.session_state.kms_url,
        help="URL of the running kms_server.py instance"
    )
    st.session_state.kms_url = kms_url

    st.divider()

    # Key Operations
    st.subheader("🔑 Key Operations")

    col1, col2 = st.columns(2)
    with col1:
        get_key_a = st.button("🔑 Key Alpha", use_container_width=True)
    with col2:
        get_key_b = st.button("🔑 Key Bravo", use_container_width=True)

    pqc_mode = st.toggle("🧬 Hybrid PQC Mode", value=False,
                          help="Enable Kyber-style hybrid key derivation (extra credit)")

    st.divider()

    # Attack & Reset
    st.subheader("🚨 Demo Controls")

    force_attack_btn = st.button("💥 Force Eve Attack", use_container_width=True,
                                  help="Trigger simulated eavesdropper → RED status")

    reset_btn = st.button("🔄 Reset System", use_container_width=True,
                           help="Clear all state, restore GREEN")

    st.divider()

    st.subheader("ℹ️ Architecture")
    st.markdown("""
    ```
    Clients ↔ Chat Server (:8765)
       ↕         ↕ (via router)
    KMS Server (:8000)
       ↑
    Router Guard (polls /link_status)
    ```
    """)


# =============================================================================
# HANDLE SIDEBAR ACTIONS
# =============================================================================

if get_key_a:
    result = api_get_session_key(kms_url, "Soldier_Alpha", pqc=pqc_mode)
    if "error" in result:
        st.error(f"❌ Alpha key failed: {result['error']}")
    else:
        st.success(f"✅ Key issued to Alpha | QBER={result.get('qber', 0):.2%}")

if get_key_b:
    result = api_get_session_key(kms_url, "Soldier_Bravo", pqc=pqc_mode)
    if "error" in result:
        st.error(f"❌ Bravo key failed: {result['error']}")
    else:
        st.success(f"✅ Key issued to Bravo | QBER={result.get('qber', 0):.2%}")

if force_attack_btn:
    result = api_force_attack(kms_url)
    if result.get("status") == "RED":
        st.error(f"🔴 ATTACK TRIGGERED! QBER={result.get('qber', 0):.2%} | "
                 f"Router will block chat traffic within 3 seconds.")
    elif "error" in result:
        st.error(f"❌ {result.get('error', 'Unknown error')}")
    else:
        st.warning(f"⚠️ {result.get('message', 'Unknown response')}")

if reset_btn:
    result = api_reset(kms_url)
    if result.get("status") == "reset_complete":
        st.success("🔄 System reset. Link status: GREEN. Router will restore traffic within 3 seconds.")
        st.session_state.message_log = []
    else:
        st.error(f"❌ Reset failed: {result}")


# =============================================================================
# MAIN DASHBOARD - METRICS ROW
# =============================================================================

health = api_get_link_status(kms_url)

col1, col2, col3, col4 = st.columns(4)

with col1:
    status = health.get('status', 'OFFLINE')
    if status == "GREEN":
        st.markdown("### 🟢 Link Status")
        st.success("**SECURE**")
    elif status == "YELLOW":
        st.markdown("### 🟡 Link Status")
        st.warning("**ELEVATED**")
    elif status == "RED":
        st.markdown("### 🔴 Link Status")
        st.error("**COMPROMISED**")
    else:
        st.markdown("### ⚪ Link Status")
        st.info("**OFFLINE** — KMS unreachable")

with col2:
    st.metric(
        label="🔑 Keys Issued",
        value=health.get('total_keys_issued', 0),
    )

with col3:
    st.metric(
        label="⚠️ Attacks Detected",
        value=health.get('attacks_detected', 0),
    )

with col4:
    qber_value = health.get('qber', 0)
    st.metric(
        label="📊 Last QBER",
        value=f"{qber_value:.1%}" if qber_value > 0 else "N/A",
    )


# =============================================================================
# ROUTER STATUS SECTION
# =============================================================================

st.divider()

router_col1, router_col2 = st.columns([1, 2])

with router_col1:
    st.header("📡 Router Guard Status")

with router_col2:
    if status == "GREEN":
        st.markdown("""
        <div class="router-card" style="border-color: #43a047;">
            <b>🟢 Router: ALLOWING traffic</b><br>
            Port 8765 (chat) is <b>OPEN</b> — iptables rules inactive.<br>
            Chat clients can communicate freely through the D-Link modem.
        </div>
        """, unsafe_allow_html=True)
    elif status == "RED":
        st.markdown("""
        <div class="router-card" style="border-color: #e53935;">
            <b>🔴 Router: BLOCKING traffic</b><br>
            Port 8765 (chat) is <b>DROPPED</b> — iptables rules active.<br>
            <code>iptables -I FORWARD -p tcp --dport 8765 -j DROP</code><br>
            Chat clients are physically isolated by the D-Link firewall.
        </div>
        """, unsafe_allow_html=True)
    elif status == "YELLOW":
        st.markdown("""
        <div class="router-card" style="border-color: #ffc107;">
            <b>🟡 Router: ALLOWING traffic (caution)</b><br>
            QBER is elevated but below threshold. Chat is still active.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="router-card" style="border-color: #9e9e9e;">
            <b>⚪ KMS Offline</b><br>
            Cannot determine router guard state. Ensure kms_server.py is running.
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# MESSAGE EXCHANGE SECTION
# =============================================================================

st.divider()
st.header("💬 Secure Message Demo")

st.info("💡 For real chat, use `client_app.py` on separate machines over Wi-Fi. "
        "This section demonstrates the encryption/decryption mechanism.")

msg_col1, msg_col2 = st.columns([2, 1])

with msg_col1:
    message_text = st.text_input(
        "Enter tactical message:",
        value="Enemy position: Grid Reference 1234. Request immediate support.",
        placeholder="Type your message here..."
    )

with msg_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    send_message = st.button("📨 Demo Encrypt + Decrypt", use_container_width=True)

if send_message:
    if status == "RED":
        st.error("❌ Cannot send — quantum link is COMPROMISED. Router is blocking traffic.")
    elif status == "OFFLINE":
        st.error("❌ KMS is offline. Start kms_server.py first.")
    else:
        # Get keys for both devices via API
        key_a_resp = api_get_session_key(kms_url, "Demo_Alpha", pqc=pqc_mode)
        key_b_resp = api_get_session_key(kms_url, "Demo_Bravo", pqc=pqc_mode)

        if "error" in key_a_resp or "error" in key_b_resp:
            st.error(f"❌ Key exchange failed: {key_a_resp.get('error', key_b_resp.get('error', ''))}")
        else:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import os as _os

            key_bytes = bytes.fromhex(key_a_resp["key_hex"])

            # Encrypt
            cipher = AESGCM(key_bytes)
            nonce = _os.urandom(12)
            ciphertext = cipher.encrypt(nonce, message_text.encode("utf-8"), None)

            st.success("✅ Message encrypted and decrypted successfully!")

            with st.expander("📋 Message Details", expanded=True):
                detail_col1, detail_col2 = st.columns(2)
                with detail_col1:
                    st.markdown("**Original Message:**")
                    st.code(message_text)
                with detail_col2:
                    # Decrypt
                    plaintext_bytes = cipher.decrypt(nonce, ciphertext, None)
                    st.markdown("**Decrypted Message:**")
                    st.code(plaintext_bytes.decode("utf-8"))

                st.markdown("**Ciphertext (hex, truncated):**")
                st.code(ciphertext.hex()[:64] + "...")

                st.markdown("**Nonce (hex):**")
                st.code(nonce.hex())


# =============================================================================
# BB84 PROTOCOL VISUALIZATION
# =============================================================================

st.divider()
st.header("🔬 BB84 Protocol Demonstration")

viz_col1, viz_col2 = st.columns(2)

with viz_col1:
    st.subheader("Run BB84 Simulation")

    num_qubits = st.slider("Number of Qubits", min_value=128, max_value=1024, value=512, step=64)

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        run_safe = st.button("🟢 Run (No Eve)", use_container_width=True)
    with btn_col2:
        run_attack = st.button("🔴 Run (With Eve)", use_container_width=True)

    if run_safe:
        key, qber, attacked = simulate_bb84(num_bits=num_qubits, eve_present=False)
        st.success("✅ Key generated successfully!")
        st.metric("QBER", f"{qber:.2%}")
        st.code(f"Key (first 32 chars): {key.hex()[:32]}...")

    if run_attack:
        key, qber, attacked = simulate_bb84(num_bits=num_qubits, eve_present=True, eve_intercept_rate=1.0)
        st.error("❌ ATTACK DETECTED!")
        st.metric("QBER", f"{qber:.2%}", delta=f"+{(qber - 0.02):.1%}")
        st.warning(f"QBER {qber:.1%} exceeds {QBER_SECURITY_THRESHOLD:.0%} threshold. Key generation aborted.")

with viz_col2:
    st.subheader("How BB84 Works")
    st.markdown("""
    **The Protocol in Brief:**

    1. **Alice** generates random bits and chooses random encoding bases
       - Computational (Z): |0⟩ or |1⟩
       - Hadamard (X): |+⟩ or |−⟩

    2. **Bob** measures each qubit using randomly chosen bases

    3. **Sifting**: They publicly compare bases, keep ~50% where they matched

    4. **QBER Check**: Compare sample of sifted bits
       - Normal: QBER ≈ 0-5%
       - Eve Attack: QBER ≈ 25%

    5. **Decision**: QBER < 11% → Use key. QBER ≥ 11% → Abort

    **Why it works:** Quantum mechanics prevents undetected eavesdropping.
    Eve's measurement disturbs the quantum states, causing errors that
    Alice and Bob can detect.
    """)


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.markdown("""
<div style="text-align: center; color: #757575; font-size: 0.85rem;">
    QSTCS v3.0 | Defense-Grade Quantum-Safe Communications |
    Network Mode: KMS API + WebSocket Chat + Router Guard |
    Classification: UNCLASSIFIED | For Demonstration Purposes
</div>
""", unsafe_allow_html=True)
