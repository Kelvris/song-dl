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
    return parser


def main():
    create_parser().parse_args()
    interactive.run()
