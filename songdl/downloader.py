import os
import re
import shutil
import subprocess
import sys
import threading
import yt_dlp
from .tui import _debug

_COOKIE_FILE = os.path.expanduser("~/.config/song-dl/cookies.txt")

_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
}


def _base_opts():
    opts = dict(_BASE_OPTS)
    # yt-dlp only enables Deno by default. Explicitly enable the first supported
    # runtime installed by song-dl so Node/Bun/QuickJS work as advertised too.
    for runtime in ("deno", "node", "bun", "quickjs"):
        path = shutil.which(runtime)
        if path:
            opts["js_runtimes"] = {runtime: {"path": path}}
            break
    if os.path.isfile(_COOKIE_FILE):
        opts["cookiefile"] = _COOKIE_FILE  # type: ignore[assignment]
    return opts


def _version_tuple(version):
    """Normalize stable, nightly tag, and PyPI dev-release versions."""
    version = str(version).removesuffix(".dev0")
    return tuple(int(part) for part in re.findall(r"\d+", version))


def ytdlp_update_available(current, latest):
    return _version_tuple(latest) > _version_tuple(current)


def check_ytdlp_update():
    """Check the recommended yt-dlp nightly channel for a newer build."""
    import json
    import urllib.request

    current = yt_dlp.version.__version__  # type: ignore[attr-defined]
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest",
            headers={"User-Agent": "song-dl/update-check"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        latest = data["tag_name"].lstrip("v")
        return current, latest, None
    except Exception as e:
        return current, None, str(e)


def update_ytdlp():
    """Upgrade yt-dlp and its recommended dependencies to nightly."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--pre",
        "yt-dlp[default]",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        return False, message or f"pip exited with status {result.returncode}"
    return True, None


def get_video_info(url):
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:  # type: ignore[arg-type]
        return ydl.extract_info(url, download=False)


def get_playlist_info(url, timeout=10):
    """Fast playlist extraction (flat format, with socket timeout)."""
    opts = {**_base_opts(), "extract_flat": "in_playlist", "socket_timeout": timeout}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        return ydl.extract_info(url, download=False)


def search_source(prefix, query, max_results=5):
    query = query.strip()[:200].replace("\x00", "")
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:  # type: ignore[arg-type]
        return ydl.extract_info(f"{prefix}{max_results}:{query}", download=False)


# ponytail: global lock for progress hook, per-thread locks if contention becomes an issue
_progress_lock = threading.Lock()


def _progress_hook(d):
    """yt-dlp progress hook — prints a single-line progress bar."""
    if d["status"] == "downloading":
        with _progress_lock:
            pct = d.get("_percent_str", "").strip()
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            parts = ["  Downloading..."]
            if pct:
                parts.append(pct)
            if speed:
                parts.append(speed)
            if eta:
                parts.append(f"ETA {eta}")
            print("  ".join(parts), flush=True)


def cleanup_temps(output_dir, video_id):
    """Remove any leftover temp/partial files for a given video_id."""
    if not video_id:
        return
    for ext in ("webm", "m4a", "mkv", "3gp", "part", "ytdl"):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def download_audio(url, output_dir, format="mp3", quality="0", info_dict=None):
    if info_dict is None:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:  # type: ignore[arg-type]
            info = ydl.extract_info(url, download=False)
    else:
        info = info_dict
    video_id = info.get("id", "")

    opts = {
        **_base_opts(),
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": format,
                "preferredquality": quality,
            }
        ],
        "progress_hooks": [_progress_hook],
    }

    _debug(f"download_audio: starting url={url} format={format} quality={quality}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
            ydl.download([url])
        print()  # clear progress line
        _debug(f"download_audio: yt-dlp download succeeded for {video_id}")
    except Exception as e:
        _debug(f"download_audio: yt-dlp failed for {video_id}: {type(e).__name__}: {e}")
        cleanup_temps(output_dir, video_id)
        raise

    # Find actual output file (yt-dlp may fall back to different extension)
    expected = os.path.join(output_dir, f"{video_id}.{format}")
    if os.path.exists(expected):
        return expected, info
    for ext in ("m4a", "opus", "flac", "mp3", "wav", "aac"):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            return f, info
    return expected, info
