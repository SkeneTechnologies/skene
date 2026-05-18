package constants

import (
	"fmt"
	"os"
	"time"
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
	GrowthPackageVersion = "0.4.1rc1"
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
	JourneyFile              = "journey.yaml"
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
	{ID: "journey", DisplayName: "Journey", Filename: JourneyFile, Description: FileDescUserJourney, InContext: false},
	{ID: "engine", DisplayName: "Growth Features", Filename: EngineFile, Description: FileDescEngine, InContext: false},
	{ID: "schema", DisplayName: "Schema", Filename: SchemaFile, Description: FileDescSchema, InContext: false},
	{ID: "plan", DisplayName: "Growth Plan", Filename: GrowthPlanFile, Description: FileDescPlan, InContext: true},
}

// Telemetry — events are sent to a Supabase Edge Function.
//
// TelemetryProxyURL and TelemetryProxyAnonKey are injected at release build
// time via `-ldflags -X` from GitHub secrets (see tui/Makefile and
// .github/workflows/tui-release.yml). Forks and local source builds get
// empty defaults, which causes the telemetry client to silently drop all
// events.
var (
	TelemetryProxyURL     = ""
	TelemetryProxyAnonKey = ""
)

const (
	TelemetryQueueSize   = 64
	TelemetryHTTPTimeout = 5 * time.Second
)

// GetTelemetryProxyURL returns the proxy endpoint, honouring the
// SKENE_TELEMETRY_URL env override for dev/staging environments.
func GetTelemetryProxyURL() string {
	if v := os.Getenv("SKENE_TELEMETRY_URL"); v != "" {
		return v
	}
	return TelemetryProxyURL
}

// GetTelemetryProxyAnonKey returns the proxy anon key, honouring the
// SKENE_TELEMETRY_KEY env override for dev/staging environments.
func GetTelemetryProxyAnonKey() string {
	if v := os.Getenv("SKENE_TELEMETRY_KEY"); v != "" {
		return v
	}
	return TelemetryProxyAnonKey
}

// Telemetry event names
const (
	EventTUIOpened          = "tui_opened"
	EventProviderSelected   = "provider_selected"
	EventModelSelected      = "model_selected"
	EventProjectDirSelected = "project_dir_selected"
	EventAnalysisStarted    = "analysis_started"
	EventAnalysisCompleted  = "analysis_completed"
	EventAnalysisFailed     = "analysis_failed"
	EventNextStepTriggered  = "next_step_triggered"
	EventTelemetryToggled   = "telemetry_toggled"

	EventViewEntered            = "view_entered"
	EventConfigReused           = "config_reused"
	EventConfigReconfigured     = "config_reconfigured"
	EventAuthSucceeded          = "auth_succeeded"
	EventAuthFallbackUsed       = "auth_fallback_used"
	EventExistingAnalysisAction = "existing_analysis_action"
	EventVisualizerOpened       = "visualizer_opened"
	EventTUIExited              = "tui_exited"
	EventAnalysisCancelled      = "analysis_cancelled"
	EventAnalysisRetried        = "analysis_retried"

	EventDeploymentStarted   = "deployment_started"
	EventDeploymentCompleted = "deployment_completed"
	EventDeploymentFailed    = "deployment_failed"

	EventPlanStarted   = "plan_started"
	EventPlanCompleted = "plan_completed"
	EventPlanFailed    = "plan_failed"

	EventBuildStarted   = "build_started"
	EventBuildCompleted = "build_completed"
	EventBuildFailed    = "build_failed"

	EventValidateStarted   = "validate_started"
	EventValidateCompleted = "validate_completed"
	EventValidateFailed    = "validate_failed"

	EventNextStepCancelled = "next_step_cancelled"
	EventOutputDirOpened   = "output_dir_opened"
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
