#!/bin/sh
# =============================================================================
# QSTCS Router Gatekeeper — router_guard.sh
# =============================================================================
# Quantum-Safe Tactical Communication System
#
# PURPOSE:
#   This script runs on a D-Link DSL-2750U (OpenWrt/BusyBox) and polls
#   the KMS server's /link_status endpoint every few seconds. Based on
#   the quantum link health (GREEN or RED), it dynamically inserts or
#   removes iptables firewall rules to ALLOW or BLOCK chat traffic.
#
# WHY THE ROUTER MATTERS:
#   All WebSocket chat traffic on port 8765 physically transits this router.
#   When the quantum channel is compromised (Eve detected, QBER > 11%),
#   this script drops packets at the kernel firewall level — a real,
#   physical network cutoff, not a software flag.
#
# DEPLOYMENT:
#   scp router_guard.sh root@192.168.1.1:/tmp/
#   ssh root@192.168.1.1 "chmod +x /tmp/router_guard.sh && /tmp/router_guard.sh"
#
# REQUIREMENTS:
#   - wget (standard on BusyBox/OpenWrt)
#   - iptables
#   - grep, cut (standard BusyBox)
#
# Author: QSTCS Development Team
# Classification: UNCLASSIFIED
# =============================================================================

# ---- CONFIGURATION ----
KMS_HOST="192.168.1.100"    # Change to YOUR laptop IP
KMS_PORT="8000"
CHAT_PORT="8765"            # Chat server WebSocket port
POLL_INTERVAL=3             # Seconds between polls
# ---- END CONFIGURATION ----

# Track current state to avoid redundant iptables calls
CURRENT_STATE="UNKNOWN"

# =============================================================================
# CLEANUP FUNCTION
# =============================================================================
cleanup() {
    echo ""
    echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Shutting down gatekeeper..."
    
    # Remove any DROP rules we inserted
    iptables -D FORWARD -p tcp --dport "$CHAT_PORT" -j DROP 2>/dev/null
    iptables -D FORWARD -p tcp --sport "$CHAT_PORT" -j DROP 2>/dev/null
    
    echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Firewall rules cleaned up. Chat traffic ALLOWED."
    echo "[GUARD] Gatekeeper stopped."
    exit 0
}

# Ensure cleanup runs on exit (Ctrl+C, kill, etc.)
trap cleanup EXIT INT TERM

# =============================================================================
# BANNER
# =============================================================================
echo ""
echo "=================================================================="
echo "  QSTCS Router Gatekeeper — D-Link DSL-2750U"
echo "=================================================================="
echo "  KMS Endpoint:  http://${KMS_HOST}:${KMS_PORT}/link_status"
echo "  Chat Port:     ${CHAT_PORT} (WebSocket)"
echo "  Poll Interval: ${POLL_INTERVAL}s"
echo "  Action:        DROP chat traffic when quantum link is RED"
echo "=================================================================="
echo ""

# =============================================================================
# MAIN POLLING LOOP
# =============================================================================
echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Starting quantum link monitor..."
echo ""

while true; do
    # Poll the KMS /link_status endpoint
    RESPONSE=$(wget -qO- "http://${KMS_HOST}:${KMS_PORT}/link_status" 2>/dev/null)
    
    if [ -z "$RESPONSE" ]; then
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | ⚠️  KMS unreachable at ${KMS_HOST}:${KMS_PORT} — retrying..."
        sleep "$POLL_INTERVAL"
        continue
    fi
    
    # Parse the "status" field from JSON using BusyBox-compatible tools
    # Expected JSON: {"status":"GREEN","qber":0.03,...}
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
    QBER=$(echo "$RESPONSE" | grep -o '"qber":[0-9.]*' | head -1 | cut -d':' -f2)
    
    if [ -z "$STATUS" ]; then
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | ⚠️  Could not parse status from response"
        sleep "$POLL_INTERVAL"
        continue
    fi
    
    # ---- STATE TRANSITION: GREEN → RED ----
    if [ "$STATUS" = "RED" ] && [ "$CURRENT_STATE" != "RED" ]; then
        echo ""
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | 🔴 QUANTUM BREACH DETECTED!"
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | QBER = ${QBER} (exceeds 11% threshold)"
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Executing: iptables -I FORWARD -p tcp --dport ${CHAT_PORT} -j DROP"
        
        iptables -I FORWARD -p tcp --dport "$CHAT_PORT" -j DROP
        iptables -I FORWARD -p tcp --sport "$CHAT_PORT" -j DROP
        
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | ❌ Chat traffic BLOCKED at network layer"
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | All packets to/from port ${CHAT_PORT} are being DROPPED"
        echo ""
        
        CURRENT_STATE="RED"
    
    # ---- STATE TRANSITION: RED → GREEN ----
    elif [ "$STATUS" = "GREEN" ] && [ "$CURRENT_STATE" = "RED" ]; then
        echo ""
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | 🟢 Quantum link RESTORED"
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | QBER = ${QBER} (within safe range)"
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Removing firewall block..."
        
        iptables -D FORWARD -p tcp --dport "$CHAT_PORT" -j DROP 2>/dev/null
        iptables -D FORWARD -p tcp --sport "$CHAT_PORT" -j DROP 2>/dev/null
        
        echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | ✓ Chat traffic ALLOWED"
        echo ""
        
        CURRENT_STATE="GREEN"
    
    # ---- INITIAL STATE (first poll) ----
    elif [ "$CURRENT_STATE" = "UNKNOWN" ]; then
        if [ "$STATUS" = "GREEN" ] || [ "$STATUS" = "YELLOW" ]; then
            echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | 🟢 Status: ${STATUS} | QBER = ${QBER} — Chat traffic ALLOWED"
            CURRENT_STATE="GREEN"
        else
            echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | 🔴 Status: ${STATUS} | QBER = ${QBER} — BLOCKING chat traffic"
            iptables -I FORWARD -p tcp --dport "$CHAT_PORT" -j DROP
            iptables -I FORWARD -p tcp --sport "$CHAT_PORT" -j DROP
            CURRENT_STATE="RED"
        fi
    
    # ---- NO STATE CHANGE (steady state, log periodically) ----
    # Uncomment the next line for verbose logging during demos:
    # echo "[GUARD] $(date '+%Y-%m-%d %H:%M:%S') | Status: ${STATUS} | QBER = ${QBER} (no change)"
    fi
    
    sleep "$POLL_INTERVAL"
done
