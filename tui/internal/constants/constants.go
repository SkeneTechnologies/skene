package constants

import (
	"fmt"
	"os"
)

// Version and repository information
var (
	Version    = "dev"
	Repository = "github.com/SkeneTechnologies/skene"
)

// URLs
const (
	SkeneAuthURL        = "https://www.skene.ai/auth"
	SkeneTestAuthURL    = "http://localhost:3000/auth"
	UVDownloadBaseURL   = "https://github.com/astral-sh/uv/releases/latest/download"
	OllamaDefaultBase   = "http://localhost:11434/v1"
	LMStudioDefaultBase = "http://localhost:1234/v1"
)

// Skene provider defaults
const (
	SkeneDefaultModel = "auto"
)

// API key URLs for providers
const (
	OpenAIKeyURL    = "https://platform.openai.com/api-keys"
	AnthropicKeyURL = "https://platform.claude.com/settings/keys"
	GeminiKeyURL    = "https://aistudio.google.com/apikey"
	SkeneKeyURL     = "https://www.skene.ai/login"
)

// Package and directory names
const (
	GrowthPackageName    = "skene"
	GrowthPackageVersion = "0.3.1rc1"
	OutputDirName     = "skene-context"
	DefaultOutputDir  = "./skene-context"
	SkeneCacheDir     = ".skene"
	SkeneCacheBinDir  = "bin"
	ProjectConfigFile = ".skene.config"
	UserConfigDir     = ".config/skene"
	UserConfigFile    = "config"
)

// GrowthPackageSpec returns the package specifier for uvx.
// Override with SKENE_PACKAGE env var for local dev (e.g. "/path/to/skene").
func GrowthPackageSpec() string {
	if pkg := os.Getenv("SKENE_PACKAGE"); pkg != "" {
		return pkg
	}
	return fmt.Sprintf("%s==%s", GrowthPackageName, GrowthPackageVersion)
}

// Output file names
const (
	GrowthPlanFile           = "growth-plan.md"
	GrowthTemplateFile       = "growth-template.json"
	GrowthManifestFile       = "growth-manifest.json"
	ProductDocsFile          = "product-docs.md"
	ImplementationPromptFile = "implementation-prompt.md"
)

// Skene ecosystem package metadata
type PackageMeta struct {
	ID          string
	Name        string
	Description string
	URL         string
}

var SkenePackages = []PackageMeta{
	{
		ID:          "growth",
		Name:        "Skene",
		Description: "Tech stack detection, growth features, revenue leakage, growth plans (via uvx)",
		URL:         "github.com/SkeneTechnologies/skene",
	},
}
