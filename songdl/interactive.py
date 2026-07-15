import atexit
import os
import sys
from . import __version__
from . import config as pconf
from . import history as hist
from . import core as c
from . import downloader as dl
from .tui import (
    C,
    W,
    _c,
    _pr,
    _title,
    _raw_input,
    _ask,
    _yn,
    _getch,
    _menu,
    _wait,
    _pick,
    _set_debug,
    _debug,
)

SOURCES = [
    ("YouTube", "ytsearch"),
    ("SoundCloud", "scsearch"),
]


def _feed(url, queue=None):
    # Detect YouTube radio mixes - these are extremely slow to extract
    import re as _re

    if _re.search(r"[?&]list=RD", url) or _re.search(r"[?&]start_radio=", url):
        print(f"  {C['y']}:: Radio mix detected, downloading single video{C['r']}")
        print(f"  {C['d']}  (use a regular playlist URL for full tracklist){C['r']}")
        # Strip playlist params so yt-dlp doesn't re-fetch them later
        url = _re.sub(r"[?&]list=RD[^&]*", "", url)
        url = _re.sub(r"[?&]start_radio=[^&]*", "", url)
        return None  # caller will treat as single video

    try:
        print(f"  {C['y']}:: Fetching info...{C['r']}", end="", flush=True)
        info = dl.get_playlist_info(url)
        print()
        if info.get("_type") == "playlist" and "entries" in info:
            entries = [e for e in info["entries"] if e is not None]
            _pr("ok", f"Found {len(entries)} track(s) in playlist.")
            return entries
        return None
    except KeyboardInterrupt:
        print()
        _pr("w", "Cancelled by user.")
        return None
    except Exception as exc:
        print()
        _pr("e", str(exc))
        return None


def _q_add(items, source="", queue=None):
    if queue is None:
        queue = []
    added = 0
    for item in items:
        url = item.get("webpage_url") or item.get("url") or ""
        if not url:
            id_ = item.get("id") or item.get("display_id") or ""
            if id_:
                url = f"https://www.youtube.com/watch?v={id_}"
            else:
                continue
        title = item.get("title", "Unknown") or "Unknown"
        queue.append({"url": url, "title": title, "source": source})
        added += 1
    if added:
        _pr("ok", f"{added} item(s) added to queue.")


def _q_process(cfg, queue):
    if not queue:
        _pr("w", "Queue is empty.")
        return

    total = len(queue)
    import time

    t0 = time.time()
    print(f"\n  {C['h']}╔{'═' * (W - 2)}╗{C['r']}")
    print(
        f"  {C['h']}║{C['r']}{_c(f'Processing queue ({total} items)')}{C['h']}║{C['r']}"
    )
    print(f"  {C['h']}╚{'═' * (W - 2)}╝{C['r']}")
    print()

    items = list(queue)
    queue.clear()

    succeeded = 0
    failed = 0

    if total == 1:
        # Sequential for single item
        entry = items[0]
        print(f"  {C['h']}[1/1]{C['r']}  {entry['title'][:50]}")
        ok = c.process_input(entry["url"], cfg, batch=False)
        succeeded = 1 if ok else 0
        failed = 0 if ok else 1
        print()
    else:
        # Parallel for batch — 3 concurrent workers
        import threading, concurrent.futures

        print_lock = threading.Lock()

        def _worker(i, entry):
            nonlocal succeeded, failed
            url = entry["url"]
            with print_lock:
                print(f"  {C['h']}[{i + 1}/{total}]{C['r']}  {entry['title'][:50]}")
            ok = c.process_input(url, cfg, batch=True)
            with print_lock:
                if ok:
                    succeeded += 1
                else:
                    failed += 1
            with print_lock:
                print()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_worker, i, entry) for i, entry in enumerate(items)]
            concurrent.futures.wait(futures)

    elapsed = time.time() - t0
    elapsed_str = (
        f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        if elapsed >= 60
        else f"{elapsed:.0f}s"
    )

    if total == 1:
        status = "succeeded" if succeeded else "failed"
        _pr("ok", f"Queue complete: {status} ({elapsed_str})")
    elif failed == 0:
        _pr("ok", f"Queue complete: {succeeded} succeeded ({elapsed_str})")
    elif succeeded == 0:
        _pr("ok", f"Queue complete: all {failed} failed — check errors above")
    else:
        _pr(
            "ok",
            f"Queue complete: {succeeded} succeeded, {failed} failed ({elapsed_str})",
        )


def _q_remove(queue):
    if not queue:
        _pr("w", "Queue is empty.")
        return
    _title("Remove from queue")
    for i, entry in enumerate(queue, 1):
        print(f"  {C['h']}{i:3d}{C['r']}  {C['b']}{entry['title'][:55]}{C['r']}")
    print()
    ritems = [(str(i), entry["title"][:50]) for i, entry in enumerate(queue, 1)]
    picked = _menu(ritems, title="Select items to remove", multi=True)
    if not picked:
        return
    indices = sorted([int(s) for s in picked], reverse=True)
    removed = []
    for i in indices:
        if 1 <= i <= len(queue):
            removed.append(queue.pop(i - 1))
    if removed:
        _pr("ok", f"Removed {len(removed)} item(s).")
    else:
        _pr("w", "Nothing removed.")
    _wait()


