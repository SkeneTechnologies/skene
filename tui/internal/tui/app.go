package tui

import (
	"context"
	"fmt"
	"os"
	"time"

	"skene/internal/constants"
	"skene/internal/game"
	"skene/internal/services/auth"
	"skene/internal/services/config"
	"skene/internal/services/growth"
	"skene/internal/services/versioncheck"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"skene/internal/tui/views"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/pkg/browser"
	"path/filepath"
)

// ═══════════════════════════════════════════════════════════════════
// WIZARD STATE MACHINE
// ═══════════════════════════════════════════════════════════════════

// AppState represents the current wizard step
type AppState int

const (
	StateWelcome        AppState = iota // Welcome screen
	StateConfigCheck                    // Existing config detected – use or reconfigure?
	StateProviderSelect                 // AI provider selection
	StateModelSelect                    // Model selection for chosen provider
	StateAuth                           // Skene magic link authentication
	StateAPIKey                         // Manual API key entry
	StateLocalModel                     // Local model detection (Ollama/LM Studio)
	StateProjectDir                     // Project directory selection
	StateAnalysisConfig                 // Analysis configuration
	StateAnalyzing                      // Analysis progress
	StateResults                        // Results dashboard
	StateNextSteps                      // Next steps after analysis
	StateError                          // Error display
	StateGame                           // Mini game during wait
)

// ═══════════════════════════════════════════════════════════════════
// MESSAGES
// ═══════════════════════════════════════════════════════════════════

// TickMsg is sent on each animation frame
type TickMsg time.Time

// CountdownMsg is sent during auth countdown
type CountdownMsg int

// AnalysisDoneMsg is sent when analysis completes
type AnalysisDoneMsg struct {
	Error  error
	Result *growth.AnalysisResult
}

// AnalysisPhaseMsg is sent to update analysis progress
type AnalysisPhaseMsg struct {
	Update growth.PhaseUpdate
}

// NextStepOutputMsg is sent when a next-step command produces output
type NextStepOutputMsg struct {
	Line string
}

// NextStepDoneMsg is sent when a next-step command finishes
type NextStepDoneMsg struct {
	Error error
}

// PromptMsg is sent when uvx asks an interactive question
type PromptMsg struct {
	Question string
	Options  []string
	Response chan string
}

// LocalModelDetectMsg is sent with local model detection results
type LocalModelDetectMsg struct {
	Models []string
	Error  error
}

// AuthCallbackMsg is sent when the API key is received from the external auth website
type AuthCallbackMsg struct {
	APIKey string
	Model  string
	Error  error
}

// VersionCheckMsg is sent when the background version check completes
type VersionCheckMsg struct {
	Result *versioncheck.Result
}

// authVerifiedMsg triggers the transition from verifying to success state
type authVerifiedMsg struct{}

// authSuccessTransitionMsg triggers the transition after showing auth success
type authSuccessTransitionMsg struct{}

// ═══════════════════════════════════════════════════════════════════
// APP MODEL
// ═══════════════════════════════════════════════════════════════════

// App is the main Bubble Tea application model implementing the wizard
type App struct {
	// Core state
	state     AppState
	prevState AppState
	width     int
	height    int
	time      float64

	// Services
	configMgr *config.Manager

	// Selected configuration
	selectedProvider *config.Provider
	selectedModel    *config.Model

	// Views
	welcomeView      *views.WelcomeView
	configCheckView  *views.ConfigCheckView
	providerView     *views.ProviderView
	modelView          *views.ModelView
	authView           *views.AuthView
	apiKeyView         *views.APIKeyView
	localModelView     *views.LocalModelView
	projectDirView     *views.ProjectDirView
	analysisConfigView *views.AnalysisConfigView
	analyzingView      *views.AnalyzingView
	resultsView        *views.ResultsView
	nextStepsView      *views.NextStepsView
	errorView          *views.ErrorView

	// Help overlay
	helpOverlay *components.HelpOverlay
	showHelp    bool

	// Game
	game *game.Game

	// Timing
	analysisStartTime time.Time

	// Cancellation for running processes
	cancelFunc      context.CancelFunc
	analyzingOrigin AppState // state to return to when cancelling/failing

	// Auth state
	authCountdown  int
	callbackServer *auth.CallbackServer

	// Error state
	currentError *views.ErrorInfo

	// Interactive prompt state
	pendingPromptResponse chan string

	// Program reference for sending messages from background tasks
	program *tea.Program
}

// ═══════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

// NewApp creates a new wizard application
func NewApp() *App {
	configMgr := config.NewManager(".")
	_ = configMgr.LoadConfig()

	// Set default values if not present
	if configMgr.Config.OutputDir == "" {
		configMgr.Config.OutputDir = "./skene-context"
	}

	app := &App{
		state:        StateWelcome,
		configMgr:    configMgr,
		welcomeView:  views.NewWelcomeView(),
		providerView: views.NewProviderView(),
		helpOverlay:  components.NewHelpOverlay(),
	}

	return app
}

// SetProgram sets the tea.Program reference for sending messages from background tasks
func (a *App) SetProgram(p *tea.Program) {
	a.program = p
}

// Init initializes the application
func (a *App) Init() tea.Cmd {
	var cmds []tea.Cmd
	cmds = append(cmds, tick())
	cmds = append(cmds, textinput.Blink)
	cmds = append(cmds, checkForUpdate())
	// Initialize welcome animation
	if a.welcomeView != nil {
		animCmd := a.welcomeView.InitAnimation()
		if animCmd != nil {
			cmds = append(cmds, animCmd)
		}
	}
	return tea.Batch(cmds...)
}

// ═══════════════════════════════════════════════════════════════════
// UPDATE
// ═══════════════════════════════════════════════════════════════════

