import argparse
from . import __version__
from . import interactive


def create_parser():
    parser = argparse.ArgumentParser(
        prog='song-dl',
        description='Download songs with rich metadata tagging (interactive)',
    )
    parser.add_argument(
        '--version', action='version',
        version=f'song-dl v{__version__}'
    )
    parser.add_argument(
        '--update', action='store_true',
        help='Check for updates and install the latest version'
    )
    parser.add_argument(
        '--check-update', action='store_true',
        help='Check if a newer version is available'
    )
    return parser


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

    interactive.run()
