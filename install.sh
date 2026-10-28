#!/bin/bash
# One-time setup. Run from inside the job-search folder:  bash install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BIN="$(command -v claude || true)"

if [ -z "$CLAUDE_BIN" ]; then
  echo "Claude Code not found. Install it and run 'claude' once to log in, then rerun this."
  exit 1
fi

mkdir -p "$DIR/reports" "$DIR/logs"
touch "$DIR/seen_jobs.txt"
[ -f "$DIR/jobs_log.csv" ] || echo "date_found,fit,firm,role,location,start,link,status" > "$DIR/jobs_log.csv"
echo "CLAUDE_BIN=\"$CLAUDE_BIN\"" > "$DIR/.env"
chmod +x "$DIR/run.sh"

PLIST="$HOME/Library/LaunchAgents/com.dannywalker.jobsearch.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.dannywalker.jobsearch</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$DIR/run.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$DIR/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/launchd.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Done. Runs daily at 7:30am (or right after your Mac wakes if it was asleep)."
echo "Test now with:  bash $DIR/run.sh"
