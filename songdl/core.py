import os
import re
import sys
import time
import termios
from . import downloader as dl
from . import metadata as meta
from . import tagger as tg
from . import history as hist

GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def _info(msg):
    print(f"{BLUE}::{RESET} {msg}")


def _ok(msg):
    print(f"{GREEN}ok{RESET} {msg}")


def _warn(msg):
    print(f"{YELLOW}!!{RESET} {msg}")


def _err(msg):
    print(f"{RED}!!{RESET} {msg}")


_URL_RE = re.compile(
    r'^(https?://)?([\w-]+\.)+[\w-]+(:\d+)?(/[\w\-./?%&=@+#]*)?$'
)


def _is_url(text):
    return bool(_URL_RE.match(text))


def _sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def _sanitize_path(name):
    """Sanitize a path component (no / to avoid accidental subdirs)."""
    name = re.sub(r'[<>:"|?*]', '_', name)
    name = name.replace('/', '_')
    name = name.strip()
    return name or '_'


def _apply_pattern(pattern, artist, album, title, track, ext):
    d = {
        '{artist}': _sanitize_path(artist or 'Unknown'),
        '{album}': _sanitize_path(album or 'Unknown Album'),
        '{title}': _sanitize_path(title or 'Unknown'),
        '{track}': str(track) if track else '',
    }
    result = pattern
    for k, v in d.items():
        result = result.replace(k, v)
    result = re.sub(r'/+', '/', result)
    result = result.strip('/')
    return result + ext


def _input(prompt):
    if not sys.stdin.isatty():
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return None
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~termios.ECHOCTL
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _format_size(bytes_):
    if bytes_ >= 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    if bytes_ >= 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_} B"


def process_input(url, args, batch=False):
    try:
        process_item(url, args, batch)
    except KeyboardInterrupt:
        _warn("Cancelled by user")
    except Exception as e:
        _err(f"{url}: {e}")
        import traceback
        traceback.print_exc()


