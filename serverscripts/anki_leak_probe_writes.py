#!/usr/bin/env python3
"""
anki_leak_probe_writes.py - WRITE-endpoint memory-leak probe for AnkiConnect.

Companion to anki_leak_probe_all.py (read-only). Hammers every WRITE action
studyplan2021 uses, N times each, over one keep-alive connection, and reports
the cgroup `anon` delta per endpoint (worst first). Anki runs gc.disable()
(aqt/main.py), so any per-request reference cycle in a handler leaks forever -
this finds it by call frequency, the same way the read-only probe does.

ISOLATION (this is the whole safety story - read it):
  * Creates ONE dedicated deck  "<prefix>leakprobe_writes"  (+ ::Text / ::Audio)
    and ONE model "LeakProbeModel", operates ONLY on those, and DELETES them on
    exit (try/finally, even on Ctrl-C).
  * A hard guard (_assert_no_foreign_decks) walks every outgoing payload - incl.
    nested multi() actions - and REFUSES to send if any string names a
    staging_/production_/ge-english_/local_ deck that isn't the probe deck. So
    it is structurally incapable of mutating production, ge-english, or any real
    staging user's data.
  * The action allow-list (WRITE_ALLOWED + SETUP_READ) blocks anything else.

WHY WRITES NEED PAIRING:
  A write legitimately grows memory - a new note IS retained state, not a leak.
  So every endpoint runs in a STATE-NEUTRAL loop: paired with its inverse
  (addNote+deleteNote, answerCard+undoAnswerCard, flagCard+unflagCard,
  createDeck+deleteDeck, createModel+deleteModel) or applied in-place
  (updateNoteFields, updateModel, setDeckStudyOptions, extendNewCardLimit).
  Net stored data stays constant, so only a real per-request cycle climbs anon.

studyplan2021 write actions covered:
  createDeck, deleteDeck, createModel, updateModel, addNote, addAudioNote,
  updateNoteFields, deleteNote, answerCard, undoAnswerCard, flagCard, unflagCard,
  setDeckStudyOptions, extendNewCardLimit, enableStudyForgotten, multi
  (importPackage is opt-in via --package-url; it's a low-frequency endpoint.)

Run ON the droplet (reads the anki.service cgroup):
    python3 anki_leak_probe_writes.py --n 200          # smoke (validate coverage)
    python3 anki_leak_probe_writes.py                   # N=3000 (audio path skipped)
    python3 anki_leak_probe_writes.py --audio           # include audio (self-hosted mp3)
    python3 anki_leak_probe_writes.py --only answerCard,flagCard
    python3 anki_leak_probe_writes.py --package-url http://127.0.0.1:9/x.apkg

Interpreting output: clean endpoints sit in the noise band (|\u0394| < --threshold).
Anything well above is the leak - chase it as a per-request reference cycle
under gc.disable() (see INCIDENT.md).
"""

import argparse
import functools
import http.client
import http.server
import json
import os
import sys
import tempfile
import threading
import time

CGROUP_MEMSTAT = "/sys/fs/cgroup/system.slice/anki.service/memory.stat"

# Mutating actions this probe is allowed to send. Nothing else, ever.
WRITE_ALLOWED = {
    "createDeck", "deleteDeck", "createModel", "updateModel", "deleteModel",
    "addNote", "addAudioNote", "updateNoteFields", "deleteNote",
    "answerCard", "undoAnswerCard", "flagCard", "unflagCard",
    "setDeckStudyOptions", "extendNewCardLimit", "enableStudyForgotten",
    "importPackage", "multi",
}
# Read-only actions used only for setup/discovery (model ids, seed card ids).
# NB: findCards/findNotes are intentionally absent - on Anki 25.09 they return a
# protobuf RepeatedScalarContainer that crashes the addon's json.dumps
# server-side, leaving the request unanswered (looks like a client hang).
SETUP_READ = {
    "version", "modelNamesAndIds", "deckNamesAndIds", "notesInfo",
    "gcStats",  # read-mostly GC diagnostic; collect=True frees cycles, not user data
}
# Any string naming a studyplan deck must belong to the probe deck - full stop.
FOREIGN_DECK_PREFIXES = ("staging_", "production_", "ge-english_", "local_")


