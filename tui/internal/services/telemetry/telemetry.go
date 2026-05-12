package telemetry

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"skene/internal/constants"
)

// ═══════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════

// Client sends anonymous telemetry events to the Skene telemetry proxy
// (a Supabase Edge Function — see ../../../../telemetry-proxy/). All sends
// are non-blocking; events are queued and flushed by a background goroutine.
type Client struct {
	proxyURL     string
	anonKey      string
	distinctID   string
	sessionID    string
	queue        chan event
	wg           sync.WaitGroup
	httpClient   *http.Client
	enabled      bool
	sessionStart time.Time
	seq          atomic.Uint64
}

type event struct {
	Event      string            `json:"event"`
	Properties map[string]string `json:"properties"`
	Timestamp  string            `json:"timestamp"`
}

type capturePayload struct {
	Event      string            `json:"event"`
	DistinctID string            `json:"distinct_id"`
	Properties map[string]string `json:"properties"`
	Timestamp  string            `json:"timestamp"`
}

// ═══════════════════════════════════════════════════════════════════
// CONSTRUCTOR
// ═══════════════════════════════════════════════════════════════════

// NewClient creates a telemetry client. When enabled is false the
// client silently drops all events. The background sender starts
// immediately and is torn down by Close().
func NewClient(enabled bool) *Client {
	now := time.Now()
	c := &Client{
		proxyURL:     constants.GetTelemetryProxyURL(),
		anonKey:      constants.GetTelemetryProxyAnonKey(),
		distinctID:   anonymousID(),
		sessionID:    fmt.Sprintf("sess-%d", now.UnixNano()),
		queue:        make(chan event, constants.TelemetryQueueSize),
		httpClient:   &http.Client{Timeout: constants.TelemetryHTTPTimeout},
		enabled:      enabled,
		sessionStart: now,
	}

	c.wg.Add(1)
	go c.sender()
	return c
}

// ═══════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════

// Track enqueues an event. It never blocks; if the queue is full
// the event is silently dropped. Each event carries a monotonic
// sequence number and the session ID so the consumer can reconstruct
// the exact order events were fired, even when two events share the
// same wall-clock millisecond or PostHog reorders them on ingestion.
func (c *Client) Track(name string, props map[string]string) {
	if !c.enabled {
		return
	}

	seq := c.seq.Add(1)
	merged := mergeDefaults(props)
	merged["session_id"] = c.sessionID
	merged["event_seq"] = fmt.Sprintf("%d", seq)

	e := event{
		Event:      name,
		Properties: merged,
		Timestamp:  time.Now().UTC().Format(time.RFC3339Nano),
	}

	select {
	case c.queue <- e:
	default:
		// queue full — drop rather than block the TUI
	}
}

// SetEnabled toggles telemetry at runtime (e.g. when the user
// flips the opt-out switch).
func (c *Client) SetEnabled(on bool) {
	c.enabled = on
}

// IsEnabled reports whether telemetry is currently active.
func (c *Client) IsEnabled() bool {
	return c.enabled
}

// SessionDuration returns the elapsed time since the client was created,
// truncated to seconds, as a human-readable string.
func (c *Client) SessionDuration() string {
	return time.Since(c.sessionStart).Truncate(time.Second).String()
}

// Close drains the queue and waits for in-flight HTTP calls
// to finish (up to 2 s).
func (c *Client) Close() {
	close(c.queue)
	done := make(chan struct{})
	go func() {
		c.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
	}
}

// ═══════════════════════════════════════════════════════════════════
// BACKGROUND SENDER
// ═══════════════════════════════════════════════════════════════════

func (c *Client) sender() {
	defer c.wg.Done()
	for e := range c.queue {
		c.post(e)
	}
}

func (c *Client) post(e event) {
	// If the proxy URL or anon key haven't been configured (still the
	// placeholder values), silently drop the event rather than spam a
	// dead endpoint. This keeps local/dev builds clean.
	if c.proxyURL == "" || c.anonKey == "" {
		return
	}

	payload := capturePayload{
		Event:      e.Event,
		DistinctID: c.distinctID,
		Properties: e.Properties,
		Timestamp:  e.Timestamp,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return
	}

	req, err := http.NewRequest(http.MethodPost, c.proxyURL, bytes.NewReader(body))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	// Supabase Edge Function with verify_jwt disabled; the publishable
	// key is public and only used to route to the correct project.
	req.Header.Set("apikey", c.anonKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return
	}
	_ = resp.Body.Close()
}

// ═══════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════

// anonymousID generates a stable-ish anonymous ID per machine by
// hashing the hostname. No PII is included.
func anonymousID() string {
	host, err := os.Hostname()
	if err != nil {
		host = "unknown"
	}
	// Simple FNV-like hash to avoid importing crypto
	var h uint64 = 14695981039346656037
	for _, b := range []byte(host) {
		h ^= uint64(b)
		h *= 1099511628211
	}
	return fmt.Sprintf("anon-%x", h)
}

// mergeDefaults adds standard context properties to every event.
func mergeDefaults(props map[string]string) map[string]string {
	defaults := map[string]string{
		"app_version": constants.Version,
		"os":          runtime.GOOS,
		"arch":        runtime.GOARCH,
	}
	if props == nil {
		return defaults
	}
	for k, v := range defaults {
		if _, exists := props[k]; !exists {
			props[k] = v
		}
	}
	return props
}
