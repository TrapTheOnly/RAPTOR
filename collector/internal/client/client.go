package client

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Client struct {
	BaseURL string
	Token   string
	HTTP    *http.Client
}

type EnrollResult struct {
	AgentID     int    `json:"agent_id"`
	SourceID    int    `json:"source_id"`
	Token       string `json:"token"`
	Hostname    string `json:"hostname"`
	DisplayName string `json:"display_name"`
	Mode        string `json:"mode"`
}

type IngestResult struct {
	OK        bool   `json:"ok"`
	SourceID  int    `json:"source_id"`
	Stored    int    `json:"stored"`
	Projected int    `json:"projected"`
	BatchID   string `json:"batch_id"`
	Token     string `json:"token"`
}

func New(baseURL, token string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		Token:   token,
		HTTP: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
			},
		},
	}
}

func (c *Client) post(path string, body any, withToken bool) (map[string]any, error) {
	raw, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, c.BaseURL+path, bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if withToken && c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
		req.Header.Set("X-Collector-Token", c.Token)
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	payload, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	var parsed map[string]any
	_ = json.Unmarshal(payload, &parsed)
	if resp.StatusCode >= 400 {
		msg := strings.TrimSpace(string(payload))
		if parsed != nil {
			if errVal, ok := parsed["error"].(string); ok && errVal != "" {
				msg = errVal
			}
		}
		return parsed, fmt.Errorf("raptor %s: %s", resp.Status, msg)
	}
	if parsed == nil {
		parsed = map[string]any{}
	}
	if tok, ok := parsed["token"].(string); ok && tok != "" {
		c.Token = tok
	}
	return parsed, nil
}

func (c *Client) Enroll(token, hostname, name, mode, version, callbackURL string, intervalSeconds int) (*EnrollResult, error) {
	parsed, err := c.post("/collector/v1/enroll", map[string]any{
		"token":            token,
		"hostname":         hostname,
		"display_name":     name,
		"mode":             mode,
		"agent_version":    version,
		"callback_url":     callbackURL,
		"interval_seconds": intervalSeconds,
	}, false)
	if err != nil {
		return nil, err
	}
	result := &EnrollResult{}
	if v, ok := parsed["agent_id"].(float64); ok {
		result.AgentID = int(v)
	}
	if v, ok := parsed["source_id"].(float64); ok {
		result.SourceID = int(v)
	}
	result.Token, _ = parsed["token"].(string)
	result.Hostname, _ = parsed["hostname"].(string)
	result.DisplayName, _ = parsed["display_name"].(string)
	result.Mode, _ = parsed["mode"].(string)
	if result.Token != "" {
		c.Token = result.Token
	}
	return result, nil
}

func (c *Client) Heartbeat(body map[string]any) (map[string]any, error) {
	return c.post("/collector/v1/heartbeat", body, true)
}

func (c *Client) Ingest(body map[string]any) (*IngestResult, error) {
	parsed, err := c.post("/collector/v1/ingest", body, true)
	if err != nil {
		return nil, err
	}
	out := &IngestResult{OK: true}
	if v, ok := parsed["source_id"].(float64); ok {
		out.SourceID = int(v)
	}
	if v, ok := parsed["stored"].(float64); ok {
		out.Stored = int(v)
	}
	if v, ok := parsed["projected"].(float64); ok {
		out.Projected = int(v)
	}
	out.BatchID, _ = parsed["batch_id"].(string)
	out.Token, _ = parsed["token"].(string)
	return out, nil
}
