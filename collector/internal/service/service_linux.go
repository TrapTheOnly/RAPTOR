//go:build linux

package service

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

const unitPath = "/etc/systemd/system/raptor-collector.service"
const destBinary = "/usr/local/bin/raptor-collector"
const pidPath = "/var/run/raptor-collector.pid"
const logPath = "/var/log/raptor-collector.log"

func systemdIsInit() bool {
	_, err := os.Stat("/run/systemd/system")
	return err == nil
}

func Install(cfgPath string) string {
	exe, err := os.Executable()
	if err != nil {
		return "Could not locate this binary. Keep `raptor-collector run` running."
	}
	if os.Geteuid() != 0 {
		return "Run setup as root to install the collector service, or keep `raptor-collector run` running."
	}
	if err := copyExecutable(exe, destBinary); err != nil {
		return fmt.Sprintf("Could not install %s: %v", destBinary, err)
	}
	if systemdIsInit() {
		return installSystemd(cfgPath)
	}
	return startDetached()
}

func installSystemd(cfgPath string) string {
	unit := fmt.Sprintf(`[Unit]
Description=RAPTOR DNS collector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%s run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
`, destBinary)
	if err := os.WriteFile(unitPath, []byte(unit), 0o644); err != nil {
		return fmt.Sprintf("Could not write %s: %v", unitPath, err)
	}
	cmd := exec.Command("systemctl", "daemon-reload")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Sprintf("systemctl daemon-reload failed: %v (%s)", err, strings.TrimSpace(string(out)))
	}
	cmd = exec.Command("systemctl", "enable", "--now", "raptor-collector")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Sprintf("systemctl enable --now failed: %v (%s)", err, strings.TrimSpace(string(out)))
	}
	return fmt.Sprintf("Installed systemd unit raptor-collector.service (config %s).", cfgPath)
}

func startDetached() string {
	if pid, ok := runningPID(); ok {
		return fmt.Sprintf("systemd is not PID 1 (typical in Docker). Collector already running as pid %d.", pid)
	}
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Sprintf("Could not open %s: %v. Start with: %s run", logPath, err, destBinary)
	}
	cmd := exec.Command(destBinary, "run")
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return fmt.Sprintf("Could not start %s run: %v", destBinary, err)
	}
	pid := cmd.Process.Pid
	_ = os.WriteFile(pidPath, []byte(strconv.Itoa(pid)+"\n"), 0o644)
	_ = cmd.Process.Release()
	logFile.Close()
	return fmt.Sprintf("systemd is not PID 1 (typical in Docker). Started %s run in the background (pid %d). Logs: %s", destBinary, pid, logPath)
}

func runningPID() (int, bool) {
	raw, err := os.ReadFile(pidPath)
	if err != nil {
		return 0, false
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(raw)))
	if err != nil || pid <= 0 {
		return 0, false
	}
	if err := syscall.Kill(pid, 0); err != nil {
		return 0, false
	}
	return pid, true
}

func copyExecutable(src, dest string) error {
	srcAbs, err := filepath.Abs(src)
	if err != nil {
		return err
	}
	destAbs, err := filepath.Abs(dest)
	if err != nil {
		return err
	}
	if srcAbs == destAbs {
		return nil
	}
	in, err := os.Open(srcAbs)
	if err != nil {
		return err
	}
	defer in.Close()
	if err := os.MkdirAll(filepath.Dir(destAbs), 0o755); err != nil {
		return err
	}
	tmp := destAbs + ".tmp"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o755)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		_ = os.Remove(tmp)
		return err
	}
	if err := out.Close(); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, destAbs)
}
