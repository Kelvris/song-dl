import base64
import os
import mutagen.id3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, USLT
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggopus import OggOpus


def _detect_mime(data):
    if data[:4] == b'\x89PNG':
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[:2] == b'\xff\xd8':
        return 'image/jpeg'
    return 'image/jpeg'


def tag_file(filepath, meta, cover_data=None):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.mp3':
        _tag_mp3(filepath, meta, cover_data)
    elif ext == '.m4a':
        _tag_m4a(filepath, meta, cover_data)
    elif ext == '.flac':
        _tag_flac(filepath, meta, cover_data)
    elif ext == '.opus':
        _tag_opus(filepath, meta, cover_data)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def _tag_mp3(filepath, meta, cover_data):
    try:
        audio = ID3(filepath)
    except mutagen.id3.ID3NoHeaderError:
        audio = ID3()
    except Exception as e:
        raise RuntimeError(f"Failed to read MP3 tags: {e}") from e

    audio['TIT2'] = TIT2(encoding=3, text=meta.get('title', ''))
    audio['TPE1'] = TPE1(encoding=3, text=meta.get('artist', ''))
    audio['TALB'] = TALB(encoding=3, text=meta.get('album', ''))

    if meta.get('year'):
        audio['TDRC'] = TDRC(encoding=3, text=str(meta['year']))

    if meta.get('genre'):
        audio['TCON'] = TCON(encoding=3, text=meta['genre'])

    if meta.get('track'):
        audio['TRCK'] = TRCK(encoding=3, text=str(meta['track']))

    if cover_data:
        audio['APIC'] = APIC(
            encoding=3, mime=_detect_mime(cover_data),
            type=3, desc='Cover', data=cover_data
        )

    if meta.get('lyrics'):
        audio['USLT'] = USLT(encoding=3, lang='eng', desc='', text=meta['lyrics'])

    audio.save(filepath)


def _tag_m4a(filepath, meta, cover_data):
    audio = MP4(filepath)

    audio['\xa9nam'] = meta.get('title', '')
    audio['\xa9ART'] = meta.get('artist', '')
    audio['\xa9alb'] = meta.get('album', '')

    if meta.get('year'):
        audio['\xa9day'] = str(meta['year'])

    if meta.get('genre'):
        audio['\xa9gen'] = meta['genre']

    if meta.get('track'):
        audio['trkn'] = [(int(meta['track']), 0)]

    if cover_data:
        mime = _detect_mime(cover_data)
        fmt = MP4Cover.FORMAT_PNG if mime == 'image/png' else MP4Cover.FORMAT_JPEG
        audio['covr'] = [MP4Cover(cover_data, fmt)]

    if meta.get('lyrics'):
        audio['\xa9lyr'] = meta['lyrics']

    audio.save()


def _tag_flac(filepath, meta, cover_data):
    audio = FLAC(filepath)

    audio['title'] = meta.get('title', '')
    audio['artist'] = meta.get('artist', '')
    audio['album'] = meta.get('album', '')

    if meta.get('year'):
        audio['date'] = str(meta['year'])

    if meta.get('genre'):
        audio['genre'] = meta['genre']

    if meta.get('track'):
        audio['tracknumber'] = str(meta['track'])

    if meta.get('lyrics'):
        audio['lyrics'] = meta['lyrics']

    if cover_data:
        pic = Picture()
        pic.data = cover_data
        pic.type = 3
        pic.mime = _detect_mime(cover_data)
        pic.desc = 'Cover'
        audio.add_picture(pic)

    audio.save()


def _tag_opus(filepath, meta, cover_data):
    audio = OggOpus(filepath)

    audio['title'] = meta.get('title', '')
    audio['artist'] = meta.get('artist', '')
    audio['album'] = meta.get('album', '')

    if meta.get('year'):
        audio['date'] = str(meta['year'])

    if meta.get('genre'):
        audio['genre'] = meta['genre']

    if meta.get('track'):
        audio['tracknumber'] = str(meta['track'])

    if meta.get('lyrics'):
        audio['lyrics'] = meta['lyrics']

    if cover_data:
        pic = Picture()
        pic.data = cover_data
        pic.type = 3
        pic.mime = _detect_mime(cover_data)
        pic.desc = 'Cover'
        audio['metadata_block_picture'] = base64.b64encode(pic.write()).decode()

    audio.save()