# ─── Actions ──────────────────────────────────────────────────────


def _act_search(cfg, queue):
    sources = cfg.sources
    if not sources:
        _pr("w", "No sources enabled. Enable them in Settings.")
        return

    query = _ask("Enter search")
    if not query:
        return

    _pr("h", f"Searching {len(sources)} source(s)...")
    results = []
    seen_ids = set()
    for prefix in sources:
        name = next((n for n, p in SOURCES if p == prefix), prefix)
        try:
            info = dl.search_source(prefix, query, max_results=cfg.max_results)
            for e in info.get("entries", []):
                if e:
                    vid = e.get("id") or e.get("url", "")
                    if vid and vid in seen_ids:
                        continue
                    if vid:
                        seen_ids.add(vid)
                    e["_source"] = name
                    results.append(e)
        except Exception as exc:
            _pr("e", f"{name}: {exc}")
            if "HTTP Error 404" in str(exc):
                _pr(
                    "d",
                    f"  Hint: {name} may be blocking requests. Try a different source.",
                )

    picked = _pick(results)
    if not picked:
        return
    _q_add(picked, source="search", queue=queue)
    r = _yn("Queue more", True)
    if r is None or not r:
        return
    _act_search(cfg, queue)


def _act_url(queue):
    import re as _re

    url = _ask("Enter URL (video or playlist)")
    if not url:
        return
    # Strip radio playlist params so yt-dlp doesn't hang on them later
    clean_url = _re.sub(r"[?&]list=RD[^&]*", "", url)
    clean_url = _re.sub(r"[?&]start_radio=[^&]*", "", clean_url)
    entries = _feed(url)
    if entries is not None:
        picked = _pick(entries, title="Playlist tracks")
        if not picked:
            return
        _q_add(picked, source="playlist", queue=queue)
    else:
        _q_add(
            [{"webpage_url": clean_url or url, "title": url[:60]}],
            source="url",
            queue=queue,
        )

    r = _yn("Queue more", True)
    if r is None or not r:
        return
    _act_url(queue)


def _act_batch(queue):
    path = _ask("Path to batch file")
    if not path:
        return
    if not os.path.exists(path):
        _pr("e", f"File not found: {path}")
        return
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    for line in lines:
        queue.append({"url": line, "title": line[:55], "source": "batch"})
    _pr("ok", f"Added {len(lines)} item(s) to queue.")


def _act_queue(cfg, queue):
    while True:
        if not queue:
            _pr("w", "Queue is empty.")
            return

        # Show queue items
        print()
        for i, entry in enumerate(queue, 1):
            print(f"  {C['h']}{i:2d}.{C['r']}  {C['b']}{entry['title'][:55]}{C['r']}")
        print()

        ch = _menu(
            [
                ("p", f"{C['ok']}Process all{C['r']}  {C['d']}(download){C['r']}"),
                ("r", f"{C['w']}Remove items{C['r']}"),
                ("c", f"{C['e']}Clear queue{C['r']}"),
                ("b", "Back"),
            ],
            title=f"Queue ({len(queue)} items)",
        )

        if ch is None or ch == "b":
            return
        if ch == "p":
            _q_process(cfg, queue)
            return
        elif ch == "r":
            _q_remove(queue)
        elif ch == "c":
            queue.clear()
            _pr("ok", "Queue cleared.")
            return


def _act_history():
    hist.show_history()


