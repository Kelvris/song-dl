import atexit
import os
import sys
import termios
from . import __version__
from . import config as pconf
from . import history as hist
from . import core as c
from . import downloader as dl

CFG = pconf.load()

SOURCES = [
    ('YouTube',       'ytsearch'),
    ('SoundCloud',    'scsearch'),
]

C = {
    'h':  '\033[96m',  'p':  '\033[95m',
    'ok': '\033[92m',  'w':  '\033[93m',
    'e':  '\033[91m',  'd':  '\033[90m',
    'b':  '\033[1m',   'r':  '\033[0m',
    'y':  '\033[93m',
}

W = 40

QUEUE = []


def _c(text):
    pad = max(0, W - len(text))
    return ' ' * (pad // 2) + text + ' ' * (pad - pad // 2)


def _pr(cat, msg=''):
    print(f"  {C[cat]}{msg}{C['r']}")


def _title(text):
    print(f"\n  {C['h']}{'─' * W}{C['r']}")
    print(f"  {C['b']}{text}{C['r']}")
    print(f"  {C['h']}{'─' * W}{C['r']}")


def _raw_input(prompt):
    if not sys.stdin.isatty():
        return input(prompt)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~termios.ECHOCTL
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        raise  # re-raise after terminal restored in finally
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _ask(text, default=None):
    suf = f" [{default}]" if default else ""
    prompt = f"  {C['p']}?{C['r']} {text}{suf}: "
    try:
        val = _raw_input(prompt).strip()
        return val if val else (default or "")
    except (EOFError, KeyboardInterrupt):
        return None


def _yn(text, default=True):
    suf = "Y/n" if default else "y/N"
    r = _ask(f"{text} ({suf})")
    if r is None:
        return None
    if not r:
        return default
    return r.lower() in ("y", "yes")


def _getch():
    """Read a single keypress without waiting for Enter."""
    if not sys.stdin.isatty():
        ch = sys.stdin.read(1)
        return ch
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        ch = sys.stdin.read(1)
        if ch == '\x03':
            return 'CTRL_C'
        if ch == '\x1b':
            seq = sys.stdin.read(2)
            if seq == '[A':
                return 'UP'
            elif seq == '[B':
                return 'DOWN'
            elif seq == '[C':
                return 'RIGHT'
            elif seq == '[D':
                return 'LEFT'
            return None
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _menu(items, title=None, multi=False, initial=None):
    """Arrow-key navigable menu.

    items: list of (return_value, display_text) tuples
    title: optional header
    multi: allow Space-toggle multi-select
    initial: set of pre-toggled indices (for multi)

    Returns selected value (single) or list of values (multi), or None.
    """
    if not sys.stdin.isatty():
        # fallback for piped input
        if title:
            _title(title)
        for i, (v, t) in enumerate(items, 1):
            print(f"  [{i}]  {t}")
        print()
        choice = _ask("Choice", "1")
        if choice is None:
            return None if not multi else None
        # Support "all" keyword
        if choice.lower() == "all":
            all_vals = [v for v, _ in items]
            return all_vals if multi else all_vals[0]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return [items[idx][0]] if multi else items[idx][0]
        except ValueError:
            pass
        if multi:
            picked = []
            for p in choice.replace(",", " ").split():
                try:
                    i = int(p) - 1
                    if 0 <= i < len(items):
                        picked.append(items[i][0])
                except ValueError:
                    continue
            return picked if picked else None
        return None if not multi else None

    selected = 0
    toggled = set(initial) if initial else set()
    number_buf = ''

    def _height():
        h = (4 if title else 0) + len(items) + 1
        if not number_buf:
            h += 2  # footer: separator + hint
        return h

    def _draw():
        if title:
            print()
            _pr('h', f"{'─' * (W + 2)}")
            print(f"  {C['b']}{title}{C['r']}")
            _pr('h', f"{'─' * (W + 2)}")
        for i, (v, t) in enumerate(items):
            pre = " ▸" if i == selected else "   "
            if multi:
                mk = f"{C['ok']}✓{C['r']}" if i in toggled else " "
                print(f" {pre} {mk} {t}")
            else:
                print(f" {pre} {C['h']}{t}{C['r']}")
        if number_buf:
            print(f"  {C['d']}Go to: {number_buf}{C['r']}")
        else:
            print(f"  {C['d']}{'─' * (W + 2)}{C['r']}")
            hint = "  ↑↓ Navigate  •  Enter Select  •  Space Toggle  •  Q Quit" if multi else "  ↑↓ Navigate  •  Enter Select  •  Q Quit"
            print(f"  {C['d']}{hint}{C['r']}")
        print()

    _draw()
    n = _height()

    while True:
        try:
            key = _getch()
            if key is None:
                continue
            if key == 'CTRL_C':
                return None if not multi else None
            if key == 'UP':
                selected = (selected - 1) % len(items)
                number_buf = ''
            elif key == 'DOWN':
                selected = (selected + 1) % len(items)
                number_buf = ''
            elif key in ('\n', '\r'):
                if number_buf:
                    try:
                        idx = int(number_buf) - 1
                        if 0 <= idx < len(items):
                            if multi:
                                if idx in toggled:
                                    toggled.remove(idx)
                                else:
                                    toggled.add(idx)
                                selected = idx
                            else:
                                return items[idx][0]
                    except ValueError:
                        pass
                    number_buf = ''
                else:
                    if multi:
                        return [items[i][0] for i in toggled] if toggled else [items[selected][0]]
                    return items[selected][0]
            elif key == ' ' and multi:
                number_buf = ''
                if selected in toggled:
                    toggled.remove(selected)
                else:
                    toggled.add(selected)
                selected = (selected + 1) % len(items)
            elif key == 'a' and multi:
                number_buf = ''
                if len(toggled) == len(items):
                    toggled.clear()
                else:
                    toggled = set(range(len(items)))
            elif key == 'q' or key == '\x1b':
                return None if not multi else None
            elif key == '\x7f':  # Backspace
                number_buf = number_buf[:-1]
            elif key in '0123456789':
                number_buf += key
                print(f"\033[{n}A\033[J", end='')
                _draw()
                continue
            else:
                number_buf = ''
                continue

            print(f"\033[{n}A\033[J", end='')
            _draw()
        except KeyboardInterrupt:
            return None if not multi else None


def _wait():
    if not sys.stdin.isatty():
        return
    try:
        _raw_input(f"\n  {C['d']}Press Enter to continue...{C['r']}")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(items, title="Results", show_source=True):
    if not items:
        _pr('w', "Nothing to show.")
        return []

    pick_items = []
    for r in items:
        dur = r.get("duration", 0)
        dur = int(dur) if dur else 0
        dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "?:??"
        t = (r.get("title", "?") or "?")[:50]
        u = (r.get("uploader", "?") or "?")[:24]
        src = r.get("_source", "")
        label = f"{C['b']}{t}{C['r']}  {C['d']}{u}  {dur_str}{C['r']}"
        if show_source and src:
            label = f"{C['d']}[{src}]{C['r']} {label}"
        pick_items.append((r, label))

    picked = _menu(pick_items, title=f"{title} ({len(items)})", multi=True)
    return picked or []


def _feed(url):
    # Detect YouTube radio mixes - these are extremely slow to extract
    import re as _re
    if _re.search(r'[?&]list=RD', url) or _re.search(r'[?&]start_radio=', url):
        print(f"  {C['y']}:: Radio mix detected, downloading single video{C['r']}")
        print(f"  {C['d']}  (use a regular playlist URL for full tracklist){C['r']}")
        # Strip playlist params so yt-dlp doesn't re-fetch them later
        url = _re.sub(r'[?&]list=RD[^&]*', '', url)
        url = _re.sub(r'[?&]start_radio=[^&]*', '', url)
        return None  # caller will treat as single video

    try:
        print(f"  {C['y']}:: Fetching info...{C['r']}", end='', flush=True)
        info = dl.get_playlist_info(url)
        print()
        if info.get('_type') == 'playlist' and 'entries' in info:
            entries = [e for e in info['entries'] if e is not None]
            _pr('ok', f"Found {len(entries)} track(s) in playlist.")
            return entries
        return None
    except KeyboardInterrupt:
        print()
        _pr('w', "Cancelled by user.")
        return None
    except Exception as exc:
        print()
        _pr('e', str(exc))
        return None


def _q_add(items, source=""):
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
        QUEUE.append({"url": url, "title": title, "source": source})
        added += 1
    if added:
        _pr('ok', f"{added} item(s) added to queue.")


def _q_process():
    if not QUEUE:
        _pr('w', "Queue is empty.")
        return

    total = len(QUEUE)
    import time
    t0 = time.time()
    print(f"\n  {C['h']}╔{'═' * (W - 2)}╗{C['r']}")
    print(f"  {C['h']}║{C['r']}{_c(f'Processing queue ({total} items)')}{C['h']}║{C['r']}")
    print(f"  {C['h']}╚{'═' * (W - 2)}╝{C['r']}")
    print()

    items = list(QUEUE)
    QUEUE.clear()

    if total == 1:
        # Sequential for single item
        entry = items[0]
        print(f"  {C['h']}[1/1]{C['r']}  {entry['title'][:50]}")
        try:
            c.process_input(entry["url"], CFG, batch=False)
        except Exception as exc:
            _pr('e', str(exc))
        print()
    else:
        # Parallel for batch — 3 concurrent workers
        import threading, concurrent.futures
        print_lock = threading.Lock()

        def _worker(i, entry):
            url = entry["url"]
            with print_lock:
                print(f"  {C['h']}[{i+1}/{total}]{C['r']}  {entry['title'][:50]}")
            try:
                c.process_input(url, CFG, batch=True)
            except Exception as exc:
                with print_lock:
                    _pr('e', str(exc))
            with print_lock:
                print()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_worker, i, entry) for i, entry in enumerate(items)]
            concurrent.futures.wait(futures)

    elapsed = time.time() - t0
    if elapsed >= 60:
        _pr('ok', f"Queue complete ({int(elapsed // 60)}m {int(elapsed % 60)}s)")
    else:
        _pr('ok', f"Queue complete ({elapsed:.0f}s)")


