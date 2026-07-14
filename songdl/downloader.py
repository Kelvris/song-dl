import os
import yt_dlp

# ponytail: yt-dlp 2026+ auto-detects JS runtimes and optimal player clients.
# Hardcoding extractor_args triggers YouTube bot detection. Keep it simple.
_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
}


def get_video_info(url):
    with yt_dlp.YoutubeDL(_BASE_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


def get_playlist_info(url, timeout=10):
    """Fast playlist extraction (flat format, with socket timeout)."""
    opts = {**_BASE_OPTS, "extract_flat": "in_playlist", "socket_timeout": timeout}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def search_source(prefix, query, max_results=5):
    query = query.strip()[:200].replace("\x00", "")
    with yt_dlp.YoutubeDL(_BASE_OPTS) as ydl:
        return ydl.extract_info(f"{prefix}{max_results}:{query}", download=False)


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


def download_audio(url, output_dir, format="mp3", quality="0"):
    with yt_dlp.YoutubeDL(_BASE_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info.get("id", "")

    opts = {
        **_BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": format,
                "preferredquality": quality,
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
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