def _act_settings(cfg):
    _title("Settings (Enter = keep current)")

    # ── Audio Format ──
    _pr("d", f"  ── Audio Format {'─' * (W - 16)}")
    f = _ask("Format (mp3/m4a/flac/opus)", cfg.format)
    if f:
        cfg.format = f
    q = _ask("Quality (0=best or 192k)", cfg.quality)
    if q:
        cfg.quality = q

    # ── Paths ──
    _pr("d", f"  ── Paths {'─' * (W - 8)}")
    o = _ask("Output directory", cfg.output_dir)
    if o:
        cfg.output_dir = o

    # ── Search Sources ──
    _title("Search Sources (Space to toggle)")
    src_items = []
    initial_toggle = set()
    for i, (name, prefix) in enumerate(SOURCES):
        if prefix in cfg.sources:
            initial_toggle.add(i)
        src_items.append((prefix, name))

    toggled = _menu(src_items, multi=True, initial=initial_toggle)
    if toggled is not None:
        cfg.sources = toggled

    # ── Search ──
    _pr("d", f"  ── Search {'─' * (W - 9)}")
    mr = _ask("Max search results (1-20)", str(cfg.max_results))
    if mr and mr.isdigit() and 1 <= int(mr) <= 20:
        cfg.max_results = int(mr)

    # ── Metadata ──
    _pr("d", f"  ── Metadata {'─' * (W - 11)}")
    s = _ask("Skip existing? (y/n)", "y" if cfg.skip_existing else "n")
    if s and s.lower() in ("y", "yes"):
        cfg.skip_existing = True
    elif s and s.lower() in ("n", "no"):
        cfg.skip_existing = False
    nc = _ask("Skip cover art? (y/n)", "y" if cfg.no_cover else "n")
    if nc and nc.lower() in ("y", "yes"):
        cfg.no_cover = True
    elif nc and nc.lower() in ("n", "no"):
        cfg.no_cover = False
    nm = _ask("Skip metadata lookup? (y/n)", "y" if cfg.no_metadata else "n")
    if nm and nm.lower() in ("y", "yes"):
        cfg.no_metadata = True
    elif nm and nm.lower() in ("n", "no"):
        cfg.no_metadata = False

    # ── File Naming ──
    _pr("d", f"  ── File Naming {'─' * (W - 15)}")
    _pr("h", "Output pattern — use {artist}, {album}, {title}, {track}")
    _pr("d", "  Examples: {artist} - {title}  or  {artist}/{album}/{title}")
    op = _ask("Output pattern", cfg.output_pattern)
    if op:
        cfg.output_pattern = op

    # ── Debug ──
    _pr("d", f"  ── Debug {'─' * (W - 10)}")
    d = _ask("Debug logging? (y/n)", "y" if cfg.debug else "n")
    if d and d.lower() in ("y", "yes"):
        cfg.debug = True
        _set_debug(True)
        _debug("Debug logging enabled")
        _pr("ok", f"Log: ~/.config/song-dl/debug.log")
    elif d and d.lower() in ("n", "no"):
        cfg.debug = False
        _set_debug(False)

    # ── Updates ──────────────────────────────────────
    _title("Updates")
    r = _yn("Check for updates?", True)
    if r is None:
        return
    if r:
        latest, has_update, error = c.check_for_update()
        if error:
            _pr("e", f"Could not check: {error}")
        elif has_update:
            _pr("ok", f"v{latest} available!")
            r = _yn(f"Update to v{latest}?", True)
            if r:
                c.run_update()
        else:
            _pr("ok", "You're on the latest version.")

    pconf.save(cfg)
    _pr("ok", "Settings saved.")


# ─── Main ─────────────────────────────────────────────────────────


def run():
    cfg = pconf.load()
    _set_debug(cfg.debug)
    queue = []

    # Save initial terminal state for emergency restoration
    _init_term = None
    try:
        if sys.stdin.isatty():
            import platform

            if platform.system() != "Windows":
                import termios

                _init_term = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    def _emergency_restore():
        if _init_term is not None:
            try:
                import termios

                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _init_term)
            except Exception:
                pass

    atexit.register(_emergency_restore)

    try:
        try:
            while True:
                print()
                _pr("h", f"╔{'═' * W}╗")
                print(
                    f"  {C['h']}║{C['r']}{_c(f'song-dl  v{__version__}')}{C['h']}║{C['r']}"
                )
                print(
                    f"  {C['h']}║{C['r']}{_c('Download songs + rich metadata')}{C['h']}║{C['r']}"
                )
                _pr("h", f"╚{'═' * W}╝")

                qs = f"Queue ({len(queue)})" if queue else "Queue (empty)"
                ch = _menu(
                    [
                        (
                            "1",
                            f"Search & Download   {C['d']}(YouTube, SoundCloud){C['r']}",
                        ),
                        (
                            "2",
                            f"Download URL        {C['d']}(video or playlist link){C['r']}",
                        ),
                        (
                            "3",
                            f"Batch download      {C['d']}(from a text file){C['r']}",
                        ),
                        ("4", qs),
                        (
                            "5",
                            f"Download history    {C['d']}(browse past downloads){C['r']}",
                        ),
                        (
                            "6",
                            f"Settings            {C['d']}(format, sources, patterns){C['r']}",
                        ),
                        ("7", f"Exit                {C['d']}(quit song-dl){C['r']}"),
                    ],
                    title="Menu",
                )

                if ch is None or ch == "7":
                    if queue and not _yn(
                        f"Exit with {len(queue)} item(s) in queue?", False
                    ):
                        continue
                    break

                actions = {
                    "1": lambda: _act_search(cfg, queue),
                    "2": lambda: _act_url(queue),
                    "3": lambda: _act_batch(queue),
                    "4": lambda: _act_queue(cfg, queue),
                    "5": _act_history,
                    "6": lambda: _act_settings(cfg),
                }
                a = actions.get(ch)
                if a:
                    _cancelled = False
                    try:
                        a()
                    except (Exception, KeyboardInterrupt) as exc:
                        if isinstance(exc, KeyboardInterrupt):
                            _pr("w", "Cancelled.")
                            _cancelled = True
                        else:
                            _pr("e", str(exc))
                            import traceback

                            traceback.print_exc()
                    if not _cancelled:
                        _wait()
        except KeyboardInterrupt:
            _pr("w", "\nExiting.")
    finally:
        _emergency_restore()
