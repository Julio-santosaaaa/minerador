#!/usr/bin/env bash
# Instala (ou remove com --uninstall) o LaunchAgent que roda o minerador todo dia.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.julio.minerador"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HOUR="${MINERADOR_HOUR:-23}"     # hora do dia (0-23); export MINERADOR_HOUR=9 pra mudar
MIN="${MINERADOR_MIN:-30}"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removido: $LABEL"
  exit 0
fi

if [ ! -x "$HERE/.venv/bin/python" ]; then
  echo "venv não encontrado. Rode:" >&2
  echo "  cd '$HERE' && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium" >&2
  exit 1
fi

mkdir -p "$HERE/data" "$(dirname "$PLIST")"

# wrapper diário: minera 20 (novas + backlog -> Notion) e DEPOIS recalcula o tracker
# das ofertas que já estão no Notion. Pausa entre as duas fases (menos risco de bloqueio).
cat > "$HERE/scripts/daily.sh" <<'DAILY_EOF'
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "=== $(date '+%F %T')  MINERAÇÃO ==="
"$PY" -u -m minerador run || echo "run falhou (segue pro recalc)"
echo "=== pausa 120s ==="
sleep 120
echo "=== $(date '+%F %T')  RECÁLCULO / TRACKER ==="
"$PY" -u -m minerador recalc || echo "recalc falhou"
echo "=== $(date '+%F %T')  FIM ==="
DAILY_EOF
chmod +x "$HERE/scripts/daily.sh"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$HERE/scripts/daily.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$HERE/data/cron.log</string>
  <key>StandardErrorPath</key><string>$HERE/data/cron.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
PLIST_EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "instalado: roda todo dia $HOUR:$(printf '%02d' "$MIN")  ->  $HERE/data/cron.log"
echo "testar agora:  launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "ver log:       tail -f '$HERE/data/cron.log'"
