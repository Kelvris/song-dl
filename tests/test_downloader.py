"""Tests for yt-dlp integration helpers."""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from songdl import downloader


def test_version_comparison_handles_stable_and_nightly_versions():
    assert downloader.ytdlp_update_available(
        "2026.07.04", "2026.08.16.020253"
    )
    assert not downloader.ytdlp_update_available(
        "2026.8.16.20253.dev0", "2026.08.16.020253"
    )


def test_base_opts_explicitly_enables_node_when_deno_is_missing():
    def find_runtime(name):
        return "/usr/bin/node" if name == "node" else None

    with patch("songdl.downloader.shutil.which", side_effect=find_runtime):
        opts = downloader._base_opts()

    assert opts["js_runtimes"] == {"node": {"path": "/usr/bin/node"}}


def test_check_ytdlp_update_reads_latest_nightly_tag():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = (
        b'{"tag_name": "2026.08.16.020253"}'
    )
    with patch("urllib.request.urlopen", return_value=response):
        current, latest, error = downloader.check_ytdlp_update()

    assert current
    assert latest == "2026.08.16.020253"
    assert error is None


def test_update_ytdlp_installs_nightly_with_default_extras():
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")
    with patch("songdl.downloader.subprocess.run", return_value=completed) as run:
        updated, error = downloader.update_ytdlp()

    assert updated is True
    assert error is None
    command = run.call_args.args[0]
    assert "--pre" in command
    assert "yt-dlp[default]" in command


def test_update_ytdlp_reports_pip_failure():
    completed = SimpleNamespace(returncode=1, stdout="", stderr="network failed")
    with patch("songdl.downloader.subprocess.run", return_value=completed):
        updated, error = downloader.update_ytdlp()

    assert updated is False
    assert error == "network failed"