// Update handles messages and updates state
func (a *App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.KeyMsg:
		// Global: ctrl+c always quits
		if msg.String() == "ctrl+c" {
			return a, tea.Quit
		}

		// Help toggle
		if msg.String() == "?" && a.state != StateAPIKey && a.state != StateProjectDir {
			a.showHelp = !a.showHelp
			return a, nil
		}

		// Close help on any key
		if a.showHelp && msg.String() != "?" {
			a.showHelp = false
			return a, nil
		}

		// State-specific key handling
		cmd := a.handleKeyPress(msg)
		if cmd != nil {
			cmds = append(cmds, cmd)
		}

	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
		a.updateViewSizes()

	case TickMsg:
		a.time += 0.05

		// Update welcome animation
		if a.state == StateWelcome {
			a.welcomeView.SetTime(a.time)
		}

		// Tick spinners for active views
		if a.state == StateAnalyzing && a.analyzingView != nil {
			a.analyzingView.TickSpinner()
			// Real analysis progress is updated via AnalysisPhaseMsg
		}
		if a.state == StateAuth && a.authView != nil {
			a.authView.TickSpinner()
		}
		if a.state == StateAPIKey && a.apiKeyView != nil {
			a.apiKeyView.TickSpinner()
		}
		if a.state == StateLocalModel && a.localModelView != nil {
			a.localModelView.TickSpinner()
		}

		// Update game if active
		if a.state == StateGame && a.game != nil {
			a.game.Update()
			// Tick progress spinner if showing progress
			a.game.TickProgressSpinner()
			// Update progress info from analyzing view
			if a.analyzingView != nil {
				if a.analyzingView.IsDone() {
					if a.analyzingView.HasFailed() {
						a.game.SetProgressInfo("", true, true)
					} else {
						a.game.SetProgressInfo("", true, false)
					}
				} else {
					phase := a.analyzingView.GetCurrentPhase()
					if phase == "" {
						phase = "Analyzing..."
					}
					a.game.SetProgressInfo(phase, false, false)
				}
			}
		}

		cmds = append(cmds, tick())

	case CountdownMsg:
		if a.state != StateAuth {
			break
		}
		a.authCountdown = int(msg)
		if a.authCountdown <= 0 {
			if a.authView != nil {
				_ = browser.OpenURL(a.authView.GetAuthURL())
				a.authView.SetAuthState(views.AuthStateWaiting)
			}
		} else if a.authView != nil {
			a.authView.SetCountdown(a.authCountdown)
			cmds = append(cmds, countdown(a.authCountdown-1))
		}

	case VersionCheckMsg:
		if msg.Result != nil && a.welcomeView != nil {
			a.welcomeView.SetUpdateAvailable(msg.Result.NewVersion, msg.Result.UpdateCmd)
		}

	case AnalysisDoneMsg:
		err := msg.Error
		if err == nil && msg.Result != nil && msg.Result.Error != nil {
			err = msg.Result.Error
		}
		// Update game progress indicator
		if a.state == StateGame && a.game != nil {
			if err != nil {
				a.game.SetProgressInfo("", true, true)
			} else {
				a.game.SetProgressInfo("", true, false)
			}
		}
		if err != nil {
			suggestion := analysisErrorSuggestion(err)
			a.showError(&views.ErrorInfo{
				Code:       constants.ErrorAnalysisFailed,
				Title:      constants.ErrorAnalysisTitle,
				Message:    err.Error(),
				Suggestion: suggestion,
				Severity:   views.SeverityError,
				Retryable:  true,
			})
		} else {
			a.state = StateResults
			if msg.Result != nil {
				a.resultsView = views.NewResultsViewWithContent(
					msg.Result.GrowthPlan,
					msg.Result.Manifest,
					msg.Result.GrowthTemplate,
				)
			} else {
				a.resultsView = views.NewResultsView()
			}
			a.resultsView.SetSize(a.width, a.height)
		}

	case AnalysisPhaseMsg:
		if a.analyzingView != nil {
			// Use phase name from enum instead of index
			phaseName := msg.Update.Phase.String()
			a.analyzingView.UpdatePhaseByName(phaseName, msg.Update.Progress, msg.Update.Message)
		}
		// Update game progress if game is active
		if a.state == StateGame && a.game != nil && a.analyzingView != nil {
			currentPhase := a.analyzingView.GetCurrentPhase()
			if currentPhase == "" {
				currentPhase = "Analyzing..."
			}
			a.game.SetProgressInfo(currentPhase, false, false)
		}

	case NextStepOutputMsg:
		if a.analyzingView != nil {
			a.analyzingView.UpdatePhase(-1, 0, msg.Line)
		}

	case PromptMsg:
		if a.analyzingView != nil {
			a.analyzingView.ShowPrompt(msg.Question, msg.Options)
			a.pendingPromptResponse = msg.Response
		}

	case NextStepDoneMsg:
		if a.analyzingView != nil {
			if msg.Error != nil {
				a.analyzingView.SetCommandFailed(msg.Error.Error())
			} else {
				a.analyzingView.SetDone()
			}
		}
		// Update game progress if game is active
		if a.state == StateGame && a.game != nil && a.analyzingView != nil {
			if a.analyzingView.IsDone() {
				if a.analyzingView.HasFailed() {
					a.game.SetProgressInfo("", true, true)
				} else {
					a.game.SetProgressInfo("", true, false)
				}
			}
		}

	case AuthCallbackMsg:
		if msg.Error != nil {
			// Auth failed, fall back to manual entry
			if a.authView != nil {
				a.authView.ShowFallback()
			}
		} else {
			// Auth succeeded - set the API key and model
			a.configMgr.SetAPIKey(msg.APIKey)
			if msg.Model != "" {
				a.configMgr.SetModel(msg.Model)
			} else {
				// Default Skene model
				a.configMgr.SetModel("skene-v1")
			}

			// Show "verifying" spinner first so the user sees activity
			if a.authView != nil {
				a.authView.SetAuthState(views.AuthStateVerifying)
			}

			// Shutdown the callback server
			if a.callbackServer != nil {
				a.callbackServer.Shutdown()
				a.callbackServer = nil
			}

			// After a fake verification delay, show success
			cmds = append(cmds, tea.Tick(2*time.Second, func(t time.Time) tea.Msg {
				return authVerifiedMsg{}
			}))
		}

	case authVerifiedMsg:
		// Show success state after the fake verification delay
		if a.authView != nil {
			a.authView.SetAuthState(views.AuthStateSuccess)
		}
		// Transition to project directory after showing success briefly
		cmds = append(cmds, tea.Tick(1500*time.Millisecond, func(t time.Time) tea.Msg {
			return authSuccessTransitionMsg{}
		}))

	case authSuccessTransitionMsg:
		a.transitionToProjectDir()

	case LocalModelDetectMsg:
		if a.localModelView != nil {
			if msg.Error != nil {
				a.localModelView.SetError(msg.Error.Error())
			} else {
				a.localModelView.SetModels(msg.Models)
			}
		}

	case game.GameTickMsg:
		if a.state == StateGame && a.game != nil {
			a.game.Update()
			cmds = append(cmds, game.GameTickCmd())
		}

	default:
		// Forward messages to welcome animation
		if a.state == StateWelcome && a.welcomeView != nil {
			animCmd := a.welcomeView.UpdateAnimation(msg)
			if animCmd != nil {
				cmds = append(cmds, animCmd)
			}
		}
	}

	return a, tea.Batch(cmds...)
}

