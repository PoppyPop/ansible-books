#!/usr/bin/env bash
set -euo pipefail

# --- CONFIG ---
THRESHOLD="90.00"            # percent
DURATION_SECONDS=300         # 5 minutes sustained
INTERVAL_SECONDS=60          # script is expected to run every 60s
SECOND_ACTION_WINDOW=1800    # 30 minutes
EXCLUDE_VMIDS=(102)          # never act on these
STATE_DIR="/var/lib/pve-psi-watch"
# --------------

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" || true

NODE="$(hostname -s)"

required_bad=$(( DURATION_SECONDS / INTERVAL_SECONDS ))
if (( required_bad < 1 )); then required_bad=1; fi

now_epoch="$(date +%s)"
now_iso="$(date -Is)"

is_excluded() {
  local id="$1"
  for x in "${EXCLUDE_VMIDS[@]}"; do
    [[ "$x" == "$id" ]] && return 0
  done
  return 1
}

# List running guests on this node: "<type> <vmid>"
mapfile -t guests < <(
  {
    pvesh get "/nodes/${NODE}/qemu" --output-format json 2>/dev/null \
      | jq -r '.[] | select(.status=="running") | "qemu \(.vmid)"'
    pvesh get "/nodes/${NODE}/lxc" --output-format json 2>/dev/null \
      | jq -r '.[] | select(.status=="running") | "lxc \(.vmid)"'
  } | sort -u
)

for entry in "${guests[@]}"; do
  type="${entry%% *}"     # qemu|lxc
  vmid="${entry##* }"

  if is_excluded "$vmid"; then
    continue
  fi

  # Read both io pressure signals (strings like "0.00")
  read -r iosome iofull < <(
    pvesh get "/nodes/${NODE}/${type}/${vmid}/status/current" --output-format json 2>/dev/null \
      | jq -r '[.pressureiosome // "0.00", .pressureiofull // "0.00"] | @tsv'
  )

  # "bad" if either >= THRESHOLD
  is_bad="$(
    awk -v some="$iosome" -v full="$iofull" -v t="$THRESHOLD" '
      BEGIN { print ((some+0 >= t+0) || (full+0 >= t+0)) ? 1 : 0 }
    '
  )"

  count_file="${STATE_DIR}/${NODE}-${type}-${vmid}.count"
  last_action_file="${STATE_DIR}/${NODE}-${type}-${vmid}.last_action"

  count=0
  [[ -f "$count_file" ]] && count="$(cat "$count_file" 2>/dev/null || echo 0)"

  if [[ "$is_bad" == "1" ]]; then
    count=$((count+1))
  else
    count=0
  fi
  echo "$count" > "$count_file"

  if (( count < required_bad )); then
    continue
  fi

  # We've met sustained condition; decide whether to reboot or stop
  echo 0 > "$count_file"

  last_action_epoch=0
  [[ -f "$last_action_file" ]] && last_action_epoch="$(cat "$last_action_file" 2>/dev/null || echo 0)"

  within_window=0
  if (( last_action_epoch > 0 )) && (( (now_epoch - last_action_epoch) <= SECOND_ACTION_WINDOW )); then
    within_window=1
  fi

  if (( within_window == 1 )); then
    logger -t pve-psi-watch "${now_iso} ${NODE} ${type}/${vmid}: io pressure sustained (some=${iosome}, full=${iofull}) >= ${THRESHOLD}; second action within 30m -> STOP"
    echo "$now_epoch" > "$last_action_file"

    if [[ "$type" == "lxc" ]]; then
      pct stop "$vmid" || logger -t pve-psi-watch "Failed to stop CT ${vmid}"
    else
      qm stop "$vmid" || logger -t pve-psi-watch "Failed to stop VM ${vmid}"
    fi
  else
    logger -t pve-psi-watch "${now_iso} ${NODE} ${type}/${vmid}: io pressure sustained (some=${iosome}, full=${iofull}) >= ${THRESHOLD}; rebooting"
    echo "$now_epoch" > "$last_action_file"

    if [[ "$type" == "lxc" ]]; then
      pct reboot "$vmid" || logger -t pve-psi-watch "Failed to reboot CT ${vmid}"
    else
      qm reboot "$vmid" --timeout 60 || logger -t pve-psi-watch "Failed to reboot VM ${vmid}"
    fi
  fi
done
