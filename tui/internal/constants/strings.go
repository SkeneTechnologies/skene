package constants

// Wizard step names
const (
	StepNameAIProvider       = "AI Provider"
	StepNameSelectModel      = "Select Model"
	StepNameAuthentication   = "Authentication"
	StepNameLocalModelSetup  = "Local Model Setup"
	StepNameProjectDir       = "Project Directory"
	StepNameProjectSetup     = "Project Setup"
	StepNameAnalysisConfig   = "Analysis Configuration"
	StepNameAnalyzing        = "Analysing Growth Opportunities"
	StepNameJourneyAnalysis  = "Analysing User Journey"
	StepNameCodebaseAnalysis = "Analysing Growth Opportunities"
	StepNameAnalysingStepper = "Analysing"
	StepNameResults          = "Analysis Results"
	StepNameNextSteps        = "Actions"
	StepCounterFormat        = "Step %d of %d"
)

// Dashboard view
const (
	DashboardTitle        = "Skene Analysis"
	DashboardSubtitle     = "Your codebase, analyzed."
	DashboardFilesHeader  = "Context files"
	DashboardFilesDesc    = "Persisted outputs from the last analysis run. Press n to see how to regenerate any file."
	DashboardMissingLabel = "Missing"
	DashboardBackLabel    = "Dashboard"
)

// Dashboard file descriptions
const (
	FileDescManifest     = "Detected tech stack, features, and growth opportunities."
	FileDescTemplate     = "Actionable growth strategies for your stack."
	FileDescPlan         = "Prioritized roadmap with implementation order."
	FileDescSchema       = "Live schema introspected from your codebase."
	FileDescEngine       = "User journey map and growth engine config."
	FileDescNewFeatures  = "Feature backlog generated from the latest run."
	FileDescCompiledYAML = "Edge function state machine for Supabase backend."
)

// File detail view
const (
	FileDetailUpdatedFormat = "Last updated: %s"
)

// Engine visualizer
const (
	VisualizerStarting = "Starting engine visualizer..."
	VisualizerURL      = "Engine visualizer running at %s"
	VisualizerStopping = "Stopping engine visualizer..."
)

// Next steps view
const (
	NextStepsSuccess = "Analysis complete! What would you like to do next?"
)

// Next step action definitions
type NextStepDef struct {
	ID           string
	Name         string
	Description  string
	Command      string
	RequiresFile string // Relative path inside outputDir; empty = always available.
	RequiresDir  bool   // When true, RequiresFile is ignored and the outputDir itself must exist.
}

var NextStepActions = []NextStepDef{
	{
		ID:          "journey",
		Name:        "Analyse User Journey",
		Description: "Schema-driven feature detection and journey planning",
		Command:     "uvx skene analyse-journey .",
	},
	{
		ID:          "rerun",
		Name:        "Analyse Growth Opportunities",
		Description: "Full growth analysis with tech stack, features, and monetisation",
		Command:     "uvx skene analyze .",
	},
	{
		ID:           "plan",
		Name:         "Generate Growth Plan",
		Description:  "Create a prioritized growth plan with implementation roadmap",
		Command:      "uvx skene plan",
		RequiresFile: GrowthManifestFile,
	},
	{
		ID:           "build",
		Name:         "Build Implementation Prompt",
		Description:  "Generate a ready-to-use prompt for Cursor, Claude, or other AI tools",
		Command:      "uvx skene build",
		RequiresFile: GrowthManifestFile,
	},
	{
		ID:           "validate",
		Name:         "Validate Manifest",
		Description:  "Validate the growth manifest against the schema",
		Command:      "uvx skene validate",
		RequiresFile: GrowthManifestFile,
	},
	{
		ID:          "view-files",
		Name:        "View Files",
		Description: "Browse analysis output files in the dashboard",
		RequiresDir: true,
	},
	{
		ID:          "open",
		Name:        "Open File Directory",
		Description: "Open the skene-context folder in your file manager",
		RequiresDir: true,
	},
	{
		ID:          "config",
		Name:        "Change Configuration",
		Description: "Modify provider, model, or project settings",
	},
	{
		ID:          "exit",
		Name:        "Quit Skene",
		Description: "Close Skene",
	},
}

