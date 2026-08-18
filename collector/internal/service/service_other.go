//go:build !linux

package service

import "runtime"

func Install(cfgPath string) string {
	if runtime.GOOS == "windows" {
		return "Windows: use install.ps1 so a startup scheduled task keeps raptor-collector run alive."
	}
	return "Keep `raptor-collector run` under a supervisor."
}
