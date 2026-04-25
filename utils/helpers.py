# Copyright (C) 2025
# Helper Functions for AnkiConnect
#
# This module contains general utility functions used across the codebase.

import sys

if sys.version_info[0] < 3:
    import urllib2
    web = urllib2
else:
    unicode = str
    from urllib import request
    web = request

URL_TIMEOUT = 10
USER_AGENT = "AnkiConnect/GlobalEdge"

try:
    import requests as _requests
    _session = _requests.Session()
    _session.headers["User-Agent"] = USER_AGENT
except ImportError:
    _session = None


def makeBytes(data):
    """Convert string to bytes"""
    return data.encode('utf-8')


def makeStr(data):
    """Convert bytes to string"""
    return data.decode('utf-8')


def download(url):
    """Download content from a URL.

    Uses a module-level requests.Session so HTTPS connections are pooled and
    TLS handshakes amortize across notes added in the same Anki session.
    """
    if _session is not None:
        try:
            resp = _session.get(url, timeout=URL_TIMEOUT)
        except _requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        return resp.content

    req = web.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = web.urlopen(req, timeout=URL_TIMEOUT)
    except web.URLError:
        return None
    if resp.code != 200:
        return None
    return resp.read()


def verifyString(string):
    """Verify that a value is a string"""
    t = type(string)
    return t == str or t == unicode


def verifyStringList(strings):
    """Verify that all items in a list are strings"""
    for s in strings:
        if not verifyString(s):
            return False
    return True


def getMimeType(filename):
    """Get MIME type based on file extension"""
    import os
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4',
        '.flac': 'audio/flac',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.txt': 'text/plain',
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.pdf': 'application/pdf'
    }
    return mime_types.get(ext, 'application/octet-stream')


def audioInject(note, fields, filename):
    """Inject audio reference into note fields"""
    for field in fields:
        if field in note:
            note[field] += u'[sound:{}]'.format(filename)
