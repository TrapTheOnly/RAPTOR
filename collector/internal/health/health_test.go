package health

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestHealthz(t *testing.T) {
	srv := httptest.NewServer(Handler("dns01", "1.1.0", nil))
	defer srv.Close()
	resp, err := http.Get(srv.URL + "/healthz")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if payload["ok"] != true || payload["hostname"] != "dns01" {
		t.Fatalf("unexpected payload %#v", payload)
	}
}

func TestRunTriggersCallback(t *testing.T) {
	var called atomic.Int32
	srv := httptest.NewServer(Handler("dns01", "1.1.0", func() { called.Add(1) }))
	defer srv.Close()
	resp, err := http.Post(srv.URL+"/run", "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		t.Fatalf("status %d body %s", resp.StatusCode, body)
	}
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		if called.Load() == 1 {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("onRun was not called")
}

func TestRunRequiresPost(t *testing.T) {
	srv := httptest.NewServer(Handler("dns01", "1.1.0", func() {}))
	defer srv.Close()
	resp, err := http.Get(srv.URL + "/run")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("status %d", resp.StatusCode)
	}
}
