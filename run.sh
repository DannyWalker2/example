#!/bin/bash
# Runs the daily job search. Called automatically each morning by launchd.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
source "$DIR/.env"
export PATH="$(dirname "$CLAUDE_BIN"):/opt/homebrew/bin:/usr/local/bin:$PATH"

TODAY=$(date +%F)
REPORT="reports/$TODAY.md"

# Only run once per day (launchd may retry after the Mac wakes up)
[ -f "$REPORT" ] && exit 0

"$CLAUDE_BIN" -p "Run today's job search following CLAUDE.md. Today is $TODAY. Write the report to $REPORT." \
  --allowedTools "WebSearch,WebFetch,Read,Write,Edit" \
  --max-turns 80 >> "logs/$TODAY.log" 2>&1

if [ -f "$REPORT" ]; then
  osascript -e 'display notification "Your job list is ready" with title "Job Search"'
  open "$REPORT"
fi
