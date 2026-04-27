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
	GrowthPackageVersion = "0.4.0rc2"
	OutputDirName     = "skene-context"
	DefaultOutputDir  = "./skene-context"
	LegacyOutputDirName = "skene"
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
	SchemaFile               = "schema.yaml"
	EngineFile               = "engine.yaml"
	UserJourneyFile          = "user-journey.yaml"
	NewFeaturesFile          = "new-features.yaml"
	CompiledStateMachineFile = "compiled/state-machine.yaml"
)

// DashboardFile describes a file shown on the results dashboard.
type DashboardFile struct {
	ID          string
	DisplayName string
	Filename    string
	Description string
	// InContext: when true, the file is resolved under the context/legacy output
	// directory (e.g. skene-context/); when false, under the canonical skene/ bundle.
	InContext bool
}

// DashboardFiles defines the output files shown on the results dashboard.
var DashboardFiles = []DashboardFile{
	{ID: "manifest", DisplayName: "Growth Manifest", Filename: GrowthManifestFile, Description: FileDescManifest, InContext: true},
	{ID: "template", DisplayName: "Growth Template", Filename: GrowthTemplateFile, Description: FileDescTemplate, InContext: true},
	{ID: "new-features", DisplayName: "Planned Features", Filename: NewFeaturesFile, Description: FileDescNewFeatures, InContext: true},
	{ID: "compiled", DisplayName: "State Machine", Filename: CompiledStateMachineFile, Description: FileDescCompiledYAML, InContext: false},
	{ID: "user-journey", DisplayName: "User Journey", Filename: UserJourneyFile, Description: FileDescUserJourney, InContext: false},
	{ID: "engine", DisplayName: "Growth Features", Filename: EngineFile, Description: FileDescEngine, InContext: false},
	{ID: "schema", DisplayName: "Schema", Filename: SchemaFile, Description: FileDescSchema, InContext: false},
	{ID: "plan", DisplayName: "Growth Plan", Filename: GrowthPlanFile, Description: FileDescPlan, InContext: true},
}

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
