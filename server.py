#!/usr/bin/env python3
"""
Server for Crate Digger.

Serves the static files and the single-page app on the root route, plus one
extra endpoint the app's Download button calls:

    GET /download?url=<youtube watch url>&title=<artist - title>

which shells out to yt-dlp to grab the audio as an MP3 and streams it back to
the browser as a file download.

Runs locally (double-click "Start Sample Digger.command") and on Codesphere.
The port comes from $PORT (Codesphere sets 3000); it defaults to 8765 locally.
Bound to 127.0.0.1 — Codesphere routes external traffic to localhost, and the
download endpoint executes a subprocess based on request input.
"""
import http.server
import json
import re
import subprocess
import sys
import tempfile
import os
import urllib.parse

PORT = int(os.environ.get('PORT', '8765'))
# Locally bind loopback (the /download endpoint runs a subprocess, so don't expose
# it to the LAN); on Codesphere set HOST=0.0.0.0 so the workspace router can reach it.
HOST = os.environ.get('HOST', '127.0.0.1')
APP_FILE = 'sample-digger.html'   # served on the main route "/"
YOUTUBE_RE = re.compile(r'^https://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}([&?].*)?$')


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/health':
            self.send_json(200, {'status': 'ok'})
        elif parsed.path == '/download':
            self.handle_download(parsed)
        else:
            if parsed.path == '/':
                self.path = '/' + APP_FILE   # serve the app on the main route
            super().do_GET()

    def handle_download(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        url = (qs.get('url') or [''])[0]
        title = (qs.get('title') or ['track'])[0]

        if not YOUTUBE_RE.match(url):
            self.send_json(400, {'error': 'Not a valid YouTube URL.'})
            return

        safe_title = re.sub(r'[^\w\s.,()\'&-]', '', title).strip() or 'track'

        with tempfile.TemporaryDirectory() as tmp:
            outtmpl = os.path.join(tmp, '%(title)s.%(ext)s')
            # Invoke yt-dlp as a module of the current interpreter so it works
            # regardless of whether ~/.local/bin is on PATH (matters on Codesphere,
            # where it's pip-installed in the prepare step).
            try:
                subprocess.run(
                    [sys.executable, '-m', 'yt_dlp', '-x', '--audio-format', 'mp3',
                     '--audio-quality', '0', '--no-playlist', '-o', outtmpl, '--', url],
                    check=True, capture_output=True, text=True, timeout=180
                )
            except subprocess.TimeoutExpired:
                self.send_json(504, {'error': 'Download timed out.'})
                return
            except subprocess.CalledProcessError as e:
                err = (e.stderr or '').strip()
                if 'No module named' in err:
                    self.send_json(500, {'error': 'yt-dlp is not installed on the server.'})
                    return
                msg = err.splitlines()[-1] if err else 'yt-dlp failed.'
                self.send_json(502, {'error': msg[:200]})
                return

            files = [f for f in os.listdir(tmp) if f.endswith('.mp3')]
            if not files:
                self.send_json(502, {'error': 'No audio file produced (is ffmpeg installed?).'})
                return

            path = os.path.join(tmp, files[0])
            size = os.path.getsize(path)
            fname = urllib.parse.quote(safe_title + '.mp3')

            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Content-Length', str(size))
            self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{fname}")
            self.end_headers()
            with open(path, 'rb') as f:
                self.wfile.write(f.read())

    def send_json(self, status, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if '/download' in (self.path or ''):
            super().log_message(fmt, *args)
        # keep static-file request logs quiet


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Serving Crate Digger on http://{HOST}:{PORT} (Ctrl+C to stop)')
    httpd.serve_forever()