// ═══════════════════════════════════════════════════════════════════
// KEY HANDLERS
// ═══════════════════════════════════════════════════════════════════

func (a *App) handleKeyPress(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()

	switch a.state {
	case StateWelcome:
		return a.handleWelcomeKeys(key)
	case StateConfigCheck:
		return a.handleConfigCheckKeys(msg)
	case StateProviderSelect:
		return a.handleProviderKeys(msg)
	case StateModelSelect:
		return a.handleModelKeys(msg)
	case StateAuth:
		return a.handleAuthKeys(key)
	case StateAPIKey:
		return a.handleAPIKeyKeys(msg)
	case StateLocalModel:
		return a.handleLocalModelKeys(key)
	case StateProjectDir:
		return a.handleProjectDirKeys(msg)
	case StateAnalysisConfig:
		return a.handleAnalysisConfigKeys(key)
	case StateAnalyzing:
		return a.handleAnalyzingKeys(key)
	case StateResults:
		return a.handleResultsKeys(key)
	case StateNextSteps:
		return a.handleNextStepsKeys(key)
	case StateError:
		return a.handleErrorKeys(key)
	case StateGame:
		return a.handleGameKeys(msg)
	}

	return nil
}

func (a *App) handleWelcomeKeys(key string) tea.Cmd {
	switch key {
	case "enter":
		if a.configMgr.HasValidConfig() {
			a.populateSelectedFromConfig()
			providerName := a.configMgr.Config.Provider
			if a.selectedProvider != nil {
				providerName = a.selectedProvider.Name
			}
			modelName := a.configMgr.Config.Model
			if a.selectedModel != nil {
				modelName = a.selectedModel.Name
			}
			a.configCheckView = views.NewConfigCheckView(
				providerName,
				modelName,
				a.configMgr.GetMaskedAPIKey(),
			)
			a.configCheckView.SetSize(a.width, a.height)
			a.state = StateConfigCheck
		} else {
			a.state = StateProviderSelect
			a.providerView.SetSize(a.width, a.height)
		}
		return nil
	}
	return nil
}

func (a *App) handleConfigCheckKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()
	switch key {
	case "up", "k":
		a.configCheckView.HandleUp()
	case "down", "j":
		a.configCheckView.HandleDown()
	case "enter":
		if a.configCheckView.SelectedUseExisting() {
			a.transitionToProjectDir()
		} else {
			a.state = StateProviderSelect
			a.providerView.SetSize(a.width, a.height)
		}
	case "esc":
		a.state = StateWelcome
		return a.welcomeView.ResetAnimation()
	}
	return nil
}

func (a *App) handleProviderKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()
	switch key {
	case "up", "k":
		a.providerView.HandleUp()
	case "down", "j":
		a.providerView.HandleDown()
	case "enter":
		return a.selectProvider()
	case "esc":
		a.state = StateWelcome
		return a.welcomeView.ResetAnimation()
	}
	return nil
}

func (a *App) handleModelKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()
	switch key {
	case "up", "k":
		a.modelView.HandleUp()
	case "down", "j":
		a.modelView.HandleDown()
	case "enter":
		a.selectModel()
	case "esc":
		a.state = StateProviderSelect
	}
	return nil
}

func (a *App) handleAuthKeys(key string) tea.Cmd {
	switch key {
	case "m":
		// Skip to manual entry - shutdown callback server
		if a.callbackServer != nil {
			a.callbackServer.Shutdown()
			a.callbackServer = nil
		}
		if a.authView != nil {
			a.authView.ShowFallback()
		}
	case "enter":
		if a.authView != nil && a.authView.IsFallbackShown() {
			a.transitionToAPIKey()
		}
	case "esc":
		// Clean up callback server
		if a.callbackServer != nil {
			a.callbackServer.Shutdown()
			a.callbackServer = nil
		}
		a.state = StateProviderSelect
	}
	return nil
}

