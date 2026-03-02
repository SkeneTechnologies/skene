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
	StepNameAnalyzing        = "Running Skene Growth Analysis"
	StepNameAnalysingStepper = "Analysing"
	StepNameResults          = "Analysis Results"
	StepNameNextSteps        = "Next Steps"
	StepCounterFormat        = "Step %d of %d"
)

// Dashboard tab names
const (
	TabGrowthManifest = "Growth Manifest"
	TabGrowthTemplate = "Growth Template"
	TabGrowthPlan     = "Growth Plan"
)

// Dashboard placeholder content
const (
	PlaceholderGrowthManifest = `No growth manifest generated yet.

Run the analysis to generate a growth manifest for your project.

The manifest will contain:
  - Tech stack detection results
  - Current growth features
  - Revenue leakage issues
  - Growth opportunities`

	PlaceholderGrowthTemplate = `No growth template generated yet.

Run the analysis to generate a growth template for your project.

The template will contain structured data about your
project's growth potential and recommended strategies.`

	PlaceholderGrowthPlan = `No growth plan created yet.

To create a plan, navigate to Next Steps and select
'Generate Growth Plan'.

The plan will contain:
  - Executive summary
  - Selected growth loops
  - Implementation roadmap
  - Success metrics`
)

// Results view
const (
	ResultsBanner    = "Skene Analysis Complete"
	ResultsNextSteps = "Press 'n' for next steps"
)

// Next steps view
const (
	NextStepsSuccess = "Analysis complete! What would you like to do next?"
)

// Next step action definitions
type NextStepDef struct {
	ID          string
	Name        string
	Description string
	Command     string
}

var NextStepActions = []NextStepDef{
	{
		ID:          "plan",
		Name:        "Generate Growth Plan",
		Description: "Create a prioritized growth plan with implementation roadmap",
		Command:     "uvx skene-growth plan",
	},
	{
		ID:          "build",
		Name:        "Build Implementation Prompt",
		Description: "Generate a ready-to-use prompt for Cursor, Claude, or other AI tools",
		Command:     "uvx skene-growth build",
	},
	{
		ID:          "validate",
		Name:        "Validate Manifest",
		Description: "Validate the growth manifest against the schema",
		Command:     "uvx skene-growth validate",
	},
	{
		ID:          "rerun",
		Name:        "Re-run Analysis",
		Description: "Analyze the codebase again with the current configuration",
		Command:     "uvx skene-growth analyze .",
	},
	{
		ID:          "open",
		Name:        "Open Generated Files",
		Description: "View the analysis output in ./skene-context/",
		Command:     "",
	},
	{
		ID:          "config",
		Name:        "Change Configuration",
		Description: "Modify provider, model, or project settings",
		Command:     "",
	},
	{
		ID:          "exit",
		Name:        "Exit",
		Description: "Close Skene",
		Command:     "",
	},
}

// Welcome view
const (
	WelcomeSubtitle = "Product-Led Growth analysis for your codebase"
	WelcomeCTA      = "> ENTER <"
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
	ProjectDirViewAnalysis   = "View Analysis"
	ProjectDirRerunAnalysis  = "Re-run Analysis"
)

// Analysis config view
const (
	AnalysisConfigSummary   = "Analysis Summary"
	AnalysisConfigRunButton = "Run Analysis"
)

// Analyzing view
const (
	AnalyzingFailed   = "Failed"
	AnalyzingComplete = "Complete"
	AnalyzingRunning  = "Running..."
	AnalyzingDone     = "Done"
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
	HelpDescPlayMiniGame     = "play mini game"
	HelpDescPlayGame         = "play game"
	HelpDescRetry            = "retry"
	HelpDescRetryDetection   = "retry detection"
	HelpDescManualEntry      = "manual entry"
	HelpDescSkipManualEntry  = "skip to manual entry"
	HelpDescContinueManual   = "continue to manual entry"
	HelpDescBackToProvider   = "go back to provider selection"
	HelpDescToggleOption     = "toggle option"
	HelpDescOpenFolder       = "open folder"
	HelpDescTabs             = "tabs"
)
