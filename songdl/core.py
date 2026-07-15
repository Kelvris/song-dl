import os
import re
import time
from . import downloader as dl
from .tui import C, _debug, _strip_ansi, _raw_input
from . import metadata as meta
from . import tagger as tg
from . import history as hist


def _info(msg):
    print(f"{C['h']}::{C['r']} {msg}")


def _ok(msg):
    print(f"{C['ok']}ok{C['r']} {msg}")


def _warn(msg):
    print(f"{C['w']}!!{C['r']} {msg}")


def _err(msg):
    print(f"{C['e']}!!{C['r']} {msg}")


def _clean_ansi(text):
    """Strip ANSI escape codes (like \\x1b[b) from exception messages."""
    return _strip_ansi(text)


def strip_radio_params(url):
    """Remove YouTube radio mix params that make extraction slow."""
    url = re.sub(r"[?&]list=RD[^&]*", "", url)
    url = re.sub(r"[?&]start_radio=[^&]*", "", url)
    return url.rstrip("?&")


_URL_RE = re.compile(r"^https?://([\w-]+\.)+[\w-]+(:\d+)?(/[\w\-./?%&=@+#]*)?$")


def _is_url(text):
    return bool(_URL_RE.match(text))


def _sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def _sanitize_path(name):
    """Sanitize a path component (no / to avoid accidental subdirs)."""
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = name.replace("/", "_")
    name = name.strip()
    return name or "_"


def _apply_pattern(pattern, artist, album, title, track, ext):
    d = {
        "{artist}": _sanitize_path(artist or "Unknown"),
        "{album}": _sanitize_path(album or "Unknown Album"),
        "{title}": _sanitize_path(title or "Unknown"),
        "{track}": str(track) if track else "",
    }
    result = pattern
    for k, v in d.items():
        result = result.replace(k, v)
    result = re.sub(r"/+", "/", result)
    result = result.strip("/")
    return result + ext


def _input(prompt):
    """Safe input: delegates to tui._raw_input, returns None on interrupt."""
    val = _raw_input(prompt, default_on_interrupt=True)
    return val.strip() if val else val


def _format_size(bytes_):
    if bytes_ >= 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    if bytes_ >= 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_} B"


