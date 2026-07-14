"""Tests for core utilities and helpers."""

import sys
import os

# Ensure songdl package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from songdl.core import _sanitize_path, _apply_pattern, _is_url
from songdl.metadata import clean_youtube_title
from songdl.tagger import _detect_mime


# --- _sanitize_path ---


def test_sanitize_path_replaces_invalid_chars():
    result = _sanitize_path('foo:bar"baz|qux?*')
    assert result == "foo_bar_baz_qux__"


def test_sanitize_path_replaces_slash():
    result = _sanitize_path("a/b/c")
    assert result == "a_b_c"


def test_sanitize_path_strips_whitespace():
    result = _sanitize_path("  hello  ")
    assert result == "hello"


def test_sanitize_path_empty_becomes_underscore():
    result = _sanitize_path("")
    assert result == "_"


def test_sanitize_path_all_invalid():
    result = _sanitize_path('<>:"|?*')
    assert result == "_______"


# --- _apply_pattern ---


def test_apply_pattern_basic():
    result = _apply_pattern(
        "{artist} - {title}", "TestArtist", "Album", "TestTitle", 1, ".mp3"
    )
    assert result == "TestArtist - TestTitle.mp3"


def test_apply_pattern_with_album_path():
    result = _apply_pattern(
        "{artist}/{album}/{title}", "Artist", "Album", "Title", 0, ".mp3"
    )
    assert result == "Artist/Album/Title.mp3"


def test_apply_pattern_fallback_defaults():
    result = _apply_pattern("{artist} - {title}", None, None, None, None, ".mp3")
    assert result == "Unknown - Unknown.mp3"


def test_apply_pattern_track_number():
    result = _apply_pattern("{track}. {title}", "A", "B", "T", 42, ".flac")
    assert result == "42. T.flac"


# --- _is_url ---


def test_is_url_https():
    assert _is_url("https://example.com/path?q=1")


def test_is_url_http():
    assert _is_url("http://youtube.com/watch?v=abc")


def test_is_url_no_scheme():
    assert _is_url("youtube.com/watch")


def test_is_url_not_url():
    assert not _is_url("just some text")
    assert not _is_url("")
    assert not _is_url("  ")


# --- clean_youtube_title ---


def test_clean_youtube_title_removes_official_video():
    result = clean_youtube_title("Song Name (Official Video)")
    assert result == "Song Name"


def test_clean_youtube_title_removes_lyrics():
    result = clean_youtube_title("Song Name (Lyrics)")
    assert result == "Song Name"


def test_clean_youtube_title_removes_pipe():
    result = clean_youtube_title("Song Name | Artist")
    assert result == "Song Name"


def test_clean_youtube_title_unchanged():
    result = clean_youtube_title("Plain Title")
    assert result == "Plain Title"


# --- _detect_mime ---


def test_detect_mime_jpeg():
    assert _detect_mime(b"\xff\xd8\xff\xe0...") == "image/jpeg"


def test_detect_mime_png():
    assert _detect_mime(b"\x89PNG\r\n\x1a\n...") == "image/png"


def test_detect_mime_webp():
    data = b"RIFF\x00\x00\x00\x00WEBP"
    assert _detect_mime(data) == "image/webp"


def test_detect_mime_fallback():
    assert _detect_mime(b"\x00\x00\x00\x00...") == "image/jpeg"


# --- Run all if executed directly ---
if __name__ == "__main__":
    tests = [
        test_sanitize_path_replaces_invalid_chars,
        test_sanitize_path_replaces_slash,
        test_sanitize_path_strips_whitespace,
        test_sanitize_path_empty_becomes_underscore,
        test_sanitize_path_all_invalid,
        test_apply_pattern_basic,
        test_apply_pattern_with_album_path,
        test_apply_pattern_fallback_defaults,
        test_apply_pattern_track_number,
        test_is_url_https,
        test_is_url_http,
        test_is_url_no_scheme,
        test_is_url_not_url,
        test_clean_youtube_title_removes_official_video,
        test_clean_youtube_title_removes_lyrics,
        test_clean_youtube_title_removes_pipe,
        test_clean_youtube_title_unchanged,
        test_detect_mime_jpeg,
        test_detect_mime_png,
        test_detect_mime_webp,
        test_detect_mime_fallback,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {type(e).__name__}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
