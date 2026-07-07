// Package backend owns the TUI's connection to the skene server: it spawns
// `uvx skene serve` (or attaches to an already-running server), drives the
// generated API client, and translates the SSE event stream into the
// structured progress the TUI renders. It replaces the old uvx
// stdout-scraping engine for the journey flow.
package backend

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"skene/internal/api"
	"skene/internal/constants"
	"skene/internal/services/uvresolver"
)

// Config carries the LLM configuration the spawned server needs. Mirrors
// what the old engine exported as SKENE_* env vars for uvx runs.
type Config struct {
	Provider string
	Model    string
	APIKey   string
	BaseURL  string
}

// Server is a running skene backend the TUI can talk to. Either owned (we
// spawned `uvx skene serve` and must kill it) or attached (SKENE_SERVER_URL
// pointed at an external server).
type Server struct {
	BaseURL string

	client *api.Client
	// http is the SSE-capable client: no overall timeout, streams stay open.
	http *http.Client
	cmd  *exec.Cmd
	tail *outputTail
	done chan error // closed with cmd.Wait result when the owned process exits
}

// startupTimeout allows for a cold uvx cache: the first spawn resolves and
// installs the skene package before the server can bind.
const startupTimeout = 120 * time.Second

// Connect returns a usable server: it attaches to SKENE_SERVER_URL when set,
// otherwise spawns `uvx skene serve` on a free local port and waits for
// /health. onStatus (optional) receives human-readable startup progress.
func Connect(ctx context.Context, cfg Config, onStatus func(string)) (*Server, error) {
	status := func(line string) {
		if onStatus != nil {
			onStatus(line)
		}
	}

	if url := os.Getenv("SKENE_SERVER_URL"); url != "" {
		status("Connecting to skene server at " + url + "...")
		s, err := attach(ctx, strings.TrimRight(url, "/"))
		if err != nil {
			return nil, fmt.Errorf("cannot reach skene server at %s: %w", url, err)
		}
		return s, nil
	}
	return spawn(ctx, cfg, status)
}

func newServer(baseURL string) (*Server, error) {
	httpClient := &http.Client{} // no Timeout: the /event stream is long-lived
	client, err := api.NewClient(baseURL, api.WithHTTPClient(httpClient), withAuthToken())
	if err != nil {
		return nil, err
	}
	return &Server{BaseURL: baseURL, client: client, http: httpClient}, nil
}

// withAuthToken adds the SKENE_SERVER_TOKEN bearer header when set (needed
// for attached servers on non-local binds; spawned servers are tokenless).
func withAuthToken() api.ClientOption {
	token := os.Getenv("SKENE_SERVER_TOKEN")
	return api.WithRequestEditorFn(func(_ context.Context, req *http.Request) error {
		if token != "" {
			req.Header.Set("Authorization", "Bearer "+token)
		}
		return nil
	})
}

func attach(ctx context.Context, baseURL string) (*Server, error) {
	s, err := newServer(baseURL)
	if err != nil {
		return nil, err
	}
	if err := s.checkHealth(ctx); err != nil {
		return nil, err
	}
	return s, nil
}

func spawn(ctx context.Context, cfg Config, status func(string)) (*Server, error) {
	uvxPath, err := uvresolver.Resolve()
	if err != nil {
		return nil, fmt.Errorf("failed to locate uvx: %w", err)
	}

	port, err := freePort()
	if err != nil {
		return nil, fmt.Errorf("no free port for skene server: %w", err)
	}

	status("Starting skene server...")

	args := []string{constants.GrowthPackageSpec(), "serve", "--port", fmt.Sprintf("%d", port)}
	cmd := exec.Command(uvxPath, args...)
	cmd.Env = append(os.Environ(), cfg.envVars()...)
	tail := newOutputTail(30)
	cmd.Stdout = tail
	cmd.Stderr = tail

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start skene server: %w", err)
	}

	s, err := newServer(fmt.Sprintf("http://127.0.0.1:%d", port))
	if err != nil {
		_ = cmd.Process.Kill()
		return nil, err
	}
	s.cmd = cmd
	s.tail = tail
	s.done = make(chan error, 1)
	go func() { s.done <- cmd.Wait() }()

	if err := s.waitHealthy(ctx); err != nil {
		s.Stop()
		return nil, err
	}
	return s, nil
}

func (c Config) envVars() []string {
	var envs []string
	if c.APIKey != "" {
		envs = append(envs, "SKENE_API_KEY="+c.APIKey)
	}
	if c.Provider != "" {
		envs = append(envs, "SKENE_PROVIDER="+c.Provider)
	}
	if c.Model != "" {
		envs = append(envs, "SKENE_MODEL="+c.Model)
	}
	if c.BaseURL != "" {
		envs = append(envs, "SKENE_BASE_URL="+c.BaseURL)
	}
	return envs
}

func (s *Server) checkHealth(ctx context.Context) error {
	reqCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	resp, err := s.client.HealthHealthGet(reqCtx)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned HTTP %d", resp.StatusCode)
	}
	return nil
}

func (s *Server) waitHealthy(ctx context.Context) error {
	deadline := time.NewTimer(startupTimeout)
	defer deadline.Stop()
	tick := time.NewTicker(250 * time.Millisecond)
	defer tick.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case err := <-s.done:
			// Put the exit result back for Stop().
			s.done <- err
			return fmt.Errorf("skene server exited during startup:\n%s", s.tail.String())
		case <-deadline.C:
			return fmt.Errorf("skene server did not become healthy within %s:\n%s", startupTimeout, s.tail.String())
		case <-tick.C:
			if err := s.checkHealth(ctx); err == nil {
				return nil
			}
		}
	}
}

// Stop terminates an owned server process; attached servers are untouched.
func (s *Server) Stop() {
	if s.cmd == nil || s.cmd.Process == nil {
		return
	}
	_ = s.cmd.Process.Signal(os.Interrupt)
	select {
	case <-s.done:
	case <-time.After(3 * time.Second):
		_ = s.cmd.Process.Kill()
		<-s.done
	}
	s.cmd = nil
}

func freePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	port := l.Addr().(*net.TCPAddr).Port
	_ = l.Close()
	return port, nil
}

// outputTail keeps the last n lines of the child's combined output for error
// reporting; the TUI no longer parses this stream for anything else.
type outputTail struct {
	mu      sync.Mutex
	lines   []string
	partial strings.Builder
	max     int
}

func newOutputTail(max int) *outputTail {
	return &outputTail{max: max}
}

func (t *outputTail) Write(p []byte) (int, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	for _, b := range p {
		if b == '\n' {
			t.lines = append(t.lines, t.partial.String())
			if len(t.lines) > t.max {
				t.lines = t.lines[1:]
			}
			t.partial.Reset()
			continue
		}
		t.partial.WriteByte(b)
	}
	return len(p), nil
}

func (t *outputTail) String() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := strings.Join(t.lines, "\n")
	if t.partial.Len() > 0 {
		if out != "" {
			out += "\n"
		}
		out += t.partial.String()
	}
	return out
}
