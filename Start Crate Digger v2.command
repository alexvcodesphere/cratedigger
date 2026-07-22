#!/bin/bash
# Serves cratedigger.html (v2 UI) over localhost. YouTube blocks embeds on file://
# pages (error 153, missing referer), so the app must be opened through http.
# The original app remains available at sample-digger.html on the same server.
cd "$(dirname "$0")"
URL="http://localhost:8765/cratedigger.html"
if lsof -i :8765 >/dev/null 2>&1; then
  open "$URL"
else
  (sleep 1; open "$URL") &
  exec python3 -m http.server 8765
fi
