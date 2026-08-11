#!/usr/bin/env bash
# Live flash progress per port (Ctrl-C to stop): bash test/flash-progress.sh
while true; do
  printf '\033[2J\033[H%s  flash progress\n' "$(date +%H:%M:%S)"
  found=no
  for f in /tmp/.flashlocks/*.out; do
    [ -f "$f" ] || continue
    port=$(basename "$f" .out)
    line=$(tr '\r' '\n' < "$f" | grep '%' | tail -1)
    stage=$(echo "$line" | grep -oE 'Loading|Verifying')
    pct=$(echo "$line" | grep -oE '[0-9]+%' | tail -1)
    if pgrep -f "picotool load -v --bus ${port%%-*}" >/dev/null 2>&1; then
      echo "  port $port: ${stage:-starting} ${pct:-0%}"
      found=yes
    fi
  done
  [ "$found" = no ] && echo "  (no active flashes)"
  sleep 2
done