// Welcome view
const (
	WelcomeSubtitle = "Product-Led Growth analysis for your codebase"
	WelcomeCTA      = "> ENTER <"
)

// Update notice (welcome view)
const (
	UpdateNoticeFormat   = "Update available: %s (current: %s)"
	UpdateNoticeHintCopy = "Press c to copy update command"
	UpdateNoticeCopied   = "Copied to clipboard!"
)

// Auth view
const (
	AuthOpeningBrowser  = "Opening browser for Skene authentication"
	AuthRedirectingIn   = "Redirecting in %ds..."
	AuthWaiting         = "Waiting for authentication..."
	AuthWaitingSub      = "Complete the login in your browser"
	AuthVerifying       = "Verifying credentials..."
	AuthVerifyingSub    = "Setting up your account"
	AuthSuccess         = "Authentication successful!"
	AuthFallbackMessage = "Browser auth cancelled."
	AuthFallbackSub     = "You can enter your Skene API key manually."
	AuthFallbackHint    = "Press Enter to continue to manual entry"
)

// API key view
const (
	APIKeyHeader          = "Enter API Credentials"
	APIKeyValidating      = "Validating API key..."
	APIKeyValidated       = "API key validated"
	APIKeyTooShort        = "API key is too short"
	APIKeyBaseURLRequired = "Base URL is required for generic providers"
)

// Provider-specific validation messages
const (
	OpenAIKeyFormat    = "OpenAI keys start with 'sk-' and are at least 20 characters"
	AnthropicKeyFormat = "Invalid Anthropic API key format"
)

// Project directory view
const (
	ProjectDirHeader         = "Select project to analyze"
	ProjectDirSubtitle       = "Enter the path to your project's root directory"
	ProjectDirNotFound       = "Directory not found"
	ProjectDirNotADir        = "Path is not a directory"
	ProjectDirNoProject      = "No recognizable project structure detected. Analysis may be limited."
	ProjectDirValid          = "Valid project directory"
	ProjectDirValidExisting  = "Valid project directory (existing analysis found)"
	ProjectDirExistingHeader = "Existing Analysis Detected"
	ProjectDirExistingMsg    = "A previous Skene Growth analysis was found in this project."
	ProjectDirExistingQ      = "What would you like to do?"
	ProjectDirViewAnalysis   = "View Journey"
	ProjectDirRerunAnalysis  = "Re-run Analysis"
	ProjectDirRunAnalysis    = "Analyse Journey"
)

// Analysis config view
const (
	AnalysisConfigSummary   = "Analysis Summary"
	AnalysisConfigRunButton = "Run Analysis"

	AnalysisModeSimple       = "Simple Analysis"
	AnalysisModeSimpleDesc   = "Schema-driven feature detection and journey planning"
	AnalysisModeAdvanced     = "Advanced Analysis"
	AnalysisModeAdvancedDesc = "Full growth analysis with tech stack, features, and monetisation"
)

// Status labels (used across analyzing view, game, etc.)
const (
	StatusFailed     = "Failed"
	StatusCompleted  = "Completed"
	StatusInProgress = "In progress"
	StatusDone       = "Done"

	StatusIconFailed    = "✗"
	StatusIconCompleted = "✓"
)

// Game strings
const (
	GameTitle          = "TIME TO"
	GameOver           = "GAME OVER"
	GameAutoFire       = "auto-fire is on"
	GameThrustUp       = "thrust up"
	GameThrustDown     = "thrust down"
	GameStatDistance   = "Distance "
	GameStatDefeated   = "Defeated "
	GameStatFinalScore = "Score    "
	GameHUDFormat      = " SCORE: %d  HP: %s  DIST: %d "
)

