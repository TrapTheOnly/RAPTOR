package health

import (
	"encoding/json"
	"net/http"
)

func Handler(hostname, version string, onRun func()) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":       true,
			"hostname": hostname,
			"version":  version,
		})
	})
	mux.HandleFunc("/run", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if onRun == nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "collector is not running"})
			return
		}
		go onRun()
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	})
	return mux
}

func Serve(addr, hostname, version string, onRun func()) error {
	return http.ListenAndServe(addr, Handler(hostname, version, onRun))
}