def process_item(url, args, batch=False):
    if not _is_url(url):
        _err(f"Not a URL: {url}")
        return

    # Strip radio playlist params to avoid slow radio mix extraction
    url = re.sub(r'[?&]list=RD[^&]*', '', url)
    url = re.sub(r'[?&]start_radio=[^&]*', '', url)
    url = url.rstrip('?&')

    _info("Fetching video info...")
    info_dict = dl.get_video_info(url)

    if 'entries' in info_dict and info_dict.get('_type') == 'playlist':
        entries = [e for e in info_dict['entries'] if e is not None and e.get('webpage_url')]
        if not entries:
            _err("Empty playlist")
            return
        _info(f"Playlist: {len(entries)} items")
        for entry in entries:
            try:
                process_item(entry['webpage_url'], args, batch=batch)
            except Exception as e:
                _err(f"  Skipped: {e}")
        return

    video_id = info_dict.get('id', '')
    yt_title = info_dict.get('title', '')
    yt_uploader = info_dict.get('uploader', '')
    yt_thumb = info_dict.get('thumbnail', '')
    yt_date = info_dict.get('upload_date', '')

    # Check skip_existing BEFORE expensive metadata lookup
    if args.skip_existing and video_id and hist.check_history(video_id):
        _warn(f"Already downloaded: {yt_title}")
        return

    clean = meta.clean_youtube_title(yt_title)

    def _yt_fallback():
        return {
            'title': yt_title, 'artist': yt_uploader, 'album': '',
            'year': yt_date[:4] if yt_date else '',
            'genre': '', 'track': 0, 'cover_url': yt_thumb, 'lyrics': '',
        }

    metadata = {}
    if not args.no_metadata:
        _info("Looking up metadata (iTunes + MusicBrainz)...")
        merged, found = meta.lookup_all(clean, yt_uploader, yt_title, info_dict)

        if found:
            print(f"\n  {CYAN}┌─ Metadata {'─' * 27}┐{RESET}")
            print(f"  │ {BOLD}Title:{RESET}  {merged.get('title', '?'):<44}│")
            print(f"  │ {BOLD}Artist:{RESET} {merged.get('artist', '?'):<44}│")
            print(f"  │ {BOLD}Album:{RESET}  {merged.get('album', '?'):<44}│")
            print(f"  │ {BOLD}Year:{RESET}   {merged.get('year', '?'):<44}│")
            print(f"  │ {BOLD}Genre:{RESET}  {merged.get('genre', '?'):<44}│")
            ly = f"{'Found' if merged.get('lyrics') else 'None':<44}"
            print(f"  │ {BOLD}Lyrics:{RESET} {ly}│")
            print(f"  {CYAN}└{'─' * 51}┘{RESET}")
            print()

            r = 'y' if batch else None
            if not batch:
                r = _input(f"  {CYAN}?{RESET} Use this? {BOLD}Y{RESET}/n/e: ")
            if r is None:
                return
            r = r.lower()
            if r in ('e', 'edit'):
                print(f"  {CYAN}── Edit fields (Enter = keep) ──{RESET}")
                merged['title'] = _input(f"  {BOLD}Title{RESET}  [{merged['title']}]: ") or merged['title']
                merged['artist'] = _input(f"  {BOLD}Artist{RESET} [{merged['artist']}]: ") or merged['artist']
                merged['album'] = _input(f"  {BOLD}Album{RESET}  [{merged['album']}]: ") or merged['album']
                merged['year'] = _input(f"  {BOLD}Year{RESET}   [{merged['year']}]: ") or merged['year']
                merged['genre'] = _input(f"  {BOLD}Genre{RESET}  [{merged['genre']}]: ") or merged['genre']
                print(f"  {CYAN}── Done ──{RESET}")
            elif r in ('n', 'no'):
                merged = _yt_fallback()

            metadata = merged
        else:
            _warn("No metadata found, using YouTube info")
            metadata = _yt_fallback()
    else:
        metadata = _yt_fallback()

    _info("Downloading...")
    t0 = time.time()
    try:
        temp_file, _ = dl.download_audio(
            url, args.output_dir, args.format, args.quality
        )
    except Exception as e:
        _err(f"Download failed: {e}")
        return

    if not os.path.exists(temp_file):
        _err("Download failed: no output file produced")
        return

    cover_data = None
    if not args.no_cover and metadata.get('cover_url'):
        _info("Downloading cover art...")
        cover_data = meta.download_image(metadata['cover_url'])

    try:
        _info("Tagging...")
        tg.tag_file(temp_file, metadata, cover_data)

        _, actual_ext = os.path.splitext(temp_file)
        pattern = getattr(args, 'output_pattern', '{artist} - {title}')
        final_name = _apply_pattern(
            pattern,
            metadata.get('artist', 'Unknown'),
            metadata.get('album', ''),
            metadata.get('title', 'Unknown'),
            metadata.get('track', 0),
            actual_ext,
        )
        final_path = os.path.join(args.output_dir, final_name)
        final_dir = os.path.dirname(final_path)
        if final_dir:
            os.makedirs(final_dir, exist_ok=True)

        if temp_file != final_path:
            base, ext = os.path.splitext(final_path)
            counter = 1
            while os.path.exists(final_path):
                final_path = f"{base}-{counter}{ext}"
                counter += 1
            os.rename(temp_file, final_path)
    except Exception:
        dl.cleanup_temps(args.output_dir, video_id)
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise

    elapsed = time.time() - t0
    size = os.path.getsize(final_path) if os.path.exists(final_path) else 0

    if video_id:
        hist.record_history(
            video_id, url,
            metadata.get('title', '?'), metadata.get('artist', ''),
            metadata.get('album', ''), final_path,
            actual_ext.lstrip('.') if actual_ext else args.format,
        )

    _ok(f"Saved: {os.path.basename(final_path)}  ({_format_size(size)}, {elapsed:.1f}s)")


def check_for_update():
    """Check GitHub for a newer version. Returns (latest_version, has_update, error)."""
    import urllib.request
    
    from . import __version__

    try:
        url = "https://raw.githubusercontent.com/Kelvris/song-dl/main/songdl/__init__.py"
        req = urllib.request.Request(url, headers={'User-Agent': 'song-dl/update-check'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8')

        match = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', content)
        if not match:
            return (None, False, "Could not parse version from GitHub")

        latest = match.group(1)
        current = __version__

        def _ver_tuple(v):
            return tuple(int(x) for x in v.split('.'))

        has_update = _ver_tuple(latest) > _ver_tuple(current)
        return (latest, has_update, None)
    except Exception as e:
        return (None, False, str(e))


def run_update():
    """Download and run the latest install script."""
    _info("Downloading and installing update...")
    ret = os.system(
        "curl -fsSL https://raw.githubusercontent.com/Kelvris/song-dl/main/install.sh | bash"
    )
    if ret == 0:
        _ok("Update complete! Please restart song-dl.")
        return True
    else:
        _err("Update failed. Check your internet connection and try again.")
        return False