func (a *App) handleAPIKeyKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()

	switch key {
	case "enter":
		if a.apiKeyView.Validate() {
			a.configMgr.SetAPIKey(a.apiKeyView.GetAPIKey())
			if a.apiKeyView.GetBaseURL() != "" {
				a.configMgr.SetBaseURL(a.apiKeyView.GetBaseURL())
			}
			a.transitionToProjectDir()
		}
	case "tab":
		a.apiKeyView.HandleTab()
	case "esc":
		a.navigateBackFromAPIKey()
	default:
		a.apiKeyView.Update(msg)
	}
	return nil
}

func (a *App) handleLocalModelKeys(key string) tea.Cmd {
	if a.localModelView == nil {
		return nil
	}

	switch key {
	case "up", "k":
		a.localModelView.HandleUp()
	case "down", "j":
		a.localModelView.HandleDown()
	case "enter":
		if a.localModelView.IsFound() {
			model := a.localModelView.GetSelectedModel()
			a.configMgr.SetModel(model)
			a.configMgr.SetBaseURL(a.localModelView.GetBaseURL())
			a.transitionToProjectDir()
		}
	case "r":
		// Retry detection
		return a.detectLocalModels()
	case "esc":
		a.state = StateProviderSelect
	}
	return nil
}

func (a *App) handleProjectDirKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()

	// Handle existing analysis choice prompt
	if a.projectDirView.IsAskingExistingChoice() {
		switch key {
		case "left", "h":
			a.projectDirView.HandleLeft()
		case "right", "l":
			a.projectDirView.HandleRight()
		case "enter":
			choice := a.projectDirView.GetExistingChoiceLabel()
			a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
			switch choice {
			case constants.ProjectDirViewAnalysis:
				a.projectDirView.SetExistingChoice(true)
				a.transitionToResultsFromExisting()
			case constants.ProjectDirRerunAnalysis:
				a.projectDirView.SetExistingChoice(false)
				a.transitionToAnalysisConfig()
			}
		case "esc":
			a.projectDirView.DismissExistingChoice()
		}
		return nil
	}

	// Handle browsing mode
	if a.projectDirView.IsBrowsing() {
		if a.projectDirView.BrowseFocusOnList() {
			switch key {
			case "up", "k", "down", "j", "backspace", ".":
				a.projectDirView.HandleBrowseKey(key)
			case "enter":
				a.projectDirView.HandleBrowseKey(key)
			case "tab":
				a.projectDirView.HandleBrowseTab()
			case "esc":
				a.projectDirView.StopBrowsing()
			}
		} else {
			switch key {
			case "left", "h":
				a.projectDirView.HandleBrowseLeft()
			case "right", "l":
				a.projectDirView.HandleBrowseRight()
			case "enter":
				btn := a.projectDirView.GetBrowseButtonLabel()
				switch btn {
				case constants.ButtonSelectDir:
					a.projectDirView.BrowseConfirm()
				case constants.ButtonCancel:
					a.projectDirView.StopBrowsing()
				}
			case "tab":
				a.projectDirView.HandleBrowseTab()
			case "esc":
				a.projectDirView.StopBrowsing()
			}
		}
		return nil
	}

	if a.projectDirView.IsInputFocused() {
		switch key {
		case "enter":
			if a.projectDirView.IsValid() {
				// Check for existing analysis first
				if a.projectDirView.CheckForExistingAnalysis() {
					return nil
				}
				a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
				a.transitionToAnalysisConfig()
			}
		case "tab":
			a.projectDirView.HandleTab()
		case "esc":
			a.navigateBackFromProjectDir()
		default:
			a.projectDirView.Update(msg)
		}
	} else {
		switch key {
		case "left", "h":
			a.projectDirView.HandleLeft()
		case "right", "l":
			a.projectDirView.HandleRight()
		case "enter":
			btn := a.projectDirView.GetButtonLabel()
			switch btn {
			case constants.ButtonUseCurrent:
				a.projectDirView.UseCurrentDir()
			case constants.ButtonBrowse:
				a.projectDirView.StartBrowsing()
			case constants.ButtonContinue:
				if a.projectDirView.IsValid() {
					// Check for existing analysis first
					if a.projectDirView.CheckForExistingAnalysis() {
						return nil
					}
					a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
					a.transitionToAnalysisConfig()
				}
			}
		case "tab":
			a.projectDirView.HandleTab()
		case "esc":
			a.navigateBackFromProjectDir()
		}
	}
	return nil
}

func (a *App) handleAnalysisConfigKeys(key string) tea.Cmd {
	switch key {
	case "enter":
		a.applyAnalysisConfig()
		return a.startAnalysis()
	case "esc":
		a.state = StateProjectDir
	}
	return nil
}

func (a *App) handleAnalyzingKeys(key string) tea.Cmd {
	if a.analyzingView != nil && a.analyzingView.IsPromptActive() {
		switch key {
		case "up", "k":
			a.analyzingView.HandlePromptUp()
		case "down", "j":
			a.analyzingView.HandlePromptDown()
		case "enter":
			idx := a.analyzingView.GetSelectedOptionIndex()
			a.analyzingView.DismissPrompt()
			if a.pendingPromptResponse != nil {
				a.pendingPromptResponse <- fmt.Sprintf("%d", idx)
				a.pendingPromptResponse = nil
			}
		}
		return nil
	}

	switch key {
	case "up", "k":
		if a.analyzingView != nil {
			a.analyzingView.ScrollUp(3)
		}
	case "down", "j":
		if a.analyzingView != nil {
			a.analyzingView.ScrollDown(3)
		}
	case "g":
		if a.analyzingView != nil && !a.analyzingView.IsDone() {
			a.prevState = a.state
			a.state = StateGame
			if a.game == nil {
				a.game = game.NewGame(60, 20)
			} else {
				a.game.Restart()
			}
			a.game.SetSize(60, 20)
			currentPhase := a.analyzingView.GetCurrentPhase()
			if currentPhase == "" {
				currentPhase = "Analyzing..."
			}
			a.game.SetProgressInfo(currentPhase, false, false)
			return game.GameTickCmd()
		}
	case "esc":
		if a.analyzingView == nil {
			return nil
		}
		if a.analyzingView.HasFailed() {
			a.navigateBackFromAnalyzing()
		} else if a.analyzingView.IsDone() {
			a.navigateBackFromAnalyzing()
		} else {
			if a.cancelFunc != nil {
				a.cancelFunc()
				a.cancelFunc = nil
			}
			a.navigateBackFromAnalyzing()
		}
	}
	return nil
}

