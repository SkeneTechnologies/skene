package growth

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"skene/internal/constants"
	"skene/internal/outputdirs"
	"skene/internal/services/uvresolver"
)

// AnalysisPhase represents a phase of the analysis
type AnalysisPhase int

const (
	PhaseScanCodebase AnalysisPhase = iota
	PhaseDetectFeatures
	PhaseGrowthLoops
	PhaseMonetisation
	PhaseOpportunities
	PhaseGenerateDocs
)

// String returns the human-readable name for the phase
func (p AnalysisPhase) String() string {
	switch p {
	case PhaseScanCodebase:
		return constants.PhaseScanningCodebase
	case PhaseDetectFeatures:
		return constants.PhaseDetectingFeatures
	case PhaseGrowthLoops:
		return constants.PhaseGrowthLoops
	case PhaseMonetisation:
		return constants.PhaseMonetisation
	case PhaseOpportunities:
		return constants.PhaseOpportunities
	case PhaseGenerateDocs:
		return constants.PhaseGeneratingDocs
	default:
		return constants.StatusInProgress
	}
}

// PhaseUpdate is sent during analysis to update progress
type PhaseUpdate struct {
	Phase    AnalysisPhase
	Progress float64
	Message  string
}

// AnalysisResult holds the complete analysis output
type AnalysisResult struct {
	GrowthPlan     string
	Manifest       string
	GrowthTemplate string
	Error          error
}

// EngineConfig holds the configuration passed to uvx commands
type EngineConfig struct {
	Provider       string
	Model          string
	APIKey         string
	BaseURL        string
	ProjectDir     string
	OutputDir      string
	UseGrowth      bool
	Upstream       string
	UpstreamAPIKey string
}

// Engine spawns uvx commands for the legacy growth commands (analyze, plan,
// build, validate, push). The journey analysis no longer runs through here —
// it goes over the skene server API (internal/services/backend).
type Engine struct {
	config   EngineConfig
	updateFn func(PhaseUpdate)
}

// NewEngine creates a new engine that delegates to uvx
func NewEngine(config EngineConfig, updateFn func(PhaseUpdate)) *Engine {
	return &Engine{
		config:   config,
		updateFn: updateFn,
	}
}

// Run executes the analysis by spawning uvx skene analyze
func (e *Engine) Run(ctx context.Context) *AnalysisResult {
	result := &AnalysisResult{}

	e.sendUpdate(PhaseScanCodebase, 0.0, "Starting analysis via uvx skene...")

	outputDir := e.resolveOutputDir()
	args := []string{
		constants.GrowthPackageSpec(), "analyze", ".",
		"--output", filepath.Join(outputDir, constants.GrowthManifestFile),
	}

	if err := e.runUVX(ctx, args); err != nil {
		result.Error = fmt.Errorf("analysis failed: %w", err)
		return result
	}

	e.sendUpdate(PhaseGenerateDocs, 1.0, "Analysis complete")

	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.GrowthPlanFile))
	result.Manifest = loadFileContent(filepath.Join(outputDir, constants.GrowthManifestFile))
	result.GrowthTemplate = loadFileContent(filepath.Join(outputDir, constants.GrowthTemplateFile))

	return result
}

// GeneratePlan spawns uvx skene plan
func (e *Engine) GeneratePlan() *AnalysisResult {
	result := &AnalysisResult{}

	outputDir := e.resolveOutputDir()
	args := []string{
		constants.GrowthPackageSpec(), "plan",
		"--context", outputDir,
		"--output", filepath.Join(outputDir, constants.GrowthPlanFile),
	}

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("plan generation failed: %w", err)
		return result
	}

	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.GrowthPlanFile))
	return result
}

// GenerateBuild spawns uvx skene build
func (e *Engine) GenerateBuild() *AnalysisResult {
	result := &AnalysisResult{}

	outputDir := e.resolveOutputDir()
	args := []string{
		constants.GrowthPackageSpec(), "build",
		"--context", outputDir,
	}

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("build generation failed: %w", err)
		return result
	}

	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.ImplementationPromptFile))
	return result
}

// Push spawns uvx skene push to deploy engine.yaml + trigger migration
// to the configured Skene Cloud workspace. Upstream URL, API token, and
// the configured output directory are propagated via the SKENE_UPSTREAM,
// SKENE_UPSTREAM_API_KEY, and SKENE_OUTPUT_DIR env vars set in
// buildEnvVars — skene push does not accept an --output / --context flag.
func (e *Engine) Push() *AnalysisResult {
	result := &AnalysisResult{}

	args := []string{constants.GrowthPackageSpec(), "push", "."}

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("push failed: %w", err)
		return result
	}

	return result
}

// ValidateManifest spawns uvx skene validate
func (e *Engine) ValidateManifest() *AnalysisResult {
	result := &AnalysisResult{}

	manifestPath := filepath.Join(e.contextOutputDir(), constants.GrowthManifestFile)
	args := []string{constants.GrowthPackageSpec(), "validate", manifestPath}

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("validation failed: %w", err)
		return result
	}

	return result
}

// runUVX spawns a uvx command in the project directory and streams its
// output line by line into progress updates. The legacy commands it runs
// are non-interactive; interactive flows live on the server now.
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
		e.sendUpdate(PhaseDetectFeatures, 0.5, line)
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

// contextOutputDir is the configured / legacy path for non-bundle outputs (manifest, plans, etc.).
func (e *Engine) contextOutputDir() string {
	rel := e.config.OutputDir
	if rel == "" {
		rel = constants.DefaultOutputDir
	}
	return outputdirs.Context(e.config.ProjectDir, rel)
}

// resolveOutputDir matches the Python CLI context directory for SKENE_OUTPUT_DIR / --context.
func (e *Engine) resolveOutputDir() string {
	return e.contextOutputDir()
}

func (e *Engine) sendUpdate(phase AnalysisPhase, progress float64, message string) {
	if e.updateFn != nil {
		e.updateFn(PhaseUpdate{
			Phase:    phase,
			Progress: progress,
			Message:  message,
		})
	}
}

func loadFileContent(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(data)
}
