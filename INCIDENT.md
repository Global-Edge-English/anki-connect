# Incident: intermittent `/v1/status` 503 outages (AnkiConnect timeouts)

**Status:** ROOT CAUSE FOUND + FIXED IN CODE. Pending production verification
(re-run the leak probe) and ~1 week of clean monitoring before stopgaps are
removed. The leak was pinpointed to one endpoint — `getDeckInfo` — and fixed in
the addon (no Anki changes).

**Root cause (one line):** a **reference-cycle memory leak in `getDeckInfo`** — a
recursive nested closure retained the entire deck tree, and because Anki runs
`gc.disable()` the cycle was never collected — grew the Anki process on every
poll until it exhausted the 960 MB droplet's RAM + swap, thrashed swap, starved
the single vCPU so AnkiConnect's cooperative MainThread couldn't run → `version`
healthcheck timed out → `/v1/status` `503 DEGRADED` on **all** environments →
OOM kill + 5 s systemd restart, ending each episode.

---

## Symptom

- BetterStack / UptimeRobot report `GET /v1/status` → **503**, body
  `{"api_status":"DEGRADED"}`, across **prod + ge-english + staging at once**.
- Episodes are intermittent and last ~75 min to ~6 h.
- Sentry: `ECONNABORTED timeout of 30000ms` on `/v1/anki/getcard`, `/answer`,
  `/getowndeckstats`, and mostly `[Anki API] status`.

## Architecture (key facts)

- **Anki droplet:** host `anki-desktop-gui`, private IP `10.104.0.3`, public
  `152.42.214.228`. **960 MB RAM + 1 GB swap.** Timezone **UTC** (`Etc/UTC`).
  Runs full GUI Anki via **x11vnc** as systemd **`anki.service`** (user
  `ankiuser`, uid 1000). AnkiConnect HTTP API on **:8765**.
- **AnkiConnect is single-threaded:** served on Anki's Qt **MainThread** via a
  cooperative `QTimer` pump ([utils/network.py](utils/network.py),
  `AjaxServer`). Anything that ties up the MainThread (or starves the box)
  freezes port 8765 entirely. (The `waitress` threads seen in py-spy are Anki's
  *internal* media server `aqt/mediasrv.py`, **not** AnkiConnect.)
- **API server (studyplan2021):** Node/Express, talks to AnkiConnect via
  `src/services/ankiService.js` (axios, **30 s** timeout, keep-alive pool
  maxSockets 4). `/v1/status` → `getStatus` calls AnkiConnect `version` wrapped
  in `withTimeout(~1.5 s)` → returns 503 fast; the 30 s `ECONNABORTED` lines are
  the *orphaned background* axios calls finishing later. **prod, ge-english, and
  staging all point at the one AnkiConnect** (coupling risk — staging can stall
  prod).
- API logs: `/home/studyplan/studyplan_production/logs/api/` —
  `error.*.log[.gz]` (JSON, has `timestamp`), `access.*.log` (JSON, **no
  per-line timestamp**), `app.*.log`.

## Episodes (UTC)

| Date | Window (UTC) | Notes |
|---|---|---|
| 2026-05-30 | ~11:00 | small burst |
| 2026-06-02 | ~03:00 | small burst |
| 2026-06-07 | 19:00 → 01:30 (+1d) | ~6 h; peak 22:00 (178 status errors) |
| 2026-06-19 | 00:30 → 01:45 | ~75 min; **OOM captured** |

Timezone note: DigitalOcean graphs render in the **browser's** zone (IST here);
droplet clock + cron + logs are **UTC**. IST = UTC+5:30, SGT = UTC+8.

## Root-cause evidence (2026-06-19 episode)

Kernel OOM log:
```
Jun 19 01:43:54 kernel: Out of memory: Killed process 1300346 (python)
   total-vm:2791200kB, anon-rss:595076kB ...
   oom-kill: ... task_memcg=/system.slice/anki.service, task=python
```
- The killed `python` was **Anki** (`task_memcg=/system.slice/anki.service`),
  ~581 MB anon-rss.