func (a *App) handleResultsKeys(key string) tea.Cmd {
	switch key {
	case "left", "h":
		a.resultsView.HandleLeft()
	case "right", "l":
		a.resultsView.HandleRight()
	case "up", "k":
		a.resultsView.HandleUp()
	case "down", "j":
		a.resultsView.HandleDown()
	case "tab":
		a.resultsView.HandleTab()
	case "n", "enter":
		a.state = StateNextSteps
		a.nextStepsView = views.NewNextStepsView()
		a.nextStepsView.SetSize(a.width, a.height)
	}
	return nil
}

func (a *App) handleNextStepsKeys(key string) tea.Cmd {
	switch key {
	case "up", "k":
		a.nextStepsView.HandleUp()
	case "down", "j":
		a.nextStepsView.HandleDown()
	case "enter":
		action := a.nextStepsView.GetSelectedAction()
		if action == nil {
			return nil
		}
		switch action.ID {
		case "exit":
			return tea.Quit
		case "rerun":
			return a.startAnalysis()
		case "config":
			a.configCheckView = nil
			a.apiKeyView = nil
			a.providerView = views.NewProviderView()
			a.providerView.SetSize(a.width, a.height)
			a.state = StateProviderSelect
		case "plan":
			return a.runEngineCommand("Generating Growth Plan", "plan")
		case "build":
			return a.runEngineCommand("Building Implementation Prompt", "build")
		case "validate":
			return a.runEngineCommand("Validating Manifest", "validate")
		case "open":
			projectDir := a.configMgr.Config.ProjectDir
			if projectDir == "" {
				projectDir, _ = os.Getwd()
			}
			outputDir := filepath.Join(projectDir, constants.OutputDirName)
			_ = browser.OpenURL(outputDir)
		}
	case "esc":
		a.refreshResultsView()
		a.state = StateResults
	}
	return nil
}

func (a *App) handleErrorKeys(key string) tea.Cmd {
	switch key {
	case "left", "h":
		a.errorView.HandleLeft()
	case "right", "l":
		a.errorView.HandleRight()
	case "enter":
		btn := a.errorView.GetSelectedButton()
		switch btn {
		case "Retry":
			a.state = a.prevState
		case "Go Back":
			a.navigateBackFromError()
		case "Quit":
			return tea.Quit
		}
	case "esc":
		a.navigateBackFromError()
	}
	return nil
}

func (a *App) handleGameKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()
	switch key {
	case "left", "a":
		a.game.MoveLeft()
	case "right", "d":
		a.game.MoveRight()
	case " ":
		a.game.Shoot()
	case "p":
		a.game.TogglePause()
	case "r":
		if a.game.IsGameOver() {
			a.game.Restart()
		}
	case "esc":
		// Clear progress indicator when exiting game
		if a.game != nil {
			a.game.ClearProgressInfo()
		}
		a.state = a.prevState
	}
	return nil
}

// ═══════════════════════════════════════════════════════════════════
// STATE TRANSITIONS
// ═══════════════════════════════════════════════════════════════════

func (a *App) selectProvider() tea.Cmd {
	provider := a.providerView.GetSelectedProvider()
	if provider == nil {
		return nil
	}

	a.selectedProvider = provider
	a.configMgr.SetProvider(provider.ID)

	// Branch based on provider type
	if provider.ID == "skene" {
		// Skene: start callback server and open browser for auth
		callbackServer, err := auth.NewCallbackServer()
		if err != nil {
			a.showError(&views.ErrorInfo{
				Code:       "AUTH_SERVER_FAILED",
				Title:      "Authentication Setup Failed",
				Message:    err.Error(),
				Suggestion: "Try again or use a different provider.",
				Severity:   views.SeverityError,
				Retryable:  true,
			})
			return nil
		}

		if err := callbackServer.Start(); err != nil {
			a.showError(&views.ErrorInfo{
				Code:       "AUTH_SERVER_FAILED",
				Title:      "Authentication Setup Failed",
				Message:    err.Error(),
				Suggestion: "Try again or use a different provider.",
				Severity:   views.SeverityError,
				Retryable:  true,
			})
			return nil
		}

		a.callbackServer = callbackServer

		// Build the auth URL with the callback parameter
		authURL := provider.AuthURL
		if authURL == "" {
			authURL = "https://www.skene.ai/login"
		}
		authURL = fmt.Sprintf("%s?callback=%s", authURL, callbackServer.GetCallbackURL())

		a.authView = views.NewAuthView(provider)
		a.authView.SetAuthURL(authURL)
		a.authView.SetSize(a.width, a.height)
		a.authCountdown = 3
		a.state = StateAuth
		return tea.Batch(countdown(3), a.waitForAuthCallback())
	}

	if provider.IsLocal {
		// Local model: detect runtime
		a.localModelView = views.NewLocalModelView(provider.ID)
		a.localModelView.SetSize(a.width, a.height)
		a.state = StateLocalModel
		return a.detectLocalModels()
	}

	// Regular providers: go to model selection
	a.modelView = views.NewModelView(provider)
	a.modelView.SetSize(a.width, a.height)
	a.state = StateModelSelect
	return nil
}

func (a *App) selectModel() {
	model := a.modelView.GetSelectedModel()
	if model == nil {
		return
	}

	a.selectedModel = model
	a.configMgr.SetModel(model.ID)

	// Go to API key entry
	a.transitionToAPIKey()
}

