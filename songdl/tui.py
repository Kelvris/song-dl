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
    number_buf = ""

    def _draw():
        # ponytail: clear screen + home cursor — reliable on all terminals
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        if title:
            print()
            _pr("h", f"{'─' * (W + 2)}")
            print(f"  {C['b']}{title}{C['r']}")
            _pr("h", f"{'─' * (W + 2)}")
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
            hint = (
                "  ↑↓ Navigate  •  Enter Select  •  Space Toggle  •  Q Quit"
                if multi
                else "  ↑↓ Navigate  •  Enter Select  •  Q Quit"
            )
            print(f"  {C['d']}{hint}{C['r']}")
        print()

    _draw()

    while True:
        try:
            key = _getch()
            if key is None:
                continue
            if key == "CTRL_C":
                return None if not multi else None
            if key == "UP":
                selected = (selected - 1) % len(items)
                number_buf = ""
            elif key == "DOWN":
                selected = (selected + 1) % len(items)
                number_buf = ""
            elif key in ("\n", "\r"):
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
                    number_buf = ""
                else:
                    if multi:
                        return (
                            [items[i][0] for i in toggled]
                            if toggled
                            else [items[selected][0]]
                        )
                    return items[selected][0]
            elif key == " " and multi:
                number_buf = ""
                if selected in toggled:
                    toggled.remove(selected)
                else:
                    toggled.add(selected)
                selected = (selected + 1) % len(items)
            elif key == "a" and multi:
                number_buf = ""
                if len(toggled) == len(items):
                    toggled.clear()
                else:
                    toggled = set(range(len(items)))
            elif key == "q" or key == "\x1b":
                return None if not multi else None
            elif key == "\x7f":  # Backspace
                number_buf = number_buf[:-1]
            elif key in "0123456789":
                number_buf += key
                _draw()
                continue
            else:
                number_buf = ""
                continue

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
