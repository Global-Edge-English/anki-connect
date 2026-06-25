#!/bin/bash
# ---------------------------------------------------------------------------
# anki_hang_watch.sh  (system-wide)
#
# v1 watched only the Anki process. But during the real outage the watcher
# stayed silent => Anki's own CPU was NOT high => Anki is the VICTIM, starved
# by some OTHER process pinning the single vCPU. So we now watch TOTAL system
# CPU, and on a sustained pin we record the hottest process box-wide (and
# py-spy it if it happens to be python/anki).
#
# Run as ROOT (py-spy attach + /proc/PID/stack need it). Logs to
# /home/ankiuser/anki_hang_watch.log.
# ---------------------------------------------------------------------------
set -u
LOG=/home/ankiuser/anki_hang_watch.log
INTERVAL=15           # seconds between samples
HIGH=85               # % total system CPU busy that counts as "pinned"
NEED=4                # consecutive high samples before capture (~60s sustained)
DUMP_COOLDOWN=300     # min seconds between captures during a long episode
log(){ echo "$(date -Is) $*" >> "$LOG"; }

# system busy% over dt seconds, from /proc/stat (100 - idle share)
sys_cpu(){
  local dt=2 i1 t1 i2 t2 line v
  line=$(grep '^cpu ' /proc/stat); set -- $line; shift   # drop the "cpu" label
  i1=$4; t1=0; for v in "$@"; do t1=$((t1+v)); done       # idle=field4, total=sum
  sleep "$dt"
  line=$(grep '^cpu ' /proc/stat); set -- $line; shift
  i2=$4; t2=0; for v in "$@"; do t2=$((t2+v)); done
  local dt_t=$((t2-t1)) dt_i=$((i2-i1))
  [ "$dt_t" -le 0 ] && { echo 0; return; }
  echo $(( 100*(dt_t-dt_i)/dt_t ))
}

capture(){
  local pct=$1 TBL HOG HOGCMD
  log "=== HANG: system CPU ${pct}% sustained — capturing ==="
  # second top iteration has accurate live %CPU; grab its table
  TBL=$(top -b -n2 -d 1 -o %CPU | tac | awk '1;/PID +USER/{exit}' | tac)
  HOG=$(echo "$TBL" | awk '$1 ~ /^[0-9]+$/{print $1; exit}')   # hottest pid
  HOGCMD=$(ps -o comm= -p "$HOG" 2>/dev/null)
  {
    echo "--- top (live %CPU) ---"; echo "$TBL" | head -15
    echo "--- hottest: pid=$HOG comm=$HOGCMD ---"
    echo "cmdline: $(tr '\0' ' ' < "/proc/$HOG/cmdline" 2>/dev/null)"
    echo "kstack:"; head -8 "/proc/$HOG/stack" 2>/dev/null
    if echo "$HOGCMD" | grep -qiE 'python|anki'; then
      echo "--- py-spy dump of hottest (python/anki) ---"
      py-spy dump --pid "$HOG" --native 2>&1 \
        || py-spy dump --pid "$HOG" --nonblocking 2>&1 \
        || echo "py-spy FAILED"
    else
      echo "(hottest is NOT python/anki — identify it from top/cmdline above)"
    fi
    echo "--- :8765 conns ---"; ss -tnpH 'sport = :8765' 2>/dev/null | head
    echo "--- end ---"
  } >> "$LOG" 2>&1
}

log "anki_hang_watch (system-wide) started"
streak=0; last_dump=0
while true; do
  pct=$(sys_cpu)
  if [ "${pct:-0}" -ge "$HIGH" ]; then
    streak=$((streak+1)); log "system cpu ${pct}% (streak ${streak}/${NEED})"
    now=$(date +%s)
    if [ "$streak" -ge "$NEED" ] && [ $((now-last_dump)) -ge "$DUMP_COOLDOWN" ]; then
      capture "$pct"; last_dump=$now
    fi
  else
    [ "$streak" -gt 0 ] && log "system cpu ${pct}% (recovered)"
    streak=0
  fi
  sleep "$INTERVAL"
done
