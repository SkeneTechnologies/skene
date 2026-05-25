package visualizer

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

//go:embed webapp/index.html webapp/skene-logo.svg
var webappFS embed.FS

// Server hosts a YAML visualizer on localhost.
type Server struct {
	httpServer *http.Server
	port       int
	filePath   string
	title      string
}

// NewServer creates a visualizer server for the given YAML file.
func NewServer(filePath, title string) *Server {
	return &Server{
		filePath: filePath,
		title:    title,
	}
}

// Start begins serving on a random available port.
func (s *Server) Start() (string, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", fmt.Errorf("failed to find available port: %w", err)
	}
	s.port = listener.Addr().(*net.TCPAddr).Port

	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/api/data", s.handleData)
	mux.HandleFunc("/skene-logo.svg", s.handleLogo)

	s.httpServer = &http.Server{
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		_ = s.httpServer.Serve(listener)
	}()

	return fmt.Sprintf("http://localhost:%d", s.port), nil
}

// Stop shuts down the server.
func (s *Server) Stop() {
	if s.httpServer != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_ = s.httpServer.Shutdown(ctx)
	}
}

// Port returns the port the server is listening on.
func (s *Server) Port() int {
	return s.port
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	data, err := webappFS.ReadFile("webapp/index.html")
	if err != nil {
		http.Error(w, "webapp not found", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write(data)
}

func (s *Server) handleLogo(w http.ResponseWriter, r *http.Request) {
	data, err := webappFS.ReadFile("webapp/skene-logo.svg")
	if err != nil {
		http.Error(w, "logo not found", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "image/svg+xml")
	w.Header().Set("Cache-Control", "public, max-age=3600")
	_, _ = w.Write(data)
}

func (s *Server) handleData(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Content-Type", "application/json")

	raw, err := os.ReadFile(s.filePath)
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "file not found"})
		return
	}

	var yamlData interface{}
	if err := yaml.Unmarshal(raw, &yamlData); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "failed to parse YAML"})
		return
	}

	response := map[string]interface{}{
		"title": s.title,
		"data":  convertYAMLToJSON(yamlData),
	}
	_ = json.NewEncoder(w).Encode(response)
}

func convertYAMLToJSON(v interface{}) interface{} {
	switch val := v.(type) {
	case map[string]interface{}:
		result := make(map[string]interface{})
		for k, v := range val {
			result[k] = convertYAMLToJSON(v)
		}
		return result
	case map[interface{}]interface{}:
		result := make(map[string]interface{})
		for k, v := range val {
			result[fmt.Sprintf("%v", k)] = convertYAMLToJSON(v)
		}
		return result
	case []interface{}:
		result := make([]interface{}, len(val))
		for i, v := range val {
			result[i] = convertYAMLToJSON(v)
		}
		return result
	default:
		return v
	}
}
