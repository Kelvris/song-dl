import re
import json
import time
import threading
import urllib.request
import urllib.error
import urllib.parse

UA = 'song-dl/0.1.0 (Python)'
ITUNES_URL = 'https://itunes.apple.com/search'
MUSICBRAINZ_URL = 'https://musicbrainz.org/ws/2/recording'
LRCLIB_URL = 'https://lrclib.net/api'


# ─── Helpers ──────────────────────────────────────────────────────

def _fetch_json(url, headers=None, timeout=15):
    hdrs = {'User-Agent': UA}
    if headers:
        hdrs.update(headers)
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


# ─── Title cleaning ───────────────────────────────────────────────

_CLEAN_PATTERNS = [
    r'\s*\(Official\s+(Music\s+)?Video\)\s*',
    r'\s*\(Official\s+Audio\)\s*',
    r'\s*\(Audio\)\s*',
    r'\s*\(Lyrics?\)\s*',
    r'\s*\(Lyric\s+Video\)\s*',
    r'\s*\(Official\s+Lyric\s+Video\)\s*',
    r'\s*\([0-9]{4}\)\s*',
    r'\s*\|.*$',
    r'\s*HD\s*$', r'\s*HQ\s*$',
    r'\s*♫\s*',
    r'\s*[-–—]\s*Topic$',
]


def clean_youtube_title(title):
    result = title
    for p in _CLEAN_PATTERNS:
        result = re.sub(p, '', result, flags=re.IGNORECASE)
    return result.strip()


# ─── iTunes ───────────────────────────────────────────────────────

def search_itunes(clean_title, raw_artist, yt_title):
    queries = []
    if clean_title and raw_artist:
        queries.append(f"{clean_title} {raw_artist}")
    if clean_title:
        queries.append(clean_title)
    if yt_title and yt_title != clean_title:
        queries.append(yt_title)

    for q in queries:
        params = {'term': q, 'entity': 'song', 'limit': 5}
        url = f"{ITUNES_URL}?{urllib.parse.urlencode(params)}"
        data = _fetch_json(url)
        if data and data.get('resultCount', 0) > 0:
            return data['results']
    return []


def _itunes_to_meta(r):
    return {
        'title': r.get('trackName', ''),
        'artist': r.get('artistName', ''),
        'album': r.get('collectionName', ''),
        'year': (r.get('releaseDate') or '')[:4],
        'genre': r.get('primaryGenreName', ''),
        'track': r.get('trackNumber', 0),
        'cover_url': get_large_artwork(r.get('artworkUrl100', '')),
    }


# ─── MusicBrainz ──────────────────────────────────────────────────

_MB_LAST_CALL = 0.0
_MB_LOCK = threading.Lock()


def search_musicbrainz(clean_title, raw_artist):
    global _MB_LAST_CALL
    with _MB_LOCK:
        elapsed = time.time() - _MB_LAST_CALL
        if elapsed < 1.2:
            time.sleep(1.2 - elapsed)

        query_parts = []
        if clean_title:
            query_parts.append(f'"{clean_title}"')
        if raw_artist:
            query_parts.append(f'artist:"{raw_artist}"')
        query = ' AND '.join(query_parts)

        params = {'query': query, 'fmt': 'json', 'limit': 3}
        url = f"{MUSICBRAINZ_URL}?{urllib.parse.urlencode(params)}"
        _MB_LAST_CALL = time.time()

    data = _fetch_json(url)

    if data and data.get('recordings'):
        return data['recordings']
    return []


def _best_mb_recording(recordings, clean_title):
    best = None
    best_score = 0
    for r in recordings:
        score = r.get('score', 0)
        title = r.get('title', '')
        if title.lower() == clean_title.lower():
            score += 30
        if best is None or score > best_score:
            best = r
            best_score = score
    return best


def _mb_to_meta(recording):
    m = {}
    m['title'] = recording.get('title', '')

    ac = recording.get('artist-credit') or []
    if ac:
        m['artist'] = ac[0].get('name', '')

    releases = recording.get('releases') or []
    if releases:
        m['album'] = releases[0].get('title', '')
        date = releases[0].get('date', '')
        if date:
            m['year'] = date[:4]

    if recording.get('first-release-date'):
        m['year'] = recording['first-release-date'][:4]

    tags = recording.get('tags') or []
    if tags:
        m['genre'] = max(tags, key=lambda t: t.get('count', 0)).get('name', '')

    m['track'] = 0
    return m


# ─── Merge ────────────────────────────────────────────────────────

def merge_metadata(itunes_results, mb_recordings, yt_info, clean_title=''):
    itunes = _itunes_to_meta(itunes_results[0]) if itunes_results else {}
    mb = _mb_to_meta(_best_mb_recording(mb_recordings, clean_title)) if mb_recordings else {}

    yt = {
        'title': yt_info.get('title', ''),
        'artist': yt_info.get('uploader', ''),
        'album': '',
        'year': (yt_info.get('upload_date') or '')[:4],
        'genre': '',
        'track': 0,
        'cover_url': yt_info.get('thumbnail', ''),
    }

    merged = {}
    for key in ('title', 'artist', 'album', 'year', 'genre', 'track', 'cover_url'):
        merged[key] = itunes.get(key) or mb.get(key) or yt.get(key) or ''

    if not itunes.get('cover_url') and yt.get('cover_url'):
        merged['cover_url'] = yt['cover_url']

    return merged


# ─── Lyrics ────────────────────────────────────────────────────────

def fetch_lyrics(artist, title):
    if not artist or not title:
        return ''
    params = urllib.parse.urlencode({'artist_name': artist, 'track_name': title})
    url = f"{LRCLIB_URL}/get?{params}"
    data = _fetch_json(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    if data:
        return data.get('plainLyrics') or data.get('syncedLyrics') or data.get('lyrics') or ''

    params = urllib.parse.urlencode({'q': f'{artist} {title}'})
    url = f"{LRCLIB_URL}/search?{params}"
    data = _fetch_json(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    if data and len(data) > 0:
        return data[0].get('plainLyrics') or data[0].get('syncedLyrics') or data[0].get('lyrics') or ''
    return ''


# ─── Artwork ──────────────────────────────────────────────────────

def get_large_artwork(url_100):
    if not url_100:
        return None
    if '100x100bb' in url_100:
        return url_100.replace('100x100bb', '600x600bb')
    # Try common size patterns
    for small in ('50x50', '100x100', '75x75'):
        large = small.replace('50', '600').replace('75', '600')
        if small in url_100:
            return url_100.replace(small, large)
    return url_100


def download_image(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            return data if len(data) >= 100 else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


# ─── High-level lookup ────────────────────────────────────────────

def lookup_all(clean_title, raw_artist, yt_title, yt_info):
    itunes_results = search_itunes(clean_title, raw_artist, yt_title)
    mb_recordings = search_musicbrainz(clean_title, raw_artist)
    merged = merge_metadata(itunes_results, mb_recordings, yt_info, clean_title)

    lyrics = fetch_lyrics(merged.get('artist', ''), merged.get('title', ''))
    merged['lyrics'] = lyrics

    return merged, bool(itunes_results or mb_recordings)
