package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"raptor-collector/internal/client"
	"raptor-collector/internal/config"
	"raptor-collector/internal/discover"
	"raptor-collector/internal/health"
	"raptor-collector/internal/service"
	"strings"
	"sync"
	"time"
)

var Version = "1.1.0"

func main() {
	log.SetFlags(log.LstdFlags)
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "setup":
		os.Exit(runSetup(os.Args[2:]))
	case "run":
		os.Exit(runLoop(os.Args[2:]))
	case "discover":
		os.Exit(runDiscover(os.Args[2:]))
	case "version":
		fmt.Println(Version)
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, `raptor-collector %s
Usage:
  raptor-collector setup --url URL --token TOKEN [--name NAME] [--mode one-sided|two-sided]
  raptor-collector run [--once]
  raptor-collector discover
`, Version)
}

func runSetup(args []string) int {
	fs := flag.NewFlagSet("setup", flag.ExitOnError)
	url := fs.String("url", os.Getenv("RAPTOR_URL"), "RAPTOR base URL")
	token := fs.String("token", os.Getenv("RAPTOR_ENROLL_TOKEN"), "one-time enroll token")
	name := fs.String("name", "", "display name in RAPTOR")
	hostname := fs.String("hostname", hostnameDefault(), "agent hostname")
	mode := fs.String("mode", "one-sided", "one-sided (airgap) or two-sided")
	listen := fs.String("listen", "0.0.0.0:7444", "listen address for two-sided ping")
	callback := fs.String("callback-url", "", "URL RAPTOR uses to ping this agent")
	interval := fs.Int("interval", 300, "ingest interval in seconds")
	bindConf := fs.String("bind-conf", os.Getenv("RAPTOR_BIND_CONF"), "named.conf path")
	axfr := fs.String("axfr-server", os.Getenv("RAPTOR_AXFR_SERVER"), "optional AXFR server host:port")
	_ = fs.Parse(args)
	if strings.TrimSpace(*url) == "" || strings.TrimSpace(*token) == "" {
		log.Print("--url and --token are required")
		return 2
	}
	normalized := config.NormalizeMode(*mode)
	display := strings.TrimSpace(*name)
	if display == "" {
		display = *hostname
	}
	cb := strings.TrimSpace(*callback)
	if normalized == "two_sided" && cb == "" {
		cb = config.AdvertisedCallback("", *listen, *hostname, config.FirstNonLoopbackIPv4())
	}
	cli := client.New(*url, "")
	enrolled, err := cli.Enroll(*token, *hostname, display, normalized, Version, cb, *interval)
	if err != nil {
		log.Printf("enroll failed: %v", err)
		return 1
	}
	cfg := &config.Config{
		RaptorURL:       strings.TrimRight(*url, "/"),
		Token:           enrolled.Token,
		SourceID:        enrolled.SourceID,
		AgentID:         enrolled.AgentID,
		Hostname:        *hostname,
		DisplayName:     display,
		Mode:            normalized,
		Listen:          *listen,
		CallbackURL:     cb,
		IntervalSeconds: *interval,
		BindConf:        *bindConf,
		AXFRServer:      *axfr,
		TSIGAlgorithm:   "hmac-sha256",
		StatePath:       config.DefaultPath(),
	}
	if err := cfg.Save(); err != nil {
		log.Printf("failed to write config: %v", err)
		return 1
	}
	fmt.Printf("Enrolled as %s (source_id=%d). Config: %s\n", display, enrolled.SourceID, cfg.StatePath)
	if normalized == "one_sided" {
		fmt.Println("Mode: one-sided. This host will contact RAPTOR; RAPTOR cannot ping it.")
	} else {
		fmt.Println("Mode: two-sided. RAPTOR can ping this agent at", cb)
	}
	fmt.Println(service.Install(cfg.StatePath))
	return 0
}

func runDiscover(args []string) int {
	cfg := loadOrEnv()
	zones := discover.All(cfg)
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(discover.Payloads(zones))
	return 0
}

func runLoop(args []string) int {
	fs := flag.NewFlagSet("run", flag.ExitOnError)
	once := fs.Bool("once", false, "run a single cycle")
	_ = fs.Parse(args)
	cfg, err := config.Load(config.DefaultPath())
	if err != nil {
		log.Printf("load config: %v (run setup first)", err)
		return 1
	}
	var cycleMu sync.Mutex
	var lastErr error
	runCycle := func() {
		if !cycleMu.TryLock() {
			log.Print("collector cycle already running")
			return
		}
		defer cycleMu.Unlock()
		lastErr = cycle(cfg)
		if lastErr != nil {
			log.Printf("cycle: %v", lastErr)
		}
	}
	if cfg.Mode == "two_sided" {
		go func() {
			addr := cfg.Listen
			if addr == "" {
				addr = "0.0.0.0:7444"
			}
			log.Printf("two-sided health listener on %s", addr)
			if err := health.Serve(addr, cfg.Hostname, Version, runCycle); err != nil {
				log.Printf("health server: %v", err)
			}
		}()
	}
	runCycle()
	if *once {
		if lastErr != nil {
			return 1
		}
		return 0
	}
	ticker := time.NewTicker(time.Duration(cfg.IntervalSeconds) * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		runCycle()
	}
	return 0
}

func cycle(cfg *config.Config) error {
	cli := client.New(cfg.RaptorURL, cfg.Token)
	zones := discover.All(cfg)
	summaries := make([]map[string]any, 0, len(zones))
	for _, z := range zones {
		summaries = append(summaries, map[string]any{"name": z.Name, "soa_serial": z.SOASerial})
	}
	hb, err := cli.Heartbeat(map[string]any{
		"zones":          summaries,
		"agent_version":  Version,
		"mode":           cfg.Mode,
		"callback_url":     cfg.CallbackURL,
		"display_name":     cfg.DisplayName,
		"interval_seconds": cfg.IntervalSeconds,
	})
	if err != nil {
		return err
	}
	if tok := cli.Token; tok != "" && tok != cfg.Token {
		cfg.Token = tok
		_ = cfg.Save()
	}
	_ = hb
	payloads := discover.Payloads(zones)
	hasRecords := false
	for _, z := range zones {
		if len(z.Records) > 0 {
			hasRecords = true
			break
		}
	}
	if !hasRecords {
		log.Print("no zone records collected")
		return nil
	}
	cursor := ""
	if len(summaries) > 0 {
		if s, ok := summaries[0]["soa_serial"].(string); ok {
			cursor = s
		}
	}
	ing, err := cli.Ingest(map[string]any{
		"source_id":     cfg.SourceID,
		"cursor":        cursor,
		"agent_version": Version,
		"zones":         payloads,
	})
	if err != nil {
		return err
	}
	if cli.Token != "" && cli.Token != cfg.Token {
		cfg.Token = cli.Token
		_ = cfg.Save()
	}
	log.Printf("ingested stored=%d projected=%d", ing.Stored, ing.Projected)
	return nil
}

func loadOrEnv() *config.Config {
	cfg, err := config.Load(config.DefaultPath())
	if err != nil {
		return &config.Config{IntervalSeconds: 300, Mode: "one_sided"}
	}
	return cfg
}

func hostnameDefault() string {
	h, err := os.Hostname()
	if err != nil || h == "" {
		return "dns-collector"
	}
	if i := strings.IndexByte(h, '.'); i > 0 {
		return h[:i]
	}
	return h
}
