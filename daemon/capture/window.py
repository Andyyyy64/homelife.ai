from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# Persistent PowerShell script: polls every POLL_MS, outputs only on focus change
_PS_MONITOR = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class FGWin {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$lastProc = ""
$lastTitle = ""
while ($true) {
    $hwnd = [FGWin]::GetForegroundWindow()
    $proc = ""
    $title = ""
    if ($hwnd -ne [IntPtr]::Zero) {
        $sb = New-Object System.Text.StringBuilder 512
        [void][FGWin]::GetWindowText($hwnd, $sb, 512)
        $title = $sb.ToString()
        $wpid = 0
        [void][FGWin]::GetWindowThreadProcessId($hwnd, [ref]$wpid)
        try { $proc = (Get-Process -Id $wpid -ErrorAction Stop).ProcessName } catch { $proc = "" }
    }
    if ($proc -eq "ScreenClippingHost") { Start-Sleep -Milliseconds POLL_MS_PLACEHOLDER; continue }
    if ($proc -ne $lastProc -or $title -ne $lastTitle) {
        [Console]::Out.WriteLine("FOCUS|$proc|$title")
        [Console]::Out.Flush()
        $lastProc = $proc
        $lastTitle = $title
    }
    Start-Sleep -Milliseconds POLL_MS_PLACEHOLDER
}
"""

# AppleScript to get frontmost app name and window title
_OSASCRIPT_GET_WINDOW = """
tell application "System Events"
    try
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
        try
            set winTitle to name of front window of frontApp
        on error
            set winTitle to ""
        end try
        return appName & "|" & winTitle
    on error
        return "|"
    end try
end tell
"""


class WindowMonitor:
    """Monitor foreground window changes.

    Uses osascript on macOS, PowerShell + Win32 on WSL2/Windows.
    Records each focus change to window_events table for precise app usage tracking.
    """

    def __init__(self, db_path: Path, poll_ms: int = 500):
        self._db_path = db_path
        self._poll_ms = poll_ms
        self._current_proc = ""
        self._current_title = ""
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None

    def start(self):
        """Start monitoring in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="window-monitor")
        self._thread.start()
        log.info("Window monitor started (poll=%dms, platform=%s)", self._poll_ms, sys.platform)

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def current(self) -> tuple[str, str]:
        """Get current (process_name, window_title)."""
        with self._lock:
            return self._current_proc, self._current_title

    def _run(self):
        while self._running:
            try:
                if sys.platform == "darwin":
                    self._run_monitor_mac()
                else:
                    self._run_monitor_wsl()
            except FileNotFoundError as e:
                log.warning("Window monitoring command not found (%s), monitoring disabled", e)
                return
            except Exception:
                log.exception("Window monitor error, restarting in 5s...")
                time.sleep(5)

    def _run_monitor_mac(self):
        """Poll frontmost app via osascript (macOS)."""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            while self._running:
                try:
                    result = subprocess.run(
                        ["osascript", "-e", _OSASCRIPT_GET_WINDOW],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    output = result.stdout.strip()
                    if "|" in output:
                        proc, _, title = output.partition("|")
                    else:
                        proc, title = output, ""
                    proc = proc.strip()
                    title = title.strip()

                    with self._lock:
                        changed = proc != self._current_proc or title != self._current_title
                        self._current_proc = proc
                        self._current_title = title

                    if changed and proc:
                        now = datetime.now()
                        conn.execute(
                            "INSERT INTO window_events (timestamp, process_name, window_title) VALUES (?, ?, ?)",
                            (now.isoformat(), proc, title),
                        )
                        conn.commit()
                        log.info("Window: %s | %s", proc, title[:60])
                except subprocess.TimeoutExpired:
                    log.debug("osascript timed out")
                except Exception:
                    log.debug("osascript error", exc_info=True)

                time.sleep(self._poll_ms / 1000)
        finally:
            conn.close()

    def _run_monitor_wsl(self):
        """Persistent PowerShell process for WSL2/Windows window monitoring."""
        script = _PS_MONITOR.replace("POLL_MS_PLACEHOLDER", str(self._poll_ms))
        self._process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            for line in self._process.stdout:  # type: ignore[union-attr]
                if not self._running:
                    break
                line = line.strip()
                if not line.startswith("FOCUS|"):
                    continue
                parts = line.split("|", 2)
                if len(parts) < 3:
                    continue
                _, proc, title = parts

                with self._lock:
                    changed = proc != self._current_proc or title != self._current_title
                    self._current_proc = proc
                    self._current_title = title

                if changed and proc:
                    now = datetime.now()
                    conn.execute(
                        "INSERT INTO window_events (timestamp, process_name, window_title) VALUES (?, ?, ?)",
                        (now.isoformat(), proc, title),
                    )
                    conn.commit()
                    log.info("Window: %s | %s", proc, title[:60])
        finally:
            conn.close()

        if self._process:
            self._process.wait()
            self._process = None