// Engine phase names
const (
	PhaseScanningCodebase  = "Scanning codebase"
	PhaseDetectingFeatures = "Detecting product features"
	PhaseGrowthLoops       = "Growth loop analysis"
	PhaseMonetisation      = "Monetisation analysis"
	PhaseOpportunities     = "Opportunity modelling"
	PhaseGeneratingDocs    = "Generating manifests & docs"
)

// Analysis phase names are now defined in internal/services/growth/engine.go
// as methods on the AnalysisPhase enum type

// Error view
const (
	ErrorAnalysisFailed = "ANALYSIS_FAILED"
	ErrorAnalysisTitle  = "Analysis Failed"
)

// Button labels
const (
	ButtonContinue   = "Continue"
	ButtonQuit       = "Quit"
	ButtonUseCurrent = "Use Current"
	ButtonBrowse     = "Browse"
	ButtonSelectDir  = "Select This Directory"
	ButtonCancel     = "Cancel"
)

// Local model view
const (
	LocalModelSelectHeader = "Select a local model"
	LocalModelRetryHint    = "Press 'r' to retry detection or 'esc' to go back"
)

// Help key labels
const (
	HelpKeyUpDown    = "↑/↓"
	HelpKeyLeftRight = "←/→"
	HelpKeyEnter     = "enter"
	HelpKeyEsc       = "esc"
	HelpKeyTab       = "tab"
	HelpKeySpace     = "space"
	HelpKeyCtrlC     = "ctrl+c"
	HelpKeyHelp      = "?"
	HelpKeyN         = "n"
	HelpKeyG         = "g"
	HelpKeyM         = "m"
	HelpKeyR         = "r"
	HelpKeyC         = "c"
)

// Help descriptions
const (
	HelpDescNavigate       = "navigate"
	HelpDescSelect         = "select"
	HelpDescSelectOption   = "select option"
	HelpDescSelectProvider = "select provider"
	HelpDescSelectModel    = "select model"

	HelpDescConfirm          = "confirm"
	HelpDescConfirmSelection = "confirm selection"
	HelpDescSubmit           = "submit"
	HelpDescContinue         = "continue"
	HelpDescStart            = "start"
	HelpDescStartAnalysis    = "start analysis"
	HelpDescGoBack           = "go back"
	HelpDescBack             = "back"
	HelpDescBackToResults    = "back to results"
	HelpDescCancel           = "cancel"
	HelpDescCancelGoBack     = "cancel and go back"
	HelpDescQuit             = "quit"
	HelpDescScroll           = "scroll"
	HelpDescSwitchTabs       = "switch tabs"
	HelpDescFocusContent     = "focus content"
	HelpDescFocusTabs        = "focus tabs"
	HelpDescFocus            = "focus"
	HelpDescSwitchFocus      = "switch focus"
	HelpDescSwitchField      = "switch field"
	HelpDescToggleHelp       = "toggle help"
	HelpDescHelp             = "help"
	HelpDescNextSteps        = "next steps"
	HelpDescPlayMiniGame     = "Kill some time"
	HelpDescPlayGame         = "Kill some time"
	HelpDescRetry            = "retry"
	HelpDescRetryDetection   = "retry detection"
	HelpDescManualEntry      = "manual entry"
	HelpDescSkipManualEntry  = "skip to manual entry"
	HelpDescContinueManual   = "continue to manual entry"
	HelpDescBackToProvider   = "go back to provider selection"
	HelpDescToggleOption     = "toggle option"
	HelpDescOpenFolder       = "open folder"
	HelpDescTabs             = "tabs"
	HelpDescCopyUpdateCmd    = "copy update cmd"
	HelpDescMove             = "move"
	HelpDescPlayAgain        = "Kill some more time"
	HelpDescStartGame        = "start"
)