- New Anki (`pid 1749722`) started **01:43:59 UTC** — 5 s later (systemd
  auto-restart). Explains the changing PID (900675 → 1300346 → 1749722).
- DO graph during the pin: ~100% CPU **plus elevated `sys`** and a **~400 MB/s
  disk read** = the swap-thrash signature.
- `free -h`: 960 MB total, ~86 MB free, ~301 MB already in swap.
- Memory snapshot 05:03 UTC (≈3 h after restart): `memory.current` 367 MB,
  **anon 101 MB** (rest is reclaimable cache). OOM hits ~580 MB anon.

## Ruled out (with evidence — do NOT re-chase)

- **External backup** `anki_backup.sh` (cron `0 3 * * *` = **03:00 UTC**):
  measured **~35 s** total (tar 29 s + rclone 5.2 s). The 08:30-IST graph blip =
  this backup. Innocent.
- **Anki internal auto-backups:** 2.7 MB colpkgs every ~30 min; were *slow
  victims* (15–28 s writes) during the pin, not the cause. Corroborate timing.
- **studyplan API 3am deck-cleanup cron** (`cron.js`): 5–10 quick `deleteDeck`s.
- **Query *speed*:** `getDeckInfo` / `getNextReviewCard` / heatmap all return in
  **~0.02 s** over all 36 decks — never a latency/CPU-per-call problem.
  (`getDeckInfo` was nonetheless the *memory* leak — see Resolution.)
- **Other endpoints:** version polling, render path (`card.question/answer`),
  media serving, internal backups, cleanup cron — all measured **non-leaking**
  by the bisect probe. Only `getDeckInfo` leaked.

## Resolution: the leak — found and fixed

**How it was found (bisect probe):** `/usr/local/bin/anki_leak_probe.sh` hammers
each study endpoint 3000× and measures the cgroup `anon` delta. Results:

| endpoint | Δ anon / 3000 calls | verdict |
|---|---|---|
| `version` (control) | +4 MB | noise |
| `getNextReviewCard` no-render | −13 MB | clean |
| `getNextReviewCard` render | +12 MB | clean |
| **`getDeckInfo`** | **+231 MB (~77 KB/call)** | **LEAK** |
| `media/<file>` GET | −19 MB | clean |

**Mechanism:** `getDeckInfo` ([managers/note_manager.py](managers/note_manager.py))
indexed the full deck tree with a **recursive nested closure**:
```python
tree = collection.sched.deck_due_tree()   # whole protobuf deck tree
def _index(node):                          # closes over itself -> ref cycle
    tree_index[int(node.deck_id)] = node   # retains every protobuf node
    for child in node.children: _index(child)
_index(tree)
```
The self-referencing closure forms a `function ↔ cell` reference cycle that
retains `tree_index` → the entire deck tree. **Anki runs `gc.disable()`**
(`aqt/main.py:1859`), so the cyclic collector never runs and the cycle is never
freed. Every call leaked the whole tree (~scales with total deck count → got
worse as users/decks grew, hence "regressed"). `getDeckInfo` is called by both
`getCard` and `getOwnDeckStats` on every study interaction → activity-driven
growth → OOM every few days.

