package growth

import (
	"strings"
	"testing"

	"skene/internal/constants"
)

// Unit tests for output-dir plumbing. The uvx invocation itself requires a
// real subprocess, so these tests exercise the helpers that assemble the env
// vars and resolve the output directory — the two inputs that determine where
// the CLI writes artifacts.

func TestResolveOutputDirUsesAbsolutePathAsIs(t *testing.T) {
	e := &Engine{config: EngineConfig{
		ProjectDir: "/tmp/project",
		OutputDir:  "/absolute/custom",
	}}
	if got := e.resolveOutputDir(); got != "/absolute/custom" {
		t.Fatalf("expected absolute path passthrough, got %q", got)
	}
}

func TestResolveOutputDirJoinsRelativeWithProjectDir(t *testing.T) {
	e := &Engine{config: EngineConfig{
		ProjectDir: "/tmp/project",
		OutputDir:  "./custom",
	}}
	got := e.resolveOutputDir()
	if !strings.HasPrefix(got, "/tmp/project") || !strings.HasSuffix(got, "custom") {
		t.Fatalf("expected project-rooted path, got %q", got)
	}
}

func TestBuildEnvVarsIncludesSkeneOutputDir(t *testing.T) {
	e := &Engine{config: EngineConfig{
		ProjectDir: "/tmp/project",
		OutputDir:  "./skene-context",
	}}

	envs := e.buildEnvVars()
	var found string
	for _, kv := range envs {
		if strings.HasPrefix(kv, "SKENE_OUTPUT_DIR=") {
			found = strings.TrimPrefix(kv, "SKENE_OUTPUT_DIR=")
		}
	}
	if found == "" {
		t.Fatalf("SKENE_OUTPUT_DIR missing from env; got: %v", envs)
	}
	if !strings.HasSuffix(found, "skene-context") {
		t.Fatalf("SKENE_OUTPUT_DIR should target skene-context; got %q", found)
	}
}

func TestDefaultOutputDirConstant(t *testing.T) {
	if constants.DefaultOutputDir != "./skene-context" {
		t.Fatalf("DefaultOutputDir regressed; got %q", constants.DefaultOutputDir)
	}
	if constants.OutputDirName != "skene-context" {
		t.Fatalf("OutputDirName regressed; got %q", constants.OutputDirName)
	}
	if constants.LegacyOutputDirName != "skene" {
		t.Fatalf("LegacyOutputDirName regressed; got %q", constants.LegacyOutputDirName)
	}
}
