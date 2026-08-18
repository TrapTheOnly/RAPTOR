package config

import (
	"encoding/json"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type Config struct {
	RaptorURL        string   `json:"raptor_url"`
	Token            string   `json:"token"`
	SourceID         int      `json:"source_id"`
	AgentID          int      `json:"agent_id"`
	Hostname         string   `json:"hostname"`
	DisplayName      string   `json:"display_name"`
	Mode             string   `json:"mode"`
	Listen           string   `json:"listen"`
	CallbackURL      string   `json:"callback_url"`
	IntervalSeconds  int      `json:"interval_seconds"`
	BindConf         string   `json:"bind_conf"`
	PowerDNSConf     string   `json:"powerdns_conf"`
	AXFRServer       string   `json:"axfr_server"`
	TSIGName         string   `json:"tsig_name"`
	TSIGSecret       string   `json:"tsig_secret"`
	TSIGAlgorithm    string   `json:"tsig_algorithm"`
	ZoneDirs         []string `json:"zone_dirs"`
	StatePath        string   `json:"-"`
}

func DefaultPath() string {
	if env := strings.TrimSpace(os.Getenv("RAPTOR_COLLECTOR_CONFIG")); env != "" {
		return env
	}
	if runtime.GOOS == "windows" {
		root := os.Getenv("ProgramData")
		if root == "" {
			root = `C:\ProgramData`
		}
		return filepath.Join(root, "raptor-collector", "config.json")
	}
	if os.Geteuid() == 0 {
		return "/etc/raptor-collector/config.json"
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".raptor-collector", "config.json")
}

func Load(path string) (*Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	cfg := &Config{StatePath: path, IntervalSeconds: 300, Mode: "one_sided"}
	if err := json.Unmarshal(raw, cfg); err != nil {
		return nil, err
	}
	cfg.StatePath = path
	if cfg.IntervalSeconds < 30 {
		cfg.IntervalSeconds = 30
	}
	if cfg.Mode == "" {
		cfg.Mode = "one_sided"
	}
	return cfg, nil
}

func (c *Config) Save() error {
	path := c.StatePath
	if path == "" {
		path = DefaultPath()
		c.StatePath = path
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func AdvertisedCallback(explicit, listen, hostname, advertisedIP string) string {
	if strings.TrimSpace(explicit) != "" {
		return strings.TrimSpace(explicit)
	}
	port := ListenPort(listen)
	if ip := strings.TrimSpace(advertisedIP); ip != "" {
		return "http://" + ip + ":" + port
	}
	if hostname = strings.TrimSpace(hostname); hostname != "" {
		return "http://" + hostname + ":" + port
	}
	return ""
}

func ListenPort(listen string) string {
	listen = strings.TrimSpace(listen)
	if listen == "" {
		return "7444"
	}
	_, port, err := net.SplitHostPort(listen)
	if err == nil && port != "" {
		return port
	}
	return "7444"
}

func FirstNonLoopbackIPv4() string {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return ""
	}
	for _, addr := range addrs {
		ipnet, ok := addr.(*net.IPNet)
		if !ok || ipnet.IP == nil || ipnet.IP.IsLoopback() {
			continue
		}
		ip := ipnet.IP.To4()
		if ip == nil || ip.IsLinkLocalUnicast() {
			continue
		}
		return ip.String()
	}
	return ""
}

func NormalizeMode(raw string) string {
	v := strings.ToLower(strings.TrimSpace(raw))
	v = strings.ReplaceAll(v, "-", "_")
	if v == "two_sided" || v == "twosided" || v == "two_way" {
		return "two_sided"
	}
	return "one_sided"
}
