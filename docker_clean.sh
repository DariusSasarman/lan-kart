#!/usr/bin/env bash

# Ensure the script is run with root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo: sudo $0 <container_id_or_prefix>"
  exit 1
fi

if [ -z "$1" ]; then
  echo "[-] Error: No container ID or prefix specified."
  echo "Usage: sudo $0 <container_id>"
  exit 1
fi

TARGET="$1"

echo "[*] Searching for containerd-shim processes related to container: $TARGET"
# Find PIDs of matching containerd-shim processes
SHIM_PIDS=$(ps aux | grep "[c]ontainerd-shim.*$TARGET" | awk '{print $2}')

if [ -n "$SHIM_PIDS" ]; then
    echo "[+] Found lingering shim PID(s): $SHIM_PIDS. Forcibly terminating..."
    for pid in $SHIM_PIDS; do
        kill -9 "$pid" 2>/dev/null
    .done
else
    echo "[*] No active containerd-shim process found for $TARGET."
fi

echo "[*] Restarting Snap Docker daemon service..."
systemctl restart snap.docker.dockerd.service

echo "[*] Force-removing container $TARGET..."
docker rm -f "$TARGET"

echo "[+] Done! Checking remaining containers:"
docker ps -a