def read_anon():
    """Current cgroup anonymous RSS in bytes (the number that climbs on a leak)."""
    try:
        with open(CGROUP_MEMSTAT) as f:
            for line in f:
                if line.startswith("anon "):
                    return int(line.split()[1])
    except FileNotFoundError:
        return None
    return None


class Client:
    """Keep-alive HTTP connection to AnkiConnect with two hard safety gates:
    an action allow-list and a foreign-deck guard on every payload."""

    def __init__(self, host, port, probe_deck):
        self.host, self.port = host, port
        self.probe_deck = probe_deck
        self.conn = http.client.HTTPConnection(host, port, timeout=60)

    def _assert_no_foreign_decks(self, value):
        """Recursively reject any string that names a studyplan deck other than
        the probe deck (catches nested multi() actions too)."""
        if isinstance(value, str):
            # Block any bare deck name under a studyplan env prefix that isn't
            # the probe deck or one of its helpers (::Text/::Audio/::tmp,
            # <deck>_forgot). probe_deck is "<prefix>leakprobe_writes" - unique
            # enough that a prefix match can't collide with a real staging_<uuid>.
            if value.startswith(FOREIGN_DECK_PREFIXES) and not value.startswith(self.probe_deck):
                raise RuntimeError(
                    f"SAFETY ABORT: payload names non-probe deck {value!r}; "
                    f"this probe may only touch {self.probe_deck!r}.")
        elif isinstance(value, dict):
            for v in value.values():
                self._assert_no_foreign_decks(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                self._assert_no_foreign_decks(v)

    def call(self, action, params=None, version=6):
        if action not in WRITE_ALLOWED and action not in SETUP_READ:
            raise RuntimeError(f"refusing action not on allow-list: {action}")
        params = params or {}
        self._assert_no_foreign_decks(params)
        body = json.dumps({"action": action, "version": version, "params": params})
        for attempt in (1, 2):
            try:
                self.conn.request("POST", "/", body,
                                  {"Content-Type": "application/json"})
                data = self.conn.getresponse().read()
                try:
                    return json.loads(data)
                except ValueError:
                    return {"result": None, "error": "non-json response"}
            except (http.client.HTTPException, ConnectionError, OSError):
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = http.client.HTTPConnection(self.host, self.port,
                                                       timeout=60)
                if attempt == 2:
                    return {"result": None, "error": "connection failed"}


def result_of(reply):
    return reply.get("result") if isinstance(reply, dict) else reply


def error_of(reply):
    return reply.get("error") if isinstance(reply, dict) else None


def gc_snapshot(client, collect=False, top_types=0, saveall=False):
    """Fetch the server-side GC snapshot via the gcStats action. Returns the
    result dict (objects, garbage, enabled, and when collect=True: collected,
    objectsAfter; when top_types>0: topTypes; when saveall: garbageTypes - the
    true type histogram of the collected cycle objects) or None if the add-on
    predates gcStats."""
    res = result_of(client.call("gcStats", {"collect": collect,
                                            "topTypes": top_types,
                                            "saveall": saveall}))
    return res if isinstance(res, dict) else None


# --------------------------------------------------------------------------- #
# Self-hosted tiny audio file (so addAudioNote's download() path is exercised
# without hitting the real CDN 3000x). The bytes don't need to be a valid MP3 -
# the addon just writes them to the media folder.
# --------------------------------------------------------------------------- #
_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 2048


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence per-request stderr spam
        pass


def start_audio_server():
    d = tempfile.mkdtemp(prefix="leakprobe_audio_")
    with open(os.path.join(d, "probe.mp3"), "wb") as f:
        f.write(_MP3_BYTES)
    handler = functools.partial(_QuietHandler, directory=d)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/probe.mp3"


# --------------------------------------------------------------------------- #
# Setup / teardown of the isolated probe deck + model + seed notes.
# --------------------------------------------------------------------------- #
PROBE_MODEL = "LeakProbeModel"


def ensure_model(client):
    """Create LeakProbeModel (Front/Back/Audio1) or return existing id.
    Audio1 is required by addAudioNote."""
    reply = client.call("createModel", {
        "modelName": PROBE_MODEL,
        "fields": ["Front", "Back", "Audio1"],
        "templates": [{
            "name": "Card 1",
            "qfmt": "{{Front}}{{Audio1}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        }],
        "css": ".card{font-family:arial;font-size:20px;text-align:center;}",
    })
    mid = result_of(reply)
    if mid:
        return int(mid)
    # Already exists (or no id) - look it up.
    models = result_of(client.call("modelNamesAndIds")) or {}
    if PROBE_MODEL in models:
        return int(models[PROBE_MODEL])
    raise SystemExit(f"FATAL: could not create or find model {PROBE_MODEL!r}: "
                     f"{error_of(reply)}")


def setup(client, probe_deck, want_audio):
    text_deck = probe_deck + "::Text"
    audio_deck = probe_deck + "::Audio"
    for d in (probe_deck, text_deck, audio_deck):
        client.call("createDeck", {"deckName": d})

    print("setup: creating decks + model...", flush=True)
    model_id = ensure_model(client)

    # Seed a handful of notes in ::Text; we need their card ids for the
    # in-place probes (answerCard/flag/undo/updateNoteFields).
    print("setup: seeding notes...", flush=True)
    seeded_notes = []
    for i in range(5):
        nid = result_of(client.call("addNote", {"note": {
            "deckName": text_deck, "modelName": PROBE_MODEL,
            "fields": {"Front": f"seed-{i}", "Back": "seed", "Audio1": ""},
        }}))
        if nid:
            seeded_notes.append(int(nid))
    if not seeded_notes:
        raise SystemExit("FATAL: could not seed any probe notes - addNote failed.")

    # Get a card id from the seeded notes via notesInfo (its 'cards' is a plain
    # db.list() of ints). We deliberately do NOT use findCards/findNotes: on
    # Anki 25.09 they return a protobuf RepeatedScalarContainer that crashes the
    # addon's json.dumps server-side, so the request never gets a response.
    info = result_of(client.call("notesInfo", {"notes": seeded_notes})) or []
    seed_card = None
    if isinstance(info, list):
        for entry in info:
            cards = entry.get("cards") if isinstance(entry, dict) else None
            if cards:
                seed_card = int(cards[0])
                break
    if seed_card is None:
        raise SystemExit("FATAL: notesInfo returned no cards for seeded notes.")

    return {
        "text_deck": text_deck, "audio_deck": audio_deck, "model_id": model_id,
        "seed_note": seeded_notes[0], "seed_card": seed_card,
    }


def teardown(client, probe_deck, model_id):
    """Best-effort, idempotent cleanup. Each step wrapped so one failure
    doesn't strand the rest."""
    print("\n--- cleanup ---", flush=True)
    for d in (probe_deck + "_forgot", probe_deck + "::tmp", probe_deck):
        try:
            client.call("deleteDeck", {"deckName": d, "deleteCards": True})
        except Exception as e:
            print(f"  cleanup deleteDeck {d}: {e}", flush=True)
    # Delete probe models by NAME (model_id may be None if a run was interrupted
    # during setup; this also sweeps the createModel+deleteModel tmp model).
    try:
        models = result_of(client.call("modelNamesAndIds")) or {}
        for mname in ("LeakProbeModel", "LeakProbeTmpModel"):
            if mname in models:
                client.call("deleteModel", {"modelId": int(models[mname])})
    except Exception as e:
        print(f"  cleanup deleteModel: {e}", flush=True)
    print(f"  removed {probe_deck!r} (+subdecks) and {PROBE_MODEL!r}.", flush=True)
    print("  NOTE: audio tests leave tiny orphaned media files; sweep with "
          "Anki > Tools > Check Media > Delete Unused if desired.", flush=True)


# --------------------------------------------------------------------------- #
# Per-endpoint state-neutral steps. Each does ONE neutral iteration.
# --------------------------------------------------------------------------- #
def build_steps(client, ctx, probe_deck, audio_url, package_url):
    text_deck = ctx["text_deck"]
    audio_deck = ctx["audio_deck"]
    model_id = ctx["model_id"]
    seed_note = ctx["seed_note"]
    seed_card = ctx["seed_card"]
    counter = [0]

    def nxt():
        counter[0] += 1
        return counter[0]

    def add_delete():
        i = nxt()
        nid = result_of(client.call("addNote", {"note": {
            "deckName": text_deck, "modelName": PROBE_MODEL,
            "fields": {"Front": f"p-{i}", "Back": "b", "Audio1": ""}}}))
        if nid:
            client.call("deleteNote", {"noteId": int(nid), "deckName": probe_deck})

    def add_audio_delete():
        i = nxt()
        nid = result_of(client.call("addAudioNote", {
            "note": {"deckName": audio_deck, "modelName": PROBE_MODEL,
                     "fields": {"Front": f"a-{i}", "Back": "b"}},
            "audioFile": audio_url}))
        if nid:
            client.call("deleteNote", {"noteId": int(nid), "deckName": probe_deck})

    def update_fields():
        i = nxt()
        client.call("updateNoteFields", {"note": {
            "id": seed_note, "deckName": probe_deck,
            "fields": {"Front": f"u-{i}", "Back": "b"}}})

    def update_fields_audio():
        client.call("updateNoteFields", {"note": {
            "id": seed_note, "deckName": probe_deck,
            "audioFields": {"Audio1": audio_url}}})

    def answer_undo():
        client.call("answerCard",
                    {"cardId": seed_card, "ease": 3, "timeTakenSeconds": 1})
        client.call("undoAnswerCard", {"cardId": seed_card, "deckName": probe_deck})

    def flag_unflag():
        client.call("flagCard", {"cardId": seed_card})
        client.call("unflagCard", {"cardId": seed_card})

    def create_delete_deck():
        tmp = probe_deck + "::tmp"
        client.call("createDeck", {"deckName": tmp})
        client.call("deleteDeck", {"deckName": tmp, "deleteCards": True})

    def create_delete_model():
        mid = result_of(client.call("createModel", {
            "modelName": "LeakProbeTmpModel", "fields": ["F"],
            "templates": [{"name": "c", "qfmt": "{{F}}", "afmt": "{{F}}"}],
            "css": ""}))
        if mid:
            client.call("deleteModel", {"modelId": int(mid)})

    def update_model():
        i = nxt()
        client.call("updateModel",
                    {"modelId": int(model_id), "css": f"/* {i} */ .card{{}}"})

    def set_study_options():
        client.call("setDeckStudyOptions",
                    {"deckName": probe_deck, "newCardsPerDay": 20,
                     "reviewsPerDay": 200})

    def extend_limit():
        client.call("extendNewCardLimit",
                    {"deckName": probe_deck, "additionalCards": 5})

    def study_forgotten():
        # Filtered decks can't be nested (no "::"), so use a top-level name.
        client.call("enableStudyForgotten", {
            "deckName": probe_deck, "days": 1,
            "filteredDeckName": probe_deck + "_forgot"})

    def multi_pair():
        client.call("multi", {"actions": [
            {"action": "flagCard", "params": {"cardId": seed_card}},
            {"action": "unflagCard", "params": {"cardId": seed_card}}]})

    steps = [
        ("addNote+deleteNote",        "addNote",          add_delete),
        ("updateNoteFields",          "updateNoteFields", update_fields),
        ("answerCard+undoAnswer",     "answerCard",       answer_undo),
        ("flagCard+unflagCard",       "flagCard",         flag_unflag),
        ("createDeck+deleteDeck",     "createDeck",       create_delete_deck),
        ("createModel+deleteModel",   "createModel",      create_delete_model),
        ("updateModel (in place)",    "updateModel",      update_model),
        ("setDeckStudyOptions",       "setDeckStudyOptions", set_study_options),
        ("extendNewCardLimit",        "extendNewCardLimit",  extend_limit),
        ("enableStudyForgotten",      "enableStudyForgotten", study_forgotten),
        ("multi[flag+unflag]",        "multi",            multi_pair),
    ]
    if audio_url:
        steps.insert(1, ("addAudioNote+deleteNote", "addAudioNote", add_audio_delete))
        steps.insert(3, ("updateNoteFields+audio",  "updateNoteFields", update_fields_audio))
    if package_url:
        def import_pkg():
            client.call("importPackage",
                        {"packageUrl": package_url, "parentDeck": probe_deck,
                         "allowDuplicates": True})
        steps.append(("importPackage", "importPackage", import_pkg))
    return steps


def run_probe(client, label, step, n, settle, threshold, top_types=0):
    """Run one state-neutral step N times and measure the PER-CALL cycle leak.

    Anki keeps gc.disable() on, so any per-request reference cycle is never
    freed. We isolate and measure that directly:
      1. gcStats(collect=True): free cycles left by the previous endpoint and
         take a clean object-count baseline.
      2. run the step N times.
      3. gcStats(collect=True) again: 'collected' is how many cycle objects
         this endpoint created - exactly what leaks forever under gc.disable().
    The headline is collected/N (objects leaked per call); a clean endpoint
    sits at ~0. anon MB is kept as a noisy secondary cross-check only. Errors
    are captured (not fatal) so one bad call doesn't strand the run.
    """
    err = None
    try:
        step()  # warm-up + first error surface
    except Exception as e:
        err = str(e)

    base = gc_snapshot(client, collect=True)
    before_anon = read_anon()
    t0 = time.time()
    next_report = t0 + 0.5
    for i in range(1, n + 1):
        try:
            step()
        except Exception as e:
            if err is None:
                err = str(e)
        now = time.time()
        if now >= next_report:
            rate = i / (now - t0) if now > t0 else 0
            sys.stdout.write(f"\r  {label:30s} {i:>5}/{n}  {rate:5.0f}/s   ")
            sys.stdout.flush()
            next_report = now + 0.5
    time.sleep(settle)

    after = gc_snapshot(client, collect=True, top_types=top_types,
                        saveall=(top_types > 0))
    after_anon = read_anon()
    elapsed = time.time() - t0

    if base is None or after is None:
        print(f"\r  {label:30s} {n}/{n}  {elapsed:4.0f}s   "
              f"n/a (no gcStats - rebuild add-on)" + " " * 6, flush=True)
        return label, None, None, err

    leaked = int(after.get("collected", 0))   # cycle objects from this burst
    per_call = leaked / n if n else 0.0
    anon_mb = ((after_anon - before_anon) / (1024 * 1024)
               if (after_anon is not None and before_anon is not None) else None)
    tag = "  <-- LEAK" if per_call > threshold else ""
    anon_txt = f"  anon{anon_mb:+.0f}MB" if anon_mb is not None else ""
    errtag = f"  [err: {err}]" if err else ""
    print(f"\r  {label:30s} {n}/{n}  {elapsed:4.0f}s   {per_call:6.2f} obj/call "
          f"({leaked:+d}/{n}){anon_txt}{tag}{errtag}" + " " * 4, flush=True)
    if tag and after.get("garbageTypes"):
        top = ", ".join(f"{name}:{cnt}" for name, cnt in after["garbageTypes"][:12])
        print(f"      leaked-object types: {top}", flush=True)
    elif tag and top_types and after.get("topTypes"):
        top = ", ".join(f"{name}:{cnt}" for name, cnt in after["topTypes"][:8])
        print(f"      top types after burst (heap, not leak): {top}", flush=True)
    return label, per_call, leaked, err


def main():
    ap = argparse.ArgumentParser(description="AnkiConnect WRITE-endpoint leak probe (studyplan2021, staging-isolated)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--n", type=int, default=3000, help="iterations per endpoint")
    ap.add_argument("--env-prefix", default="staging_", help="probe deck is created under this prefix")
    ap.add_argument("--threshold", type=float, default=1.0, help="objects/call (gc cycle objects) over which an endpoint is flagged LEAK")
    ap.add_argument("--top-types", type=int, default=0, dest="top_types", help="if >0, print the top-N object types after the burst for flagged endpoints")
    ap.add_argument("--settle", type=float, default=0.5, help="seconds to wait after a burst before reading anon")
    ap.add_argument("--only", default=None, help="comma-separated action/label substrings to limit the run")
    ap.add_argument("--audio", action="store_true", help="include audio path (self-hosts a tiny mp3 on localhost)")
    ap.add_argument("--package-url", default=None, help="opt-in: URL to a small .apkg to probe importPackage")
    args = ap.parse_args()

    if not args.env_prefix.endswith("_"):
        sys.exit("FATAL: --env-prefix should end with '_' (e.g. staging_).")
    probe_deck = args.env_prefix + "leakprobe_writes"

    client = Client(args.host, args.port, probe_deck)
    ver = result_of(client.call("version"))
    if read_anon() is None:
        print(f"WARN: cannot read {CGROUP_MEMSTAT} - run this ON the droplet; "
              f"deltas will be blank.", file=sys.stderr)
    print(f"AnkiConnect apiVersion={ver}", flush=True)
    print(f"ISOLATED probe deck = {probe_deck!r}  (+::Text/::Audio), model = "
          f"{PROBE_MODEL!r}\nguard: refuses any payload naming a non-probe "
          f"staging_/production_/ge-english_/local_ deck.\n", flush=True)
    if gc_snapshot(client) is None:
        print("WARN: add-on has no gcStats action - rebuild/redeploy the updated "
              "AnkiConnect.py. Rows will read 'n/a (no gcStats)'.", file=sys.stderr)

    audio_url = start_audio_server() if args.audio else None
    if audio_url:
        print(f"audio: self-hosted {audio_url}", flush=True)

    model_id = None
    try:
        ctx = setup(client, probe_deck, args.audio)
        model_id = ctx["model_id"]
        print(f"seeded: note={ctx['seed_note']} card={ctx['seed_card']}  "
              f"N={args.n}/endpoint  threshold={args.threshold} obj/call\n"
              f"metric: objects leaked per call (gc cycle objects, collected "
              f"between endpoints); anon MB is a noisy cross-check only.\n",
              flush=True)

        steps = build_steps(client, ctx, probe_deck, audio_url, args.package_url)
        if args.only:
            want = [s.strip() for s in args.only.split(",")]
            steps = [s for s in steps if any(w in s[0] or w == s[1] for w in want)]

        results = []
        for label, _action, step in steps:
            results.append(run_probe(client, label, step, args.n, args.settle,
                                     args.threshold, args.top_types))
    finally:
        teardown(client, probe_deck, model_id)

    print("\n=== summary (worst first, objects leaked per call) ===", flush=True)
    for label, per_call, leaked, err in sorted(
            results, key=lambda r: (r[1] if r[1] is not None else float("-inf")),
            reverse=True):
        if per_call is None:
            print(f"  {label:30s}   n/a (no gcStats)")
            continue
        flag = "  LEAK" if per_call > args.threshold else ""
        print(f"  {label:30s} {per_call:6.2f} obj/call  ({leaked:+d}/{args.n}){flag}"
              f"{f'   [err: {err}]' if err else ''}")


if __name__ == "__main__":
    main()