def _q_remove():
    if not QUEUE:
        _pr('w', "Queue is empty.")
        return
    _title("Remove from queue")
    for i, entry in enumerate(QUEUE, 1):
        print(f"  {C['h']}{i:3d}{C['r']}  {C['b']}{entry['title'][:55]}{C['r']}")
    print()
    ritems = [(str(i), entry['title'][:50]) for i, entry in enumerate(QUEUE, 1)]
    picked = _menu(ritems, title="Select items to remove", multi=True)
    if not picked:
        return
    indices = sorted([int(s) for s in picked], reverse=True)
    removed = []
    for i in indices:
        if 1 <= i <= len(QUEUE):
            removed.append(QUEUE.pop(i - 1))
    if removed:
        _pr('ok', f"Removed {len(removed)} item(s).")
    else:
        _pr('w', "Nothing removed.")
    _wait()


# ─── Actions ──────────────────────────────────────────────────────

def _act_search():
    sources = CFG.sources
    if not sources:
        _pr('w', "No sources enabled. Enable them in Settings.")
        return

    query = _ask("Enter search")
    if not query:
        return

    _pr('h', f"Searching {len(sources)} source(s)...")
    results = []
    for prefix in sources:
        name = next((n for n, p in SOURCES if p == prefix), prefix)
        try:
            info = dl.search_source(prefix, query)
            for e in info.get("entries", []):
                if e:
                    e["_source"] = name
                    results.append(e)
        except Exception as exc:
            _pr('e', f"{name}: {exc}")
            if 'HTTP Error 404' in str(exc):
                _pr('d', f"  Hint: {name} may be blocking requests. Try a different source.")

    picked = _pick(results)
    if not picked:
        return
    _q_add(picked, source="search")
    r = _yn("Queue more", True)
    if r is None or not r:
        return
    _act_search()


