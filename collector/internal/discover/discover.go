package discover

import (
	"os"
	"os/exec"
	"path/filepath"
	"raptor-collector/internal/axfr"
	"raptor-collector/internal/config"
	"raptor-collector/internal/namedconf"
	"raptor-collector/internal/zone"
	"runtime"
	"strings"
)

type Zone struct {
	Name      string
	Source    string
	FilePath  string
	SOASerial string
	Records   []zone.Record
}

var bindCandidates = []string{
	"/etc/bind/named.conf",
	"/etc/named.conf",
	"/etc/named/named.conf",
	"/chroot/etc/named.conf",
}

var pdnsCandidates = []string{
	"/etc/powerdns/pdns.conf",
	"/etc/pdns/pdns.conf",
}

func loadFile(path, origin string) []zone.Record {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	return zone.Parse(string(raw), origin)
}

func discoverBind(conf string) []Zone {
	candidates := bindCandidates
	if strings.TrimSpace(conf) != "" {
		candidates = []string{conf}
	}
	var found []Zone
	for _, path := range candidates {
		if _, err := os.Stat(path); err != nil {
			continue
		}
		for _, z := range namedconf.Load(path) {
			recs := []zone.Record{}
			if z.FilePath != "" {
				recs = loadFile(z.FilePath, z.Name)
			}
			found = append(found, Zone{Name: z.Name, Source: "bind", FilePath: z.FilePath, SOASerial: zone.SOASerial(recs), Records: recs})
		}
		if len(found) > 0 {
			break
		}
	}
	return found
}

func discoverPowerDNS(conf string) []Zone {
	path := conf
	if path == "" {
		for _, c := range pdnsCandidates {
			if _, err := os.Stat(c); err == nil {
				path = c
				break
			}
		}
	}
	if path == "" {
		return nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	bindConfig := ""
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(strings.Split(line, "#")[0])
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		key := strings.TrimSpace(parts[0])
		if key == "bind-config" || key == "bind-config-file" {
			bindConfig = strings.TrimSpace(parts[1])
		}
	}
	if bindConfig != "" {
		if _, err := os.Stat(bindConfig); err == nil {
			var found []Zone
			for _, z := range namedconf.Load(bindConfig) {
				recs := []zone.Record{}
				if z.FilePath != "" {
					recs = loadFile(z.FilePath, z.Name)
				}
				found = append(found, Zone{Name: z.Name, Source: "powerdns", FilePath: z.FilePath, SOASerial: zone.SOASerial(recs), Records: recs})
			}
			if len(found) > 0 {
				return found
			}
		}
	}
	out, err := exec.Command("pdnsutil", "list-all-zones").Output()
	if err != nil {
		return nil
	}
	var found []Zone
	for _, line := range strings.Split(string(out), "\n") {
		name := strings.ToLower(strings.TrimSuffix(strings.TrimSpace(line), "."))
		if name != "" {
			found = append(found, Zone{Name: name, Source: "powerdns"})
		}
	}
	return found
}

func discoverWindows() []Zone {
	if runtime.GOOS != "windows" {
		return nil
	}
	out, err := exec.Command("dnscmd", ".", "/EnumZones").Output()
	if err != nil {
		return nil
	}
	var found []Zone
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		name := strings.ToLower(strings.TrimSuffix(fields[0], "."))
		if name == "" || name == "zone" || strings.Contains(strings.ToLower(name), "enumzone") {
			continue
		}
		if !strings.Contains(name, ".") && (name == "." || name == "command") {
			continue
		}
		z := Zone{Name: name, Source: "windows_dns"}
		printed, err := exec.Command("dnscmd", ".", "/ZonePrint", name).Output()
		if err == nil {
			recs := zone.Parse(string(printed), name)
			z.Records = recs
			z.SOASerial = zone.SOASerial(recs)
		}
		found = append(found, z)
	}
	return found
}

func discoverDirs(dirs []string) []Zone {
	var found []Zone
	for _, dir := range dirs {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			path := filepath.Join(dir, entry.Name())
			origin := strings.TrimSuffix(entry.Name(), ".db")
			origin = strings.ToLower(strings.TrimSuffix(origin, "."))
			recs := loadFile(path, origin)
			found = append(found, Zone{Name: origin, Source: "zone_dir", FilePath: path, SOASerial: zone.SOASerial(recs), Records: recs})
		}
	}
	return found
}

func All(cfg *config.Config) []Zone {
	var found []Zone
	found = append(found, discoverBind(cfg.BindConf)...)
	found = append(found, discoverPowerDNS(cfg.PowerDNSConf)...)
	found = append(found, discoverWindows()...)
	found = append(found, discoverDirs(cfg.ZoneDirs)...)
	byName := map[string]Zone{}
	for _, z := range found {
		if z.Name == "" {
			continue
		}
		if _, ok := byName[z.Name]; !ok {
			byName[z.Name] = z
		}
	}
	out := make([]Zone, 0, len(byName))
	for _, z := range byName {
		if len(z.Records) == 0 && cfg.AXFRServer != "" {
			if recs, err := axfr.Transfer(z.Name, cfg.AXFRServer, cfg.TSIGName, cfg.TSIGSecret, cfg.TSIGAlgorithm); err == nil {
				z.Records = recs
				z.SOASerial = zone.SOASerial(recs)
			}
		}
		out = append(out, z)
	}
	return out
}

func Payloads(zones []Zone) []map[string]any {
	out := make([]map[string]any, 0, len(zones))
	for _, z := range zones {
		out = append(out, map[string]any{
			"name":       z.Name,
			"soa_serial": z.SOASerial,
			"records":    zone.ToPayload(z.Records),
		})
	}
	return out
}
