import argparse
from . import __version__
from . import interactive


def create_parser():
    parser = argparse.ArgumentParser(
        prog="song-dl",
        description="Download songs with rich metadata tagging (interactive)",
    )
    parser.add_argument(
        "--version", action="version", version=f"song-dl v{__version__}"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Check for updates and install the latest version",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Check if a newer version is available",
    )
    return parser


def _check_ytdlp_update():
    """Check if yt-dlp is outdated and prompt user to update."""
    from .downloader import check_ytdlp_update

    current, latest, error = check_ytdlp_update()
    if error or not latest:
        return
    try:

        def _ver_tuple(v):
            parts = []
            for x in v.split("."):
                digit = ""
                for ch in x:
                    if ch.isdigit():
                        digit += ch
                    else:
                        break
                parts.append(int(digit) if digit else 0)
            return tuple(parts)

        cur_tuple = _ver_tuple(current)
        lat_tuple = _ver_tuple(latest)
    except (ValueError, AttributeError):
        return
    if lat_tuple <= cur_tuple:
        return
    print(f"\n  !! yt-dlp {current} is outdated (latest: {latest})")
    print(f"  !! Some downloads may fail without the latest version.")
    try:
        r = input("  ? Update now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if r in ("", "y", "yes"):
        import subprocess
        import sys

        print("  :: Updating yt-dlp...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True,
        )
        print("  ok yt-dlp updated. Restart song-dl to use the new version.")


def main():
    args = create_parser().parse_args()

    if args.update:
        from . import core

        core.run_update()
        return

    if args.check_update:
        from . import core

        latest, has_update, error = core.check_for_update()
        if error:
            print(f"!! Could not check for updates: {error}")
        elif has_update:
            print(f":: A new version is available: v{latest}")
            print(f":: Run 'song-dl --update' to upgrade.")
        else:
            print(f":: You're on the latest version (v{latest}).")
        return

    _check_ytdlp_update()
    interactive.run()