func (a *App) transitionToAPIKey() {
	a.apiKeyView = views.NewAPIKeyView(a.selectedProvider, a.selectedModel)
	a.apiKeyView.SetSize(a.width, a.height)
	a.state = StateAPIKey
}

func (a *App) transitionToProjectDir() {
	_ = a.configMgr.SaveUserConfig()
	a.projectDirView = views.NewProjectDirView()
	a.projectDirView.SetSize(a.width, a.height)
	a.state = StateProjectDir
}

func (a *App) transitionToAnalysisConfig() {
	providerName := ""
	modelName := ""
	if a.selectedProvider != nil {
		providerName = a.selectedProvider.Name
	}
	if a.selectedModel != nil {
		modelName = a.selectedModel.Name
	}
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir = "."
	}

	a.analysisConfigView = views.NewAnalysisConfigView(providerName, modelName, projectDir)
	a.analysisConfigView.SetSize(a.width, a.height)
	a.state = StateAnalysisConfig
}

func (a *App) transitionToResultsFromExisting() {
	projectDir := a.configMgr.Config.ProjectDir
	outputDir := filepath.Join(projectDir, constants.OutputDirName)

	growthPlan := loadFileContent(filepath.Join(outputDir, constants.GrowthPlanFile))
	manifest := loadFileContent(filepath.Join(outputDir, constants.GrowthManifestFile))
	growthTemplate := loadFileContent(filepath.Join(outputDir, constants.GrowthTemplateFile))

	a.resultsView = views.NewResultsViewWithContent(growthPlan, manifest, growthTemplate)
	a.resultsView.SetSize(a.width, a.height)
	a.state = StateResults
}

func (a *App) refreshResultsView() {
	if a.resultsView == nil {
		return
	}
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		return
	}
	outputDir := filepath.Join(projectDir, constants.OutputDirName)
	a.resultsView.RefreshContent(outputDir)
}

func (a *App) applyAnalysisConfig() {
	if a.analysisConfigView != nil {
		a.configMgr.Config.UseGrowth = a.analysisConfigView.GetUseGrowth()
		a.configMgr.Config.Verbose = true
	}
}

func (a *App) navigateBackFromAPIKey() {
	if a.selectedProvider != nil {
		if a.selectedProvider.ID == "skene" {
			a.state = StateAuth
		} else if a.selectedProvider.IsGeneric {
			a.state = StateProviderSelect
		} else {
			a.state = StateModelSelect
		}
	} else {
		a.state = StateProviderSelect
	}
}

func (a *App) navigateBackFromProjectDir() {
	if a.selectedProvider != nil && a.selectedProvider.IsLocal {
		a.state = StateLocalModel
	} else if a.apiKeyView != nil {
		a.state = StateAPIKey
	} else if a.configCheckView != nil {
		a.configCheckView.SetSize(a.width, a.height)
		a.state = StateConfigCheck
	} else {
		a.state = StateProviderSelect
		a.providerView.SetSize(a.width, a.height)
	}
}

func (a *App) navigateBackFromAnalyzing() {
	// Clean up the cancel func if still set
	if a.cancelFunc != nil {
		a.cancelFunc()
		a.cancelFunc = nil
	}

	switch a.analyzingOrigin {
	case StateNextSteps:
		a.refreshResultsView()
		a.state = StateNextSteps
		if a.nextStepsView == nil {
			a.nextStepsView = views.NewNextStepsView()
		}
		a.nextStepsView.SetSize(a.width, a.height)
	case StateAnalysisConfig:
		a.state = StateAnalysisConfig
		if a.analysisConfigView != nil {
			a.analysisConfigView.SetSize(a.width, a.height)
		}
	default:
		a.state = StateAnalysisConfig
	}
}

func (a *App) navigateBackFromError() {
	// If the error came from a running process, skip back to the origin
	// so the user can re-trigger it rather than landing on a dead view.
	if a.prevState == StateAnalyzing {
		a.navigateBackFromAnalyzing()
		return
	}

	target := a.prevState
	switch target {
	case StateModelSelect:
		if a.modelView == nil {
			target = StateProviderSelect
		}
	case StateAuth:
		if a.authView == nil {
			target = StateProviderSelect
		}
	case StateAPIKey:
		if a.apiKeyView == nil {
			target = StateProviderSelect
		}
	case StateLocalModel:
		if a.localModelView == nil {
			target = StateProviderSelect
		}
	case StateProjectDir:
		if a.projectDirView == nil {
			target = StateProviderSelect
		}
	case StateAnalysisConfig:
		if a.analysisConfigView == nil {
			target = StateProjectDir
		}
	}
	a.state = target
}

// ═══════════════════════════════════════════════════════════════════
// ASYNC OPERATIONS
// ═══════════════════════════════════════════════════════════════════

func (a *App) startAnalysis() tea.Cmd {
	a.analyzingView = views.NewAnalyzingView()
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateAnalysisConfig
	a.state = StateAnalyzing
	return a.startRealAnalysisCmd(a.program)
}

func (a *App) startRealAnalysisCmd(p *tea.Program) tea.Cmd {
	cfg := a.buildEngineConfig()

	ctx, cancel := context.WithCancel(context.Background())
	a.cancelFunc = cancel

	return func() tea.Msg {
		engine := growth.NewEngine(cfg, func(update growth.PhaseUpdate) {
			if p != nil {
				p.Send(AnalysisPhaseMsg{Update: update})
			}
		})
		engine.SetPromptHandler(func(prompt growth.InteractivePrompt) {
			if p != nil {
				p.Send(PromptMsg{
					Question: prompt.Question,
					Options:  prompt.Options,
					Response: prompt.Response,
				})
			}
		})

		result := engine.Run(ctx)
		if result.Error != nil {
			return AnalysisDoneMsg{Error: result.Error, Result: result}
		}
		return AnalysisDoneMsg{Error: nil, Result: result}
	}
}

