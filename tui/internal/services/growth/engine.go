// Package growth spawns uvx for the one remaining Python CLI command the
// TUI still shells out to: skene push. Analysis no longer runs through
// here — it goes over the skene server API (internal/services/backend).
package growth

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"

	"skene/internal/constants"
	"skene/internal/outputdirs"
	"skene/internal/services/uvresolver"
)

// EngineConfig holds the configuration passed to uvx commands
type EngineConfig struct {
	Provider       string
	Model          string
	APIKey         string
	BaseURL        string
	ProjectDir     string
	OutputDir      string
	Upstream       string
	UpstreamAPIKey string
}

// Engine spawns uvx skene push to deploy an analysis bundle to Skene Cloud.
type Engine struct {
	config   EngineConfig
	onOutput func(line string)
}

// NewEngine creates a new engine that delegates to uvx. onOutput (optional)
// receives the spawned command's output line by line.
func NewEngine(config EngineConfig, onOutput func(line string)) *Engine {
	return &Engine{
		config:   config,
		onOutput: onOutput,
	}
}

// Push spawns uvx skene push to deploy engine.yaml + trigger migration
// to the configured Skene Cloud workspace. Upstream URL, API token, and
// the configured output directory are propagated via the SKENE_UPSTREAM,
// SKENE_UPSTREAM_API_KEY, and SKENE_OUTPUT_DIR env vars set in
// buildEnvVars — skene push does not accept an --output / --context flag.
func (e *Engine) Push() error {
	args := []string{constants.GrowthPackageSpec(), "push", "."}

	if err := e.runUVX(context.Background(), args); err != nil {
		return fmt.Errorf("push failed: %w", err)
	}

	return nil
}

// runUVX spawns a uvx command in the project directory and streams its
// output line by line into progress updates. The command it runs is
// non-interactive; interactive flows live on the server now.
func (e *Engine) runUVX(ctx context.Context, args []string) error {
	uvxPath, err := uvresolver.Resolve()
	if err != nil {
		return fmt.Errorf("failed to locate uvx: %w", err)
	}

	cmd := exec.CommandContext(ctx, uvxPath, args...)
	cmd.Dir = e.config.ProjectDir
	cmd.Env = append(os.Environ(), e.buildEnvVars()...)
	cmd.Stdin = nil

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start uvx: %w", err)
	}

	var lastLines []string
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimRight(scanner.Text(), "\r")
		e.emit(line)
		lastLines = append(lastLines, line)
		if len(lastLines) > 10 {
			lastLines = lastLines[1:]
		}
	}

	if err := cmd.Wait(); err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		tail := strings.Join(lastLines, "\n")
		if tail != "" {
			return fmt.Errorf("uvx command failed:\n%s", tail)
		}
		return fmt.Errorf("uvx command failed: %w", err)
	}
	return nil
}

func (e *Engine) buildEnvVars() []string {
	var envs []string
	if e.config.APIKey != "" {
		envs = append(envs, "SKENE_API_KEY="+e.config.APIKey)
	}
	if e.config.Provider != "" {
		envs = append(envs, "SKENE_PROVIDER="+e.config.Provider)
	}
	if e.config.Model != "" {
		envs = append(envs, "SKENE_MODEL="+e.config.Model)
	}
	if e.config.BaseURL != "" {
		envs = append(envs, "SKENE_BASE_URL="+e.config.BaseURL)
	}
	if e.config.Upstream != "" {
		envs = append(envs, "SKENE_UPSTREAM="+e.config.Upstream)
	}
	if e.config.UpstreamAPIKey != "" {
		envs = append(envs, "SKENE_UPSTREAM_API_KEY="+e.config.UpstreamAPIKey)
	}
	if outDir := e.resolveOutputDir(); outDir != "" {
		envs = append(envs, "SKENE_OUTPUT_DIR="+outDir)
	}
	return envs
}

// resolveOutputDir matches the Python CLI context directory for SKENE_OUTPUT_DIR.
func (e *Engine) resolveOutputDir() string {
	rel := e.config.OutputDir
	if rel == "" {
		rel = constants.DefaultOutputDir
	}
	return outputdirs.Context(e.config.ProjectDir, rel)
}

func (e *Engine) emit(line string) {
	if e.onOutput != nil {
		e.onOutput(line)
	}
}