**Fix** (addon only — Anki untouched): iterative `while stack` walk storing plain
int tuples instead of protobuf nodes — no closure, no cycle, no retention. Plus a
CLAUDE.md rule ("Memory: Anki disables the cyclic GC — no per-request reference
cycles") so it's caught in review.

## Fix checklist

- [x] **Code fix** — `getDeckInfo` leak removed (`managers/note_manager.py`).
- [x] **Guardrail** — CLAUDE.md "no per-request reference cycles" rule added.
- [x] **Stopgaps applied** (remove after verification): `MemoryMax=750M` +
  `Restart=always` drop-in, and `0 18 UTC` daily `systemctl restart anki.service`.
- [ ] **Verify** — re-run `/usr/local/bin/anki_leak_probe.sh`; `getDeckInfo` Δ
  must drop to the ±15 noise band.
- [ ] **Monitor ~1 week** — `anon` slope stays flat (no ~15 MB/hr climb), no
  BetterStack incidents, hang watcher quiet.
- [ ] **Then remove stopgaps** — `rm /etc/systemd/system/anki.service.d/mem.conf`;
  drop the daily-restart cron; `systemctl daemon-reload && systemctl restart anki.service`.
- [ ] (Optional, headroom) resize droplet to ≥ 2 GB; decouple **staging** from
  prod AnkiConnect; lock down SSH (constant root brute-force in journal).

## Instrumentation deployed (on the Anki droplet)

- **System-wide hang watcher** — `/usr/local/bin/anki_hang_watch.sh`, systemd
  `anki-hang-watch.service` (runs as root). On sustained ≥85% **total** CPU it
  logs `free` + `top` + hottest-process cmdline/kstack + `py-spy --native` to
  `/home/ankiuser/anki_hang_watch.log`. Functional-tested (caught a `yes`
  spinner). Source mirrored in repo: [anki_hang_watch.sh](anki_hang_watch.sh).
  - v1 watched only the Anki process and stayed silent during outages → that's
    how we learned **Anki is the victim (starved), not the CPU hog**.
- **Memory logger** — `/usr/local/bin/anki_mem_log.sh`, cron `* * * * *`. Logs
  `anon`, `memory.current`, and top-3 cgroup processes by RSS to
  `/home/ankiuser/anki_mem.log`.
- **Hardened backup** in repo: [anki_backup.sh](anki_backup.sh) (no gzip on
  media, `nice`/`ionice`, throttled rclone, atomic sqlite snapshot, flock).
  NOT yet deployed to the droplet (old backup still cron'd; it's harmless/fast).

## Continue here / what to check next

1. **Verify the fix** (minutes) — re-run the probe; `getDeckInfo` Δ should now be
   ~noise (was +231):
   ```bash
   /usr/local/bin/anki_leak_probe.sh
   ```
   Still elevated → residual cycle in the per-child path (`confForDid`/`get`);
   hunt it the same way (the leak is always a per-request ref cycle under
   `gc.disable()`).
2. **Confirm the deployed addon has the fix:**
   ```bash
   NM=$(find /home/ankiuser/.local/share/Anki2/addons21 -name note_manager.py)
   grep -c "stack = \[tree\]"  "$NM"   # expect 1 (iterative walk present)
   grep -c "def _index(node)"  "$NM"   # expect 0 (real closure gone; a bare
                                       # "def _index" match is just the comment)
   ```
3. **Monitor the anon slope ~1 week** (was climbing ~15 MB/hr during active hours):
   ```bash
   awk 'NR%30==1' /home/ankiuser/anki_mem.log | tail -30
   ```
   Flat day-over-day = fixed → then remove the stopgaps (see Fix checklist).
4. **If an episode still fires**, the system-wide hang watcher captured it:
   ```bash
   sed -n '/=== HANG/,/--- end ---/p' /home/ankiuser/anki_hang_watch.log | tail -80
   ```

## Diagnostic tooling (on the droplet)

- `/usr/local/bin/anki_leak_probe.sh` — per-endpoint anon-delta bisect harness.
- `/usr/local/bin/anki_mem_log.sh` (cron) — anon + per-process RSS → `anki_mem.log`.
- `/usr/local/bin/anki_hang_watch.sh` (`anki-hang-watch.service`) — system-wide
  CPU pin → `free`/`top`/py-spy → `anki_hang_watch.log`.

## Quick reference

- Droplet shell: `root@anki-desktop-gui` (UTC). API shell: `studyplan@studyplan`.
- Anki PID now: `ss -lptnH 'sport = :8765' | grep -oE 'pid=[0-9]+'`.
- Anki memory now: `cat /sys/fs/cgroup/system.slice/anki.service/memory.current`;
  anon: `awk '/^anon /{print $2}' /sys/fs/cgroup/system.slice/anki.service/memory.stat`.
- OOM history: `journalctl -k | grep -iE 'killed process|out of memory'`.
- API error histogram (UTC, incl. gz):
  `{ grep -h '\[Anki API\]' "$LOGDIR"/error.*.log; zcat "$LOGDIR"/error.*.log.gz; } | grep -oE '"timestamp":"[0-9-]+T[0-9]{2}' | sort | uniq -c`