func (a *App) runEngineCommand(title string, command string) tea.Cmd {
	a.analyzingView = views.NewCommandView(title)
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateNextSteps
	a.state = StateAnalyzing

	cfg := a.buildEngineConfig()

	ctx, cancel := context.WithCancel(context.Background())
	a.cancelFunc = cancel

	p := a.program
	return func() tea.Msg {
		if ctx.Err() != nil {
			return NextStepDoneMsg{Error: ctx.Err()}
		}

		engine := growth.NewEngine(cfg, func(update growth.PhaseUpdate) {
			if p != nil {
				p.Send(NextStepOutputMsg{Line: update.Message})
			}
		})
		engine.SetPromptHandler(func(prompt growth.InteractivePrompt) {
			if p != nil {
				p.Send(PromptMsg{
					Question: prompt.Question,
					Options:  prompt.Options,
					Response: prompt.Response,
				})
			}
		})

		var result *growth.AnalysisResult
		switch command {
		case "plan":
			if p != nil {
				p.Send(NextStepOutputMsg{Line: "Running: uvx skene plan ..."})
			}
			result = engine.GeneratePlan()
		case "build":
			if p != nil {
				p.Send(NextStepOutputMsg{Line: "Running: uvx skene build ..."})
			}
			result = engine.GenerateBuild()
		case "validate":
			if p != nil {
				p.Send(NextStepOutputMsg{Line: "Running: uvx skene validate ..."})
			}
			result = engine.ValidateManifest()
		default:
			return NextStepDoneMsg{Error: fmt.Errorf("unknown command: %s", command)}
		}

		if result.Error != nil {
			return NextStepDoneMsg{Error: result.Error}
		}
		return NextStepDoneMsg{Error: nil}
	}
}


func (a *App) waitForAuthCallback() tea.Cmd {
	server := a.callbackServer
	if server == nil {
		return nil
	}

	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		result, err := server.WaitForResult(ctx)
		if err != nil {
			return AuthCallbackMsg{Error: fmt.Errorf("authentication timed out")}
		}

		if result.Error != "" {
			return AuthCallbackMsg{Error: fmt.Errorf("%s", result.Error)}
		}

		return AuthCallbackMsg{
			APIKey: result.APIKey,
			Model:  result.Model,
		}
	}
}

func (a *App) detectLocalModels() tea.Cmd {
	providerID := ""
	if a.selectedProvider != nil {
		providerID = a.selectedProvider.ID
	}

	return func() tea.Msg {
		// Simulate detection with some default models
		time.Sleep(500 * time.Millisecond)

		var models []string
		switch providerID {
		case "ollama":
			models = []string{"llama3.3", "mistral", "codellama", "deepseek-r1"}
		case "lmstudio":
			models = []string{"Currently loaded model"}
		}

		if len(models) > 0 {
			return LocalModelDetectMsg{Models: models}
		}
		return LocalModelDetectMsg{
			Error: fmt.Errorf("could not connect to local model server"),
		}
	}
}

// analysisErrorSuggestion returns a contextual suggestion based on the error
func analysisErrorSuggestion(err error) string {
	s := err.Error()
	if containsAny(s, "failed to locate uvx", "failed to download uv") {
		return "The CLI could not provision the uvx runtime. Check your internet connection and try again."
	}
	if containsAny(s, "No module named", "not found: skene", "package not found") {
		return "The skene package could not be found. Make sure it is published or install it manually."
	}
	if containsAny(s, "API key", "401", "unauthorized") {
		return "Check your API key, ensure it has the required permissions, and try again."
	}
	if containsAny(s, "network", "connection", "timeout") {
		return "Check your network connection and try again."
	}
	return "Check the output above for details and try again."
}

func containsAny(s string, substrs ...string) bool {
	for _, sub := range substrs {
		if len(s) >= len(sub) {
			for i := 0; i <= len(s)-len(sub); i++ {
				if s[i:i+len(sub)] == sub {
					return true
				}
			}
		}
	}
	return false
}

func (a *App) showError(err *views.ErrorInfo) {
	a.prevState = a.state
	a.currentError = err
	a.errorView = views.NewErrorView(err)
	a.errorView.SetSize(a.width, a.height)
	a.state = StateError
}

// ═══════════════════════════════════════════════════════════════════
// VIEW SIZING
// ═══════════════════════════════════════════════════════════════════

func (a *App) updateViewSizes() {
	if a.welcomeView != nil {
		a.welcomeView.SetSize(a.width, a.height)
	}
	if a.configCheckView != nil {
		a.configCheckView.SetSize(a.width, a.height)
	}
	if a.providerView != nil {
		a.providerView.SetSize(a.width, a.height)
	}
	if a.modelView != nil {
		a.modelView.SetSize(a.width, a.height)
	}
	if a.authView != nil {
		a.authView.SetSize(a.width, a.height)
	}
	if a.apiKeyView != nil {
		a.apiKeyView.SetSize(a.width, a.height)
	}
	if a.localModelView != nil {
		a.localModelView.SetSize(a.width, a.height)
	}
	if a.projectDirView != nil {
		a.projectDirView.SetSize(a.width, a.height)
	}
	if a.analysisConfigView != nil {
		a.analysisConfigView.SetSize(a.width, a.height)
	}
	if a.analyzingView != nil {
		a.analyzingView.SetSize(a.width, a.height)
	}
	if a.resultsView != nil {
		a.resultsView.SetSize(a.width, a.height)
	}
	if a.nextStepsView != nil {
		a.nextStepsView.SetSize(a.width, a.height)
	}
	if a.errorView != nil {
		a.errorView.SetSize(a.width, a.height)
	}
	if a.game != nil {
		a.game.SetSize(60, 20)
	}
}

