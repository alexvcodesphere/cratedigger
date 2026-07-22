#!/bin/bash
# Serves sample-digger.html over localhost. YouTube blocks embeds on file:// pages
# (error 153, missing referer), so the app must be opened through http.
# Uses server.py (not the plain http.server module) so the Download button's
# /download endpoint — which shells out to yt-dlp — is available.
cd "$(dirname "$0")"
URL="http://localhost:8765/sample-digger.html"
if lsof -i :8765 >/dev/null 2>&1; then
  open "$URL"
else
  (sleep 1; open "$URL") &
  exec python3 server.py
fi