def _act_url():
    import re as _re
    url = _ask("Enter URL (video or playlist)")
    if not url:
        return
    # Strip radio playlist params so yt-dlp doesn't hang on them later
    clean_url = _re.sub(r'[?&]list=RD[^&]*', '', url)
    clean_url = _re.sub(r'[?&]start_radio=[^&]*', '', clean_url)
    entries = _feed(url)
    if entries is not None:
        picked = _pick(entries, title="Playlist tracks")
        if not picked:
            return
        _q_add(picked, source="playlist")
    else:
        _q_add([{"webpage_url": clean_url or url, "title": url[:60]}], source="url")

    r = _yn("Queue more", True)
    if r is None or not r:
        return
    _act_url()


def _act_batch():
    path = _ask("Path to batch file")
    if not path:
        return
    if not os.path.exists(path):
        _pr('e', f"File not found: {path}")
        return
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    for line in lines:
        QUEUE.append({"url": line, "title": line[:55], "source": "batch"})
    _pr('ok', f"Added {len(lines)} item(s) to queue.")


def _act_queue():
    while True:
        if not QUEUE:
            _pr('w', "Queue is empty.")
            return

        # Show queue items
        print()
        for i, entry in enumerate(QUEUE, 1):
            print(f"  {C['h']}{i:2d}.{C['r']}  {C['b']}{entry['title'][:55]}{C['r']}")
        print()

        ch = _menu([
            ("p", f"{C['ok']}Process all{C['r']}  {C['d']}(download){C['r']}"),
            ("r", f"{C['w']}Remove items{C['r']}"),
            ("c", f"{C['e']}Clear queue{C['r']}"),
            ("b", "Back"),
        ], title=f"Queue ({len(QUEUE)} items)")

        if ch is None or ch == "b":
            return
        if ch == "p":
            _q_process()
            return
        elif ch == "r":
            _q_remove()
        elif ch == "c":
            QUEUE.clear()
            _pr('ok', "Queue cleared.")
            return


def _act_history():
    hist.show_history()


