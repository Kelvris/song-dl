"""TUI primitives — colors, input, menus, cross-platform key reading."""

import os
import sys


C = {
    "h": "\033[96m",
    "p": "\033[95m",
    "ok": "\033[92m",
    "w": "\033[93m",
    "e": "\033[91m",
    "d": "\033[90m",
    "b": "\033[1m",
    "r": "\033[0m",
    "y": "\033[93m",
}

W = 40


def _c(text):
    pad = max(0, W - len(text))
    return " " * (pad // 2) + text + " " * (pad - pad // 2)


def _pr(cat, msg=""):
    print(f"  {C[cat]}{msg}{C['r']}")


def _title(text):
    print(f"\n  {C['h']}{'─' * W}{C['r']}")
    print(f"  {C['b']}{text}{C['r']}")
    print(f"  {C['h']}{'─' * W}{C['r']}")


def _raw_input(prompt):
    """Safe input: ECHOCTL disabled on Unix, plain input on Windows/non-tty."""
    if not sys.stdin.isatty():
        return input(prompt)
    import platform

    if platform.system() == "Windows":
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            raise
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~termios.ECHOCTL
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        raise
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
    """Read a single keypress without waiting for Enter.

    Cross-platform: msvcrt on Windows, termios on Unix, fallback on non-tty.
    """
    if not sys.stdin.isatty():
        ch = sys.stdin.read(1)
        return ch
    import platform

    if platform.system() == "Windows":
        import msvcrt

        ch = msvcrt.getch()
        if ch == b"\x03":
            return "CTRL_C"
        if ch == b"\x1b":
            seq = msvcrt.getch()
            if seq == b"[":
                seq2 = msvcrt.getch()
                if seq2 == b"A":
                    return "UP"
                elif seq2 == b"B":
                    return "DOWN"
                elif seq2 == b"C":
                    return "RIGHT"
                elif seq2 == b"D":
                    return "LEFT"
            return None
        return ch.decode("utf-8", errors="replace")
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        ch = sys.stdin.read(1)
        if ch == "\x03":
            return "CTRL_C"
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "UP"
            elif seq == "[B":
                return "DOWN"
            elif seq == "[C":
                return "RIGHT"
            elif seq == "[D":
                return "LEFT"
            return None
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _menu(items, title=None, multi=False, initial=None):
    """Numbered-list menu.

    items: list of (return_value, display_text) tuples
    title: optional header
    multi: allow multi-select (space-separated numbers)

    Returns selected value (single) or list of values (multi), or None.
    """
    if title:
        _title(title)
    for i, (v, t) in enumerate(items, 1):
        print(f"  [{i}]  {t}")
    print()
    if multi:
        hint = f"  {C['d']}Space-separated numbers, 'all' or 'q'{C['r']}"
    else:
        hint = f"  {C['d']}Number (1-{len(items)}), 'q' to cancel{C['r']}"
    print(hint)
    print()

    while True:
        try:
            raw = _raw_input("  > ")
        except (EOFError, KeyboardInterrupt):
            return None if not multi else None
        if not raw or raw.lower() == "q":
            return None if not multi else None
        if multi and raw.lower() == "all":
            return [v for v, _ in items]
        if multi:
            picked = []
            for p in raw.replace(",", " ").split():
                try:
                    i = int(p) - 1
                    if 0 <= i < len(items):
                        picked.append(items[i][0])
                except ValueError:
                    continue
            if picked:
                return picked
        else:
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(items):
                    return items[idx][0]
            except ValueError:
                pass
        print(f"  {C['e']}Invalid choice{C['r']}")


def _wait():
    if not sys.stdin.isatty():
        return
    try:
        _raw_input(f"\n  {C['d']}Press Enter to continue...{C['r']}")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(items, title="Results", show_source=True):
    if not items:
        _pr("w", "Nothing to show.")
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
