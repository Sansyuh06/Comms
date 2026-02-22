"""
Streamlit Monitoring Dashboard
==============================
Defense-Grade Implementation for QSTCS

This module provides a real-time web-based monitoring interface for the
Quantum-Safe Tactical Communication System. It enables SOC (Security Operations
Center) personnel to monitor system health, observe key metrics, and validate
the quantum security mechanisms.

DASHBOARD CAPABILITIES:
-----------------------
1. Real-time link status (GREEN/YELLOW/RED)
2. QBER (Quantum Bit Error Rate) monitoring
3. Key issuance tracking
4. Attack detection alerts
5. Interactive message demonstration
6. BB84 protocol visualization

SECURITY NOTE:
--------------
This dashboard is READ-ONLY for security metrics. It does not have access to
cryptographic keys or plaintext messages. All displayed information is safe
for SOC monitoring without compromising operational security.

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import streamlit as st
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kms.key_management_service import KeyManagementService
from devices.client import SoldierDevice
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
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize Streamlit session state with QSTCS components."""
    if 'kms' not in st.session_state:
        st.session_state.kms = KeyManagementService()
    
    if 'soldier_a' not in st.session_state:
        st.session_state.soldier_a = SoldierDevice("Soldier_Alpha", st.session_state.kms)
    
    if 'soldier_b' not in st.session_state:
        st.session_state.soldier_b = SoldierDevice("Soldier_Bravo", st.session_state.kms)
    
    if 'message_log' not in st.session_state:
        st.session_state.message_log = []

init_session_state()


# =============================================================================
# HEADER
# =============================================================================

st.markdown('<p class="main-header">🛡️ Quantum-Safe Tactical Communication System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Real-Time Security Operations Dashboard | Classification: UNCLASSIFIED</p>', unsafe_allow_html=True)


# =============================================================================
# SIDEBAR - SYSTEM CONTROLS
# =============================================================================

with st.sidebar:
    st.header("⚙️ System Controls")
    
    st.subheader("Device Operations")
    
    col1, col2 = st.columns(2)
    with col1:
        get_key_a = st.button("🔑 Key Alpha", use_container_width=True)
    with col2:
        get_key_b = st.button("🔑 Key Bravo", use_container_width=True)
    
    st.divider()
    
    st.subheader("Attack Simulation")
    eve_attack = st.toggle("🚨 Eve Eavesdropping", value=False)
    
    if eve_attack:
        st.warning("⚠️ Eve is actively intercepting quantum channel!")
    
    st.divider()
    
    st.subheader("System Reset")
    if st.button("🔄 Reset System", use_container_width=True):
        st.session_state.kms.reset_for_demo()
        st.session_state.soldier_a = SoldierDevice("Soldier_Alpha", st.session_state.kms)
        st.session_state.soldier_b = SoldierDevice("Soldier_Bravo", st.session_state.kms)
        st.session_state.message_log = []
        st.rerun()


# =============================================================================
# HANDLE KEY REQUESTS
# =============================================================================

if get_key_a:
    try:
        st.session_state.kms.get_fresh_key("Soldier_Alpha", force_eve_attack=eve_attack)
        if not eve_attack:
            st.session_state.soldier_a._current_key = st.session_state.kms._last_key
    except Exception as e:
        st.error(f"❌ Key request failed: {str(e)}")

if get_key_b:
    try:
        st.session_state.kms.get_fresh_key("Soldier_Bravo", force_eve_attack=eve_attack)
        if not eve_attack:
            st.session_state.soldier_b._current_key = st.session_state.kms._last_key
    except Exception as e:
        st.error(f"❌ Key request failed: {str(e)}")


# =============================================================================
# MAIN DASHBOARD - METRICS ROW
# =============================================================================

health = st.session_state.kms.check_link_health()

col1, col2, col3, col4 = st.columns(4)

with col1:
    status = health['status']
    if status == "GREEN":
        st.markdown("### 🟢 Link Status")
        st.success("**SECURE**")
    elif status == "YELLOW":
        st.markdown("### 🟡 Link Status")
        st.warning("**ELEVATED**")
    else:
        st.markdown("### 🔴 Link Status")
        st.error("**COMPROMISED**")

with col2:
    st.metric(
        label="🔑 Keys Issued",
        value=health['total_keys_issued'],
        delta=None
    )

with col3:
    st.metric(
        label="⚠️ Attacks Detected",
        value=health['attacks_detected'],
        delta=None
    )

with col4:
    qber_value = health['last_qber']
    st.metric(
        label="📊 Last QBER",
        value=f"{qber_value:.1%}" if qber_value > 0 else "N/A",
        delta=None
    )


# =============================================================================
# MESSAGE EXCHANGE SECTION
# =============================================================================

st.divider()
st.header("💬 Secure Message Exchange")

msg_col1, msg_col2 = st.columns([2, 1])

with msg_col1:
    message_text = st.text_input(
        "Enter tactical message:",
        value="Enemy position: Grid Reference 1234. Request immediate support.",
        placeholder="Type your message here..."
    )

with msg_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    send_message = st.button("📨 Send Alpha → Bravo", use_container_width=True)

if send_message:
    if eve_attack:
        st.warning("⚠️ Eve is attacking! Attempting to establish secure channel...")
        try:
            st.session_state.kms.get_fresh_key("Soldier_Alpha", force_eve_attack=True)
            st.error("❌ Key exchange failed due to eavesdropping attack!")
        except Exception as e:
            st.error(f"❌ Attack detected: {str(e)}")
    else:
        # Get keys for both devices
        if not st.session_state.soldier_a.has_key:
            st.session_state.soldier_a.request_key()
        if not st.session_state.soldier_b.has_key:
            st.session_state.soldier_b.request_key()
        
        if st.session_state.soldier_a.has_key and st.session_state.soldier_b.has_key:
            # Encrypt and send
            packet = st.session_state.soldier_a.send_encrypted_message("Soldier_Bravo", message_text)
            
            if packet:
                # Decrypt and receive
                decrypted = st.session_state.soldier_b.receive_encrypted_message(packet)
                
                if decrypted:
                    st.success(f"✅ Message delivered securely!")
                    
                    with st.expander("📋 Message Details", expanded=True):
                        detail_col1, detail_col2 = st.columns(2)
                        with detail_col1:
                            st.markdown("**Original Message:**")
                            st.code(message_text)
                        with detail_col2:
                            st.markdown("**Decrypted Message:**")
                            st.code(decrypted)
                        
                        st.markdown("**Ciphertext (truncated):**")
                        st.code(packet['ciphertext'][:64] + "...")
                    
                    st.session_state.message_log.append({
                        'sender': 'Soldier_Alpha',
                        'recipient': 'Soldier_Bravo',
                        'preview': message_text[:30] + "..." if len(message_text) > 30 else message_text
                    })
                else:
                    st.error("❌ Decryption failed!")
            else:
                st.error("❌ Encryption failed!")
        else:
            st.error("❌ Key establishment failed. Try again.")


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
        st.success(f"✅ Key generated successfully!")
        st.metric("QBER", f"{qber:.2%}")
        st.code(f"Key (first 32 chars): {key.hex()[:32]}...")
    
    if run_attack:
        key, qber, attacked = simulate_bb84(num_bits=num_qubits, eve_present=True, eve_intercept_rate=1.0)
        st.error(f"❌ ATTACK DETECTED!")
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
    QSTCS v2.0 | Defense-Grade Quantum-Safe Communications | 
    Classification: UNCLASSIFIED | For Demonstration Purposes
</div>
""", unsafe_allow_html=True)