def _act_settings():
    _title("Settings (Enter = keep current)")

    # ── Audio Format ──
    _pr('d', f"  ── Audio Format {'─' * (W - 16)}")
    f = _ask("Format (mp3/m4a/flac/opus)", CFG.format)
    if f: CFG.format = f
    q = _ask("Quality (0=best or 192k)", CFG.quality)
    if q: CFG.quality = q

    # ── Paths ──
    _pr('d', f"  ── Paths {'─' * (W - 8)}")
    o = _ask("Output directory", CFG.output_dir)
    if o: CFG.output_dir = o

    # ── Search Sources ──
    _title("Search Sources (Space to toggle)")
    src_items = []
    initial_toggle = set()
    for i, (name, prefix) in enumerate(SOURCES):
        if prefix in CFG.sources:
            initial_toggle.add(i)
        src_items.append((prefix, name))

    toggled = _menu(src_items, multi=True, initial=initial_toggle)
    if toggled is not None:
        CFG.sources = toggled

    # ── Metadata ──
    _pr('d', f"  ── Metadata {'─' * (W - 11)}")
    s = _ask("Skip existing? (y/n)", "y" if CFG.skip_existing else "n")
    if s and s.lower() in ("y", "yes"):
        CFG.skip_existing = True
    elif s and s.lower() in ("n", "no"):
        CFG.skip_existing = False
    nc = _ask("Skip cover art? (y/n)", "y" if CFG.no_cover else "n")
    if nc and nc.lower() in ("y", "yes"):
        CFG.no_cover = True
    elif nc and nc.lower() in ("n", "no"):
        CFG.no_cover = False
    nm = _ask("Skip metadata lookup? (y/n)", "y" if CFG.no_metadata else "n")
    if nm and nm.lower() in ("y", "yes"):
        CFG.no_metadata = True
    elif nm and nm.lower() in ("n", "no"):
        CFG.no_metadata = False

    # ── File Naming ──
    _pr('d', f"  ── File Naming {'─' * (W - 15)}")
    _pr('h', "Output pattern — use {artist}, {album}, {title}, {track}")
    _pr('d', "  Examples: {artist} - {title}  or  {artist}/{album}/{title}")
    op = _ask("Output pattern", CFG.output_pattern)
    if op: CFG.output_pattern = op

    # ── Updates ──────────────────────────────────────
    _title("Updates")
    r = _yn("Check for updates?", True)
    if r is None:
        return
    if r:
        latest, has_update, error = c.check_for_update()
        if error:
            _pr('e', f"Could not check: {error}")
        elif has_update:
            _pr('ok', f"v{latest} available!")
            r = _yn(f"Update to v{latest}?", True)
            if r:
                c.run_update()
        else:
            _pr('ok', "You're on the latest version.")

    pconf.save(CFG)
    _pr('ok', "Settings saved.")


# ─── Main ─────────────────────────────────────────────────────────

def run():
    # Save initial terminal state for emergency restoration
    _init_term = None
    try:
        if sys.stdin.isatty():
            _init_term = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    def _emergency_restore():
        if _init_term is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _init_term)
            except Exception:
                pass

    atexit.register(_emergency_restore)

    try:
        try:
            while True:
                print()
                _pr('h', f"╔{'═' * W}╗")
                print(f"  {C['h']}║{C['r']}{_c(f'song-dl  v{__version__}')}{C['h']}║{C['r']}")
                print(f"  {C['h']}║{C['r']}{_c('Download songs + rich metadata')}{C['h']}║{C['r']}")
                _pr('h', f"╚{'═' * W}╝")

                qs = f"Queue ({len(QUEUE)})" if QUEUE else "Queue (empty)"
                ch = _menu([
                    ("1", f"Search & Download   {C['d']}(YouTube, SoundCloud){C['r']}"),
                    ("2", f"Download URL        {C['d']}(video or playlist link){C['r']}"),
                    ("3", f"Batch download      {C['d']}(from a text file){C['r']}"),
                    ("4", qs),
                    ("5", f"Download history    {C['d']}(browse past downloads){C['r']}"),
                    ("6", f"Settings            {C['d']}(format, sources, patterns){C['r']}"),
                    ("7", f"Exit                {C['d']}(quit song-dl){C['r']}"),
                ], title="Menu")

                if ch is None or ch == "7":
                    if QUEUE and not _yn(f"Exit with {len(QUEUE)} item(s) in queue?", False):
                        continue
                    break

                actions = {
                    "1": _act_search, "2": _act_url, "3": _act_batch,
                    "4": _act_queue, "5": _act_history, "6": _act_settings,
                }
                a = actions.get(ch)
                if a:
                    _cancelled = False
                    try:
                        a()
                    except (Exception, KeyboardInterrupt) as exc:
                        if isinstance(exc, KeyboardInterrupt):
                            _pr('w', "Cancelled.")
                            _cancelled = True
                        else:
                            _pr('e', str(exc))
                            import traceback
                            traceback.print_exc()
                    if not _cancelled:
                        _wait()
        except KeyboardInterrupt:
            _pr('w', "\nExiting.")
    finally:
        _emergency_restore()
