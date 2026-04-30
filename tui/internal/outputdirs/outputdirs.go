// Package outputdirs centralises how the TUI and growth engine pick bundle vs
// context output directories. Canonical product artifacts (schema.yaml, engine.yaml)
// always go under the skene/ bundle. Ancillary/legacy files (e.g. growth manifest)
// follow output_dir, falling back to skene-context/ when the default skene/ bundle
// is missing but the legacy tree exists.
package outputdirs

import (
	"os"
	"path/filepath"
	"skene/internal/constants"
)

// Bundle returns the canonical <projectDir>/skene path for engine.yaml and schema.yaml.
func Bundle(projectDir string) string {
	if projectDir == "" {
		return constants.OutputDirName
	}
	return filepath.Join(projectDir, constants.OutputDirName)
}

// Context resolves the directory used for non-bundle artifacts (e.g. growth manifest,
// new-features, classic analyze outputs). projectDir is the project root. configOutput
// is the configured output path from .skene.config, typically "./skene" or
// a relative path, or an absolute path.
func Context(projectDir, configOutput string) string {
	if projectDir == "" {
		if wd, err := os.Getwd(); err == nil {
			projectDir = wd
		} else {
			projectDir = "."
		}
	}
	if configOutput == "" {
		configOutput = constants.DefaultOutputDir
	}
	if filepath.IsAbs(configOutput) {
		return filepath.Clean(configOutput)
	}
	primary := filepath.Join(projectDir, configOutput)
	if info, err := os.Stat(primary); err == nil && info.IsDir() {
		return primary
	}
	// Defaulting to skene/ but the tree only has legacy skene-context/:
	if isDefaultSkeneOutput(configOutput) {
		leg := filepath.Join(projectDir, constants.LegacyOutputDirName)
		if info, err := os.Stat(leg); err == nil && info.IsDir() {
			return leg
		}
	}
	return primary
}

func isDefaultSkeneOutput(configOutput string) bool {
	if configOutput == constants.DefaultOutputDir {
		return true
	}
	return filepath.Clean(configOutput) == constants.OutputDirName
}