def process_input(url, args, batch=False):
    try:
        result = process_item(url, args, batch)
        # process_item returns None on success, or a string error on failure
        if result is not None:
            _err(f"Download failed: {result}")
            _debug(f"process_input: download failed for {url}: {result}")
            return False
        _debug(f"process_input: success for {url}")
        return True
    except KeyboardInterrupt:
        _warn("Cancelled by user")
        return False
    except Exception as e:
        _err(f"{url}: {e}")
        _debug(f"process_input: exception for {url}: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def process_item(url, args, batch=False):
    if not _is_url(url):
        _err(f"Not a URL: {url}")
        return f"Not a URL: {url}"  # [1.2] return error string, not None

    # Strip radio playlist params to avoid slow radio mix extraction
    url = strip_radio_params(url)

    _info("Fetching video info...")
    info_dict = dl.get_video_info(url)

    if "entries" in info_dict and info_dict.get("_type") == "playlist":
        entries = [
            e for e in info_dict["entries"] if e is not None and e.get("webpage_url")
        ]
        if not entries:
            _err("Empty playlist")
            return
        _info(f"Playlist: {len(entries)} items")
        for entry in entries:
            try:
                entry_url = entry.get("webpage_url") or entry.get("url") or ""
                if entry_url:
                    process_item(entry_url, args, batch=batch)
            except Exception as e:
                _err(f"  Skipped: {e}")
        return

    video_id = info_dict.get("id", "")
    yt_title = info_dict.get("title", "")
    yt_uploader = info_dict.get("uploader", "")
    yt_thumb = info_dict.get("thumbnail", "")
    yt_date = info_dict.get("upload_date", "")

    # Check skip_existing BEFORE expensive metadata lookup
    if args.skip_existing and video_id and hist.check_history(video_id):
        _warn(f"Already downloaded: {yt_title}")
        return

    clean = meta.clean_youtube_title(yt_title)

    def _yt_fallback():
        return {
            "title": yt_title,
            "artist": yt_uploader,
            "album": "",
            "year": yt_date[:4] if yt_date else "",
            "genre": "",
            "track": 0,
            "cover_url": yt_thumb,
            "lyrics": "",
        }

    metadata = {}
    if not args.no_metadata:
        _info("Looking up metadata (iTunes + MusicBrainz)...")
        merged, found = meta.lookup_all(clean, yt_uploader, yt_title, info_dict)

        if found:
            print(f"\n  {C['h']}┌─ Metadata {'─' * 27}┐{C['r']}")
            print(f"  │ {C['b']}Title:{C['r']}  {merged.get('title', '?'):<44}│")
            print(f"  │ {C['b']}Artist:{C['r']} {merged.get('artist', '?'):<44}│")
            print(f"  │ {C['b']}Album:{C['r']}  {merged.get('album', '?'):<44}│")
            print(f"  │ {C['b']}Year:{C['r']}   {merged.get('year', '?'):<44}│")
            print(f"  │ {C['b']}Genre:{C['r']}  {merged.get('genre', '?'):<44}│")
            ly = f"{'Found' if merged.get('lyrics') else 'None':<44}"
            print(f"  │ {C['b']}Lyrics:{C['r']} {ly}│")
            print(f"  {C['h']}└{'─' * 51}┘{C['r']}")
            print()

            r = "y" if batch else None
            if not batch:
                r = _input(f"  {C['h']}?{C['r']} Use this? {C['b']}Y{C['r']}/n/e: ")
            if r is None:
                return
            r = r.lower()
            if r in ("e", "edit"):
                print(f"  {C['h']}── Edit fields (Enter = keep) ──{C['r']}")
                merged["title"] = (
                    _input(f"  {C['b']}Title{C['r']}  [{merged['title']}]: ")
                    or merged["title"]
                )
                merged["artist"] = (
                    _input(f"  {C['b']}Artist{C['r']} [{merged['artist']}]: ")
                    or merged["artist"]
                )
                merged["album"] = (
                    _input(f"  {C['b']}Album{C['r']}  [{merged['album']}]: ")
                    or merged["album"]
                )
                merged["year"] = (
                    _input(f"  {C['b']}Year{C['r']}   [{merged['year']}]: ")
                    or merged["year"]
                )
                merged["genre"] = (
                    _input(f"  {C['b']}Genre{C['r']}  [{merged['genre']}]: ")
                    or merged["genre"]
                )
                print(f"  {C['h']}── Done ──{C['r']}")
            elif r in ("n", "no"):
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
            url, args.output_dir, args.format, args.quality, info_dict=info_dict
        )
    except Exception as e:
        raw = str(e)
        msg = (
            _clean_ansi(raw).strip("'\"") or type(e).__name__ or "Unknown yt-dlp error"
        )
        _debug(f"process_item error: {msg}  raw={raw!r}")
        _warn("Check your connection or try again later.")
        return msg

    if not os.path.exists(temp_file):
        _debug(f"process_item: temp file not found: {temp_file}")
        return "no output file produced"

    cover_data = None
    if not args.no_cover and metadata.get("cover_url"):
        _info("Downloading cover art...")
        cover_data = meta.download_image(metadata["cover_url"])

    try:
        _info("Tagging...")
        tg.tag_file(temp_file, metadata, cover_data)

        _, actual_ext = os.path.splitext(temp_file)
        pattern = getattr(args, "output_pattern", "{artist} - {title}")
        final_name = _apply_pattern(
            pattern,
            metadata.get("artist", "Unknown"),
            metadata.get("album", ""),
            metadata.get("title", "Unknown"),
            metadata.get("track", 0),
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
            video_id,
            url,
            metadata.get("title", "?"),
            metadata.get("artist", ""),
            metadata.get("album", ""),
            final_path,
            actual_ext.lstrip(".") if actual_ext else args.format,
        )

    _ok(
        f"Saved: {os.path.basename(final_path)}  ({_format_size(size)}, {elapsed:.1f}s)"
    )


