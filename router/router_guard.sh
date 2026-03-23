#!/bin/sh

# Quantum-aware router guard (OpenWrt-style simulation)

KMS_HOST="192.168.1.100"
KMS_PORT="8000"
CHAT_PORTS="1919 1920 1921 1922 1923 1924 1925"
POLL_INTERVAL=3
RED_THRESHOLD=2
APPLY_FIREWALL=1

PRIMARY_IP="192.168.1.100"
BACKUP_IP="192.168.1.150"
PRIMARY_NET="192.168.1.0/24"
BACKUP_NET="192.168.2.0/24"
BACKUP_NET_IP="192.168.2.1"

CURRENT_LEVEL=1
CURRENT_PORT=""
CURRENT_IP="$PRIMARY_IP"
CURRENT_NET="$PRIMARY_NET"
BURNED_PORTS=""
BURNED_IPS=""
BURNED_NETS=""
RED_STREAK=0

log() {
  echo "[router_guard] $*"
}

contains_word() {
  case " $1 " in
    *" $2 "*) return 0 ;;
    *) return 1 ;;
  esac
}

next_available() {
  pool="$1"
  burned="$2"
  for item in $pool; do
    if ! contains_word "$burned" "$item"; then
      echo "$item"
      return 0
    fi
  done
  echo ""
}

extract_json_str() {
  echo "$1" | sed -n 's/.*"'$2'"[ ]*:[ ]*"\([^"]*\)".*/\1/p'
}

extract_json_num() {
  echo "$1" | sed -n 's/.*"'$2'"[ ]*:[ ]*\([0-9]*\).*/\1/p'
}

init_port() {
  if [ -z "$CURRENT_PORT" ]; then
    for p in $CHAT_PORTS; do
      CURRENT_PORT="$p"
      break
    done
  fi
}

apply_firewall() {
  status="$1"

  if [ "$APPLY_FIREWALL" -ne 1 ]; then
    return
  fi

  if ! command -v iptables >/dev/null 2>&1; then
    log "iptables not found; skipping firewall changes"
    return
  fi

  iptables -N QCHAT 2>/dev/null
  iptables -F QCHAT
  iptables -C INPUT -j QCHAT 2>/dev/null || iptables -I INPUT 1 -j QCHAT
  iptables -C FORWARD -j QCHAT 2>/dev/null || iptables -I FORWARD 1 -j QCHAT

  for p in $BURNED_PORTS; do
    iptables -A QCHAT -p tcp --dport "$p" -j DROP
  done

  if [ "$CURRENT_LEVEL" -ge 4 ]; then
    iptables -A QCHAT -p tcp -j DROP
    return
  fi

  if [ "$status" = "RED" ]; then
    iptables -A QCHAT -p tcp --dport "$CURRENT_PORT" -j DROP
  else
    iptables -A QCHAT -p tcp --dport "$CURRENT_PORT" -j ACCEPT
  fi

  iptables -A QCHAT -j RETURN
}

escalate_to() {
  target="$1"
  if [ "$CURRENT_LEVEL" -ge "$target" ]; then
    return
  fi

  CURRENT_LEVEL="$target"

  if [ "$CURRENT_LEVEL" -eq 2 ]; then
    log "Escalation -> Level 2 (switching IP)"
    CURRENT_IP="$BACKUP_IP"
    BURNED_PORTS=""
    CURRENT_PORT=""
    init_port
    return
  fi

  if [ "$CURRENT_LEVEL" -eq 3 ]; then
    log "Escalation -> Level 3 (switching network)"
    CURRENT_NET="$BACKUP_NET"
    CURRENT_IP="$BACKUP_NET_IP"
    BURNED_PORTS=""
    CURRENT_PORT=""
    init_port
    return
  fi

  if [ "$CURRENT_LEVEL" -ge 4 ]; then
    log "Escalation -> Level 4 (LOCKDOWN)"
    return
  fi
}

handle_red_event() {
  if [ "$CURRENT_LEVEL" -eq 1 ]; then
    if ! contains_word "$BURNED_PORTS" "$CURRENT_PORT"; then
      BURNED_PORTS="$BURNED_PORTS $CURRENT_PORT"
      log "Level 1: burned port $CURRENT_PORT"
    fi
    next_port=$(next_available "$CHAT_PORTS" "$BURNED_PORTS")
    if [ -n "$next_port" ]; then
      CURRENT_PORT="$next_port"
      log "Level 1: rotating to port $CURRENT_PORT"
      return
    fi
    escalate_to 2
    return
  fi

  if [ "$CURRENT_LEVEL" -eq 2 ]; then
    if ! contains_word "$BURNED_IPS" "$CURRENT_IP"; then
      BURNED_IPS="$BURNED_IPS $CURRENT_IP"
      log "Level 2: burned IP $CURRENT_IP"
    fi
    next_ip=$(next_available "$PRIMARY_IP $BACKUP_IP" "$BURNED_IPS")
    if [ -n "$next_ip" ]; then
      CURRENT_IP="$next_ip"
      log "Level 2: rotating to IP $CURRENT_IP"
      return
    fi
    escalate_to 3
    return
  fi

  if [ "$CURRENT_LEVEL" -eq 3 ]; then
    if ! contains_word "$BURNED_NETS" "$CURRENT_NET"; then
      BURNED_NETS="$BURNED_NETS $CURRENT_NET"
      log "Level 3: burned network $CURRENT_NET"
    fi
    next_net=$(next_available "$PRIMARY_NET $BACKUP_NET" "$BURNED_NETS")
    if [ -n "$next_net" ]; then
      CURRENT_NET="$next_net"
      log "Level 3: rotating to network $CURRENT_NET"
      return
    fi
    escalate_to 4
  fi
}

init_port

log "Starting router guard (current port $CURRENT_PORT, level $CURRENT_LEVEL)"

while true; do
  JSON=$(curl -s "http://$KMS_HOST:$KMS_PORT/link_status")
  STATUS=$(extract_json_str "$JSON" status)
  KMS_LEVEL=$(extract_json_num "$JSON" escalation_level)

  if [ -z "$STATUS" ]; then
    log "KMS unreachable or invalid response"
    sleep "$POLL_INTERVAL"
    continue
  fi

  if [ -n "$KMS_LEVEL" ]; then
    if [ "$KMS_LEVEL" -gt "$CURRENT_LEVEL" ]; then
      escalate_to "$KMS_LEVEL"
    fi
  fi

  if [ "$STATUS" = "RED" ]; then
    RED_STREAK=$((RED_STREAK + 1))
  else
    RED_STREAK=0
  fi

  if [ "$RED_STREAK" -ge "$RED_THRESHOLD" ]; then
    log "RED threshold reached at level $CURRENT_LEVEL"
    handle_red_event
    RED_STREAK=0
  fi

  log "Level $CURRENT_LEVEL status=$STATUS port=$CURRENT_PORT ip=$CURRENT_IP net=$CURRENT_NET"
  apply_firewall "$STATUS"

  if [ "$CURRENT_LEVEL" -ge 4 ]; then
    log "LOCKDOWN active. Manual reset required."
    sleep "$POLL_INTERVAL"
    continue
  fi

  sleep "$POLL_INTERVAL"
done
