package growth

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"skene/internal/constants"
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
		return "Scanning codebase"
	case PhaseDetectFeatures:
		return "Detecting product features"
	case PhaseGrowthLoops:
		return "Growth loop analysis"
	case PhaseMonetisation:
		return "Monetisation analysis"
	case PhaseOpportunities:
		return "Opportunity modelling"
	case PhaseGenerateDocs:
		return "Generating manifests & docs"
	default:
		return "Analyzing..."
	}
}

// PhaseUpdate is sent during analysis to update progress
type PhaseUpdate struct {
	Phase    AnalysisPhase
	Progress float64
	Message  string
}

// InteractivePrompt represents a prompt from uvx that requires user input
type InteractivePrompt struct {
	Question string
	Options  []string
	Response chan string
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
	Provider   string
	Model      string
	APIKey     string
	BaseURL    string
	ProjectDir string
	OutputDir  string
	UseGrowth bool
}

// Engine spawns uvx commands to run Skene libraries in the selected repository
type Engine struct {
	config   EngineConfig
	updateFn func(PhaseUpdate)
	promptFn func(InteractivePrompt)
}

// NewEngine creates a new engine that delegates to uvx
func NewEngine(config EngineConfig, updateFn func(PhaseUpdate)) *Engine {
	return &Engine{
		config:   config,
		updateFn: updateFn,
	}
}

// SetPromptHandler sets the callback for interactive prompts from uvx
func (e *Engine) SetPromptHandler(fn func(InteractivePrompt)) {
	e.promptFn = fn
}

// Run executes the analysis by spawning uvx skene-growth analyze
func (e *Engine) Run(ctx context.Context) *AnalysisResult {
	result := &AnalysisResult{}

	e.sendUpdate(PhaseScanCodebase, 0.0, "Starting analysis via uvx skene-growth...")

	args := []string{constants.GrowthPackageName, "analyze", "."}
	args = append(args, e.buildCommonFlags()...)

	if err := e.runUVX(ctx, args); err != nil {
		result.Error = fmt.Errorf("analysis failed: %w", err)
		return result
	}

	e.sendUpdate(PhaseGenerateDocs, 1.0, "Analysis complete")

	outputDir := e.resolveOutputDir()
	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.GrowthPlanFile))
	result.Manifest = loadFileContent(filepath.Join(outputDir, constants.GrowthManifestFile))
	result.GrowthTemplate = loadFileContent(filepath.Join(outputDir, constants.GrowthTemplateFile))

	return result
}

// GeneratePlan spawns uvx skene-growth plan
func (e *Engine) GeneratePlan() *AnalysisResult {
	result := &AnalysisResult{}

	args := []string{constants.GrowthPackageName, "plan"}
	args = append(args, e.buildCommonFlags()...)

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("plan generation failed: %w", err)
		return result
	}

	outputDir := e.resolveOutputDir()
	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.GrowthPlanFile))
	return result
}

// GenerateBuild spawns uvx skene-growth build
func (e *Engine) GenerateBuild() *AnalysisResult {
	result := &AnalysisResult{}

	args := []string{constants.GrowthPackageName, "build"}
	args = append(args, e.buildCommonFlags()...)

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("build generation failed: %w", err)
		return result
	}

	outputDir := e.resolveOutputDir()
	result.GrowthPlan = loadFileContent(filepath.Join(outputDir, constants.ImplementationPromptFile))
	return result
}

// ValidateManifest spawns uvx skene-growth validate
func (e *Engine) ValidateManifest() *AnalysisResult {
	result := &AnalysisResult{}

	manifestPath := filepath.Join(e.resolveOutputDir(), constants.GrowthManifestFile)
	args := []string{constants.GrowthPackageName, "validate", manifestPath}

	if err := e.runUVX(context.Background(), args); err != nil {
		result.Error = fmt.Errorf("validation failed: %w", err)
		return result
	}

	return result
}

