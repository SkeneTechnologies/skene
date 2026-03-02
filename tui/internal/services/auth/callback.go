package auth

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"sync"
	"time"
)

// CallbackResult holds the result received from the external auth flow
type CallbackResult struct {
	APIKey string `json:"api_key"`
	Model  string `json:"model,omitempty"`
	Error  string `json:"error,omitempty"`
}

// CallbackServer runs a temporary local HTTP server to receive the API key
// from the external authentication website via redirect.
type CallbackServer struct {
	port     int
	server   *http.Server
	resultCh chan CallbackResult
	mu       sync.Mutex
	done     bool
}

// NewCallbackServer creates a new callback server on a random available port.
func NewCallbackServer() (*CallbackServer, error) {
	// Find a free port
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("failed to find free port: %w", err)
	}
	port := listener.Addr().(*net.TCPAddr).Port
	listener.Close()

	cs := &CallbackServer{
		port:     port,
		resultCh: make(chan CallbackResult, 1),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/callback", cs.handleCallback)

	cs.server = &http.Server{
		Addr:    fmt.Sprintf("127.0.0.1:%d", port),
		Handler: mux,
	}

	return cs, nil
}

// Start begins listening for the callback. Non-blocking.
func (cs *CallbackServer) Start() error {
	listener, err := net.Listen("tcp", cs.server.Addr)
	if err != nil {
		return fmt.Errorf("failed to start callback server: %w", err)
	}

	go func() {
		if err := cs.server.Serve(listener); err != nil && err != http.ErrServerClosed {
			cs.resultCh <- CallbackResult{Error: fmt.Sprintf("server error: %v", err)}
		}
	}()

	return nil
}

// GetPort returns the port the server is listening on.
func (cs *CallbackServer) GetPort() int {
	return cs.port
}

// GetCallbackURL returns the full callback URL for the external service.
func (cs *CallbackServer) GetCallbackURL() string {
	return fmt.Sprintf("http://localhost:%d/callback", cs.port)
}

// WaitForResult blocks until a result is received or the context is cancelled.
func (cs *CallbackServer) WaitForResult(ctx context.Context) (*CallbackResult, error) {
	select {
	case result := <-cs.resultCh:
		return &result, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

// Shutdown gracefully shuts down the server.
func (cs *CallbackServer) Shutdown() {
	cs.mu.Lock()
	defer cs.mu.Unlock()

	if cs.done {
		return
	}
	cs.done = true

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	_ = cs.server.Shutdown(ctx)
}

// handleCallback processes the callback from the external auth website.
// Supports both GET (query params) and POST (JSON body).
func (cs *CallbackServer) handleCallback(w http.ResponseWriter, r *http.Request) {
	// Set CORS headers so the external website can call this endpoint
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var result CallbackResult

	switch r.Method {
	case "GET":
		// API key passed as query parameter
		result.APIKey = r.URL.Query().Get("api_key")
		result.Model = r.URL.Query().Get("model")
		result.Error = r.URL.Query().Get("error")

	case "POST":
		// API key passed as JSON body
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&result); err != nil {
			http.Error(w, "invalid request body", http.StatusBadRequest)
			return
		}

	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Validate we got something useful
	if result.APIKey == "" && result.Error == "" {
		http.Error(w, "missing api_key", http.StatusBadRequest)
		return
	}

	// Send the result
	cs.mu.Lock()
	if !cs.done {
		cs.resultCh <- result
	}
	cs.mu.Unlock()

	// Return a simple success response
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, "Authentication complete. You can close this window.")
}
