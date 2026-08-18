package config

import "testing"

func TestAdvertisedCallbackPrefersExplicit(t *testing.T) {
	got := AdvertisedCallback("http://dns01.corp:9000", "0.0.0.0:7444", "host", "10.0.0.5")
	if got != "http://dns01.corp:9000" {
		t.Fatalf("got %q", got)
	}
}

func TestAdvertisedCallbackPrefersIPOverHostname(t *testing.T) {
	got := AdvertisedCallback("", "0.0.0.0:7444", "cf23cf485016", "192.168.215.2")
	if got != "http://192.168.215.2:7444" {
		t.Fatalf("got %q", got)
	}
}

func TestAdvertisedCallbackUsesListenPort(t *testing.T) {
	got := AdvertisedCallback("", "0.0.0.0:9001", "dns01", "10.1.2.3")
	if got != "http://10.1.2.3:9001" {
		t.Fatalf("got %q", got)
	}
}

func TestAdvertisedCallbackFallsBackToHostname(t *testing.T) {
	got := AdvertisedCallback("", ":7444", "dns01", "")
	if got != "http://dns01:7444" {
		t.Fatalf("got %q", got)
	}
}