// runUVX spawns a uvx command in the project directory and streams output.
// It auto-provisions uv if not already installed.
//
// Uses chunk-based I/O so interactive prompts (no trailing newline) are
// detected via a stall timer rather than waiting for a line delimiter.
func (e *Engine) runUVX(ctx context.Context, args []string) error {
	uvxPath, err := uvresolver.Resolve()
	if err != nil {
		return fmt.Errorf("failed to locate uvx: %w", err)
	}

	cmd := exec.CommandContext(ctx, uvxPath, args...)
	cmd.Dir = e.config.ProjectDir
	cmd.Env = append(os.Environ(), e.buildEnvVars()...)

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdin pipe: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start uvx: %w", err)
	}

	type readResult struct {
		line    string
		isEOF   bool
	}

	readCh := make(chan readResult, 64)

	go func() {
		defer func() { readCh <- readResult{isEOF: true} }()
		buf := make([]byte, 4096)
		var partial bytes.Buffer
		for {
			n, readErr := stdout.Read(buf)
			if n > 0 {
				partial.Write(buf[:n])
				for {
					idx := bytes.IndexByte(partial.Bytes(), '\n')
					if idx < 0 {
						break
					}
					line := strings.TrimRight(string(partial.Bytes()[:idx]), "\r")
					rest := make([]byte, partial.Len()-idx-1)
					copy(rest, partial.Bytes()[idx+1:])
					partial.Reset()
					partial.Write(rest)
					readCh <- readResult{line: line}
				}
			}
			if readErr != nil {
				if partial.Len() > 0 {
					readCh <- readResult{line: strings.TrimRight(partial.String(), "\r")}
				}
				return
			}
		}
	}()

	var lastLines []string
	appendLast := func(line string) {
		lastLines = append(lastLines, line)
		if len(lastLines) > 10 {
			lastLines = lastLines[1:]
		}
	}

	var pendingOptions []string
	var pendingQuestion string
	collectingOptions := false

	firePrompt := func() {
		if len(pendingOptions) == 0 || e.promptFn == nil {
			return
		}
		responseCh := make(chan string, 1)
		e.promptFn(InteractivePrompt{
			Question: pendingQuestion,
			Options:  pendingOptions,
			Response: responseCh,
		})
		select {
		case answer := <-responseCh:
			fmt.Fprintln(stdin, answer)
		case <-ctx.Done():
			stdin.Close()
		}
		collectingOptions = false
		pendingOptions = nil
		pendingQuestion = ""
	}

	processLine := func(line string) {
		trimmed := strings.TrimSpace(line)

		if collectingOptions {
			if opt := parseOptionLine(trimmed); opt != "" {
				pendingOptions = append(pendingOptions, opt)
				return
			}
			if isSelectLine(trimmed) && len(pendingOptions) > 0 {
				firePrompt()
				return
			}
			// Non-option, non-select line while collecting: fire what we have
			if len(pendingOptions) > 0 {
				firePrompt()
			} else {
				collectingOptions = false
			}
		}

		if isPromptQuestion(trimmed) {
			collectingOptions = true
			pendingQuestion = trimmed
			pendingOptions = nil
			e.sendUpdate(PhaseDetectFeatures, 0.5, line)
			appendLast(line)
			return
		}

		e.sendUpdate(PhaseDetectFeatures, 0.5, line)
		appendLast(line)
	}

	stallTimeout := 800 * time.Millisecond

	for {
		var timer *time.Timer
		if collectingOptions && len(pendingOptions) > 0 {
			timer = time.NewTimer(stallTimeout)
		}

		if timer != nil {
			select {
			case r := <-readCh:
				timer.Stop()
				if r.isEOF {
					if collectingOptions && len(pendingOptions) > 0 {
						firePrompt()
					}
					goto done
				}
				processLine(r.line)
			case <-timer.C:
				firePrompt()
			case <-ctx.Done():
				timer.Stop()
				stdin.Close()
				goto done
			}
		} else {
			select {
			case r := <-readCh:
				if r.isEOF {
					goto done
				}
				processLine(r.line)
			case <-ctx.Done():
				stdin.Close()
				goto done
			}
		}
	}

done:
	if err := cmd.Wait(); err != nil {
		tail := strings.Join(lastLines, "\n")
		if tail != "" {
			return fmt.Errorf("uvx command failed:\n%s", tail)
		}
		return fmt.Errorf("uvx command failed: %w", err)
	}
	return nil
}

func isPromptQuestion(line string) bool {
	lower := strings.ToLower(line)
	if strings.Contains(lower, "where do you want") ||
		strings.Contains(lower, "select an option") {
		return true
	}
	if strings.HasSuffix(lower, "?") &&
		!strings.HasPrefix(lower, "#") &&
		len(lower) < 120 {
		return true
	}
	return false
}

func parseOptionLine(line string) string {
	trimmed := strings.TrimSpace(line)
	if len(trimmed) < 3 {
		return ""
	}
	if trimmed[0] >= '1' && trimmed[0] <= '9' {
		rest := trimmed[1:]
		if strings.HasPrefix(rest, ".") || strings.HasPrefix(rest, ")") {
			return strings.TrimSpace(rest[1:])
		}
	}
	return ""
}

func isSelectLine(line string) bool {
	lower := strings.ToLower(line)
	return strings.Contains(lower, "select option") ||
		strings.Contains(lower, "[1/") ||
		strings.Contains(lower, "(1)") ||
		strings.Contains(lower, "enter your choice")
}

func (e *Engine) buildCommonFlags() []string {
	var flags []string
	if e.config.Provider != "" {
		flags = append(flags, "--provider", e.config.Provider)
	}
	if e.config.Model != "" {
		flags = append(flags, "--model", e.config.Model)
	}
	if e.config.APIKey != "" {
		flags = append(flags, "--api-key", e.config.APIKey)
	}
	if e.config.BaseURL != "" {
		flags = append(flags, "--base-url", e.config.BaseURL)
	}
	return flags
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
	return envs
}

func (e *Engine) resolveOutputDir() string {
	if e.config.OutputDir != "" {
		if filepath.IsAbs(e.config.OutputDir) {
			return e.config.OutputDir
		}
		return filepath.Join(e.config.ProjectDir, e.config.OutputDir)
	}
	return filepath.Join(e.config.ProjectDir, constants.OutputDirName)
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