// ═══════════════════════════════════════════════════════════════════
// VIEW RENDERING
// ═══════════════════════════════════════════════════════════════════

// View renders the current wizard step
func (a *App) View() string {
	var content string

	switch a.state {
	case StateWelcome:
		content = a.welcomeView.Render()
	case StateConfigCheck:
		if a.configCheckView != nil {
			content = a.configCheckView.Render()
		}
	case StateProviderSelect:
		content = a.providerView.Render()
	case StateModelSelect:
		if a.modelView != nil {
			content = a.modelView.Render()
		}
	case StateAuth:
		if a.authView != nil {
			content = a.authView.Render()
		}
	case StateAPIKey:
		if a.apiKeyView != nil {
			content = a.apiKeyView.Render()
		}
	case StateLocalModel:
		if a.localModelView != nil {
			content = a.localModelView.Render()
		}
	case StateProjectDir:
		if a.projectDirView != nil {
			content = a.projectDirView.Render()
		}
	case StateAnalysisConfig:
		if a.analysisConfigView != nil {
			content = a.analysisConfigView.Render()
		}
	case StateAnalyzing:
		if a.analyzingView != nil {
			content = a.analyzingView.Render()
		}
	case StateResults:
		if a.resultsView != nil {
			content = a.resultsView.Render()
		}
	case StateNextSteps:
		if a.nextStepsView != nil {
			content = a.nextStepsView.Render()
		}
	case StateError:
		if a.errorView != nil {
			content = a.errorView.Render()
		}
	case StateGame:
		if a.game != nil {
			content = lipgloss.Place(
				a.width,
				a.height,
				lipgloss.Center,
				lipgloss.Center,
				a.game.Render(),
			)
		}
	}

	// Safety: if a state rendered nothing (nil view), show a fallback
	if content == "" {
		content = lipgloss.Place(
			a.width,
			a.height,
			lipgloss.Center,
			lipgloss.Center,
			styles.Muted.Render("Loading..."),
		)
	}

	// Overlay help if visible
	if a.showHelp {
		helpItems := a.getCurrentHelpItems()
		a.helpOverlay.SetItems(helpItems)
		overlay := a.helpOverlay.Render(a.width, a.height)
		if overlay != "" {
			content = overlay
		}
	}

	return content
}

func (a *App) getCurrentHelpItems() []components.HelpItem {
	switch a.state {
	case StateWelcome:
		return a.welcomeView.GetHelpItems()
	case StateConfigCheck:
		if a.configCheckView != nil {
			return a.configCheckView.GetHelpItems()
		}
	case StateProviderSelect:
		return a.providerView.GetHelpItems()
	case StateModelSelect:
		if a.modelView != nil {
			return a.modelView.GetHelpItems()
		}
	case StateAuth:
		if a.authView != nil {
			return a.authView.GetHelpItems()
		}
	case StateAPIKey:
		if a.apiKeyView != nil {
			return a.apiKeyView.GetHelpItems()
		}
	case StateLocalModel:
		if a.localModelView != nil {
			return a.localModelView.GetHelpItems()
		}
	case StateProjectDir:
		if a.projectDirView != nil {
			return a.projectDirView.GetHelpItems()
		}
	case StateAnalysisConfig:
		if a.analysisConfigView != nil {
			return a.analysisConfigView.GetHelpItems()
		}
	case StateAnalyzing:
		if a.analyzingView != nil {
			return a.analyzingView.GetHelpItems()
		}
	case StateResults:
		if a.resultsView != nil {
			return a.resultsView.GetHelpItems()
		}
	case StateNextSteps:
		if a.nextStepsView != nil {
			return a.nextStepsView.GetHelpItems()
		}
	case StateError:
		if a.errorView != nil {
			return a.errorView.GetHelpItems()
		}
	}

	return components.NewHelpOverlay().Items
}

// ═══════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════

// populateSelectedFromConfig fills selectedProvider and selectedModel from
// the loaded config so that display names are available when the wizard is skipped.
func (a *App) populateSelectedFromConfig() {
	if p := config.GetProviderByID(a.configMgr.Config.Provider); p != nil {
		a.selectedProvider = p
		for i := range p.Models {
			if p.Models[i].ID == a.configMgr.Config.Model {
				a.selectedModel = &p.Models[i]
				break
			}
		}
	}
}

// buildEngineConfig creates an EngineConfig with properly resolved paths.
// OutputDir is resolved relative to ProjectDir so that output files are always
// written inside the user's chosen project directory.
func (a *App) buildEngineConfig() growth.EngineConfig {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}

	outputDir := a.configMgr.Config.OutputDir
	if outputDir == "" {
		outputDir = "./skene-context"
	}
	if !filepath.IsAbs(outputDir) {
		outputDir = filepath.Join(projectDir, outputDir)
	}

	return growth.EngineConfig{
		Provider:    a.configMgr.Config.Provider,
		Model:       a.configMgr.Config.Model,
		APIKey:      a.configMgr.Config.APIKey,
		BaseURL:     a.configMgr.Config.BaseURL,
		ProjectDir:  projectDir,
		OutputDir:   outputDir,
		UseGrowth: a.configMgr.Config.UseGrowth,
	}
}

func loadFileContent(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(data)
}

func tick() tea.Cmd {
	return tea.Tick(time.Millisecond*50, func(t time.Time) tea.Msg {
		return TickMsg(t)
	})
}

func checkForUpdate() tea.Cmd {
	return func() tea.Msg {
		return VersionCheckMsg{Result: versioncheck.Check()}
	}
}

func countdown(seconds int) tea.Cmd {
	return tea.Tick(time.Second, func(t time.Time) tea.Msg {
		return CountdownMsg(seconds)
	})
}
