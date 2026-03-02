package constants

// Version and repository information
var (
	Version    = "v0.3.0"
	Repository = "github.com/SkeneTechnologies/skene-cli"
)

// URLs
const (
	SkeneAuthURL       = "https://skene-cli-demo.vercel.app/auth"
	UVDownloadBaseURL  = "https://github.com/astral-sh/uv/releases/latest/download"
	OllamaDefaultBase  = "http://localhost:11434/v1"
	LMStudioDefaultBase = "http://localhost:1234/v1"
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
	GrowthPackageName  = "skene-growth"
	OutputDirName      = "skene-context"
	DefaultOutputDir   = "./skene-context"
	SkeneCacheDir      = ".skene"
	SkeneCacheBinDir   = "bin"
	ProjectConfigFile  = ".skene.config"
	UserConfigDir      = ".config/skene"
	UserConfigFile     = "config"
)

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
		Name:        "Skene Growth",
		Description: "Tech stack detection, growth features, revenue leakage, growth plans (via uvx)",
		URL:         "github.com/SkeneTechnologies/skene-growth",
	},
}