def check_for_update():
    """Check GitHub for a newer version. Returns (latest_version, has_update, error)."""
    import urllib.request

    from . import __version__

    try:
        url = (
            "https://raw.githubusercontent.com/Kelvris/song-dl/main/songdl/__init__.py"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "song-dl/update-check"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")

        match = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', content)
        if not match:
            return (None, False, "Could not parse version from GitHub")

        latest = match.group(1)
        current = __version__

        def _ver_tuple(v):
            """Parse version string into sortable tuple, ignoring non-numeric suffixes."""
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

        has_update = _ver_tuple(latest) > _ver_tuple(current)
        return (latest, has_update, None)
    except Exception as e:
        return (None, False, str(e))


def run_update():
    """Download latest source files and replace in-place (no full reinstall)."""
    import tempfile
    import shutil
    import urllib.request
    import tarfile

    latest, has_update, error = check_for_update()
    if error:
        _err(f"Could not check for updates: {error}")
        return False
    if not has_update:
        _ok(f"You're already on the latest version (v{latest}).")
        return True

    SONGDL_DATA_DIR = os.path.join(
        os.path.expanduser("~"), ".local", "share", "song-dl"
    )
    if not os.path.isdir(SONGDL_DATA_DIR):
        _err(f"Installation not found at {SONGDL_DATA_DIR}.")
        _err("Run the full installer first: `bash <(curl -fsSL ...)`")
        return False

    tarball_url = (
        f"https://github.com/Kelvris/song-dl/archive/refs/tags/v{latest}.tar.gz"
    )

    _info(f"Downloading v{latest} ...")

    tmp_path = None
    extract_dir = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
            req = urllib.request.Request(
                tarball_url, headers={"User-Agent": "song-dl/update"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                tmp.write(resp.read())

        extract_dir = tempfile.mkdtemp()
        with tarfile.open(tmp_path, "r:gz") as tar:
            # ponytail: tarfile path traversal — 'data' filter is Python 3.12+
            # fallback to manual check for older Python
            try:
                tar.extractall(extract_dir, filter="data")
            except TypeError:
                for member in tar.getmembers():
                    member_path = os.path.realpath(
                        os.path.join(extract_dir, member.name)
                    )
                    if not member_path.startswith(os.path.realpath(extract_dir)):
                        raise Exception(
                            f"Path traversal detected in tar: {member.name}"
                        )
                tar.extractall(extract_dir)
        os.unlink(tmp_path)
        tmp_path = None  # cleaned up

        src = os.path.join(extract_dir, f"song-dl-{latest}")

        _info("Replacing source files ...")

        # Atomic-ish swap: copy to .new/ first, then replace
        dst_songdl = os.path.join(SONGDL_DATA_DIR, "songdl")
        dst_tmp = dst_songdl + ".new"
        if os.path.isdir(dst_tmp):
            shutil.rmtree(dst_tmp)
        shutil.copytree(os.path.join(src, "songdl"), dst_tmp)
        shutil.copy2(os.path.join(src, "main.py"), SONGDL_DATA_DIR)
        shutil.copy2(os.path.join(src, "requirements.txt"), SONGDL_DATA_DIR)
        if os.path.isdir(dst_songdl):
            shutil.rmtree(dst_songdl)
        os.rename(dst_tmp, dst_songdl)

        _ok(f"Updated to v{latest}! Restart song-dl to use it.")
        return True

    except Exception as e:
        _err(f"Update failed: {_clean_ansi(str(e) or type(e).__name__)}")
        return False

    finally:
        for p in (tmp_path, extract_dir):
            if p is None:
                continue
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass
