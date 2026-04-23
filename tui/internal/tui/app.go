package tui

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"skene/internal/constants"
	"skene/internal/game"
	"skene/internal/services/auth"
	"skene/internal/services/config"
	"skene/internal/services/growth"
	"skene/internal/services/versioncheck"
	"skene/internal/services/visualizer"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"skene/internal/tui/views"

	"github.com/atotto/clipboard"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/pkg/browser"
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
	StateAnalyzing                      // Analysis progress
	StateResults                        // Results dashboard
	StateFileDetail                     // Single file detail view
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
	APIKey   string
	Model    string
	Upstream string
	Error    error
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
	analyzingView      *views.AnalyzingView
	resultsView        *views.ResultsView
	fileDetailView     *views.FileDetailView
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
	analyzingOrigin  AppState // state to return to when cancelling/failing
	journeyAnalysis  bool     // true when running analyse-journey (auto-opens visualizer)

	// Visualizer
	visualizerServer *visualizer.Server

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
		configMgr.Config.OutputDir = constants.DefaultOutputDir
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
						phase = constants.StatusInProgress
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
			if a.analyzingView != nil {
				a.analyzingView.SetCommandFailed("")
			}
		} else {
			if a.analyzingView != nil {
				a.analyzingView.SetDone()
			}
			a.resultsView = a.createResultsView()
			a.resultsView.SetSize(a.width, a.height)
			if a.state != StateGame && a.analyzingOrigin == StateProjectDir {
				if a.journeyAnalysis {
					if a.engineFileExists() {
						a.projectDirView.SetNoSchemaDetected(false)
						a.openEngineVisualizerIfExists()
					} else {
						a.projectDirView.SetNoSchemaDetected(true)
					}
				} else {
					a.projectDirView.SetNoSchemaDetected(false)
				}
				a.returnToProjectDirWithExisting()
			}
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
				currentPhase = constants.StatusInProgress
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
			if a.authView != nil {
				a.authView.ShowFallback()
			}
		} else {
			a.configMgr.SetAPIKey(msg.APIKey)
			a.configMgr.SetUpstreamAPIKey(msg.APIKey)
			a.configMgr.SetModel(constants.SkeneDefaultModel)
			if msg.Upstream != "" {
				a.configMgr.SetUpstream(buildUpstreamURL(msg.Upstream))
			}

			if a.authView != nil {
				a.authView.SetAuthState(views.AuthStateVerifying)
			}

			if a.callbackServer != nil {
				a.callbackServer.Shutdown()
				a.callbackServer = nil
			}

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
	case StateAnalyzing:
		return a.handleAnalyzingKeys(key)
	case StateResults:
		return a.handleResultsKeys(key)
	case StateFileDetail:
		return a.handleFileDetailKeys(key)
	case StateNextSteps:
		return a.handleResultsKeys(key)
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
	case "c":
		if a.welcomeView != nil && a.welcomeView.HasUpdate() {
			if clipboard.WriteAll(a.welcomeView.GetUpdateCmd()) == nil {
				a.welcomeView.SetCopied()
			}
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
		if a.projectDirView.IsShowingNextSteps() {
			return a.handleProjectDirNextStepsKeys(key)
		}
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
				a.openEngineVisualizerIfExists()
			case constants.ProjectDirRerunAnalysis, constants.ProjectDirRunAnalysis:
				a.projectDirView.SetNoSchemaDetected(false)
				return a.startJourneyAnalysis()
			case constants.ProjectDirRunCodebaseAnalysis:
				a.projectDirView.SetNoSchemaDetected(false)
				cmd := a.startCodebaseAnalysis()
				a.analyzingOrigin = StateProjectDir
				return cmd
			}
		case "n":
			outputDir := filepath.Join(a.projectDirView.GetProjectDir(), constants.OutputDirName)
			a.projectDirView.ShowNextSteps(outputDir)
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
				return a.startJourneyAnalysis()
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
					return a.startJourneyAnalysis()
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

func (a *App) handleProjectDirNextStepsKeys(key string) tea.Cmd {
	nsv := a.projectDirView.GetNextStepsView()
	switch key {
	case "up", "k":
		nsv.HandleUp()
	case "down", "j":
		nsv.HandleDown()
	case "enter":
		action := nsv.GetSelectedAction()
		if action == nil {
			return nil
		}
		a.projectDirView.HideNextSteps()
		a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
		switch action.ID {
		case "exit":
			return tea.Quit
		case "journey":
			a.projectDirView.SetNoSchemaDetected(false)
			return a.startJourneyAnalysis()
		case "rerun":
			a.projectDirView.SetNoSchemaDetected(false)
			cmd := a.startCodebaseAnalysis()
			a.analyzingOrigin = StateProjectDir
			return cmd
		case "plan":
			return a.runEngineCommand("Generating Growth Plan", "plan")
		case "build":
			return a.runEngineCommand("Building Implementation Prompt", "build")
		case "validate":
			return a.runEngineCommand("Validating Manifest", "validate")
		case "view-files":
			a.transitionToResultsFromExisting()
		case "open":
			outputDir := filepath.Join(a.projectDirView.GetProjectDir(), constants.OutputDirName)
			_ = browser.OpenURL(outputDir)
		case "config":
			a.configCheckView = nil
			a.apiKeyView = nil
			a.providerView = views.NewProviderView()
			a.providerView.SetSize(a.width, a.height)
			a.state = StateProviderSelect
		}
	case "esc":
		a.projectDirView.HideNextSteps()
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
		if a.analyzingView != nil {
			a.prevState = a.state
			a.state = StateGame
			if a.game == nil {
				a.game = game.NewGame(a.width, a.height)
			} else {
				a.game.Restart()
			}
			a.game.SetSize(a.width, a.height)
			if a.analyzingView.HasFailed() {
				a.game.SetProgressInfo("", true, true)
			} else if a.analyzingView.IsDone() {
				a.game.SetProgressInfo("", true, false)
			} else {
				currentPhase := a.analyzingView.GetCurrentPhase()
				if currentPhase == "" {
					currentPhase = constants.StatusInProgress
				}
				a.game.SetProgressInfo(currentPhase, false, false)
			}
			return game.GameTickCmd()
		}
	case "r":
		if a.analyzingView != nil && a.analyzingView.HasFailed() {
			return a.startJourneyAnalysis()
		}
	case "esc":
		if a.analyzingView == nil {
			return nil
		}
		if a.analyzingView.HasFailed() {
			a.navigateBackFromAnalyzing()
		} else if a.analyzingView.IsDone() {
			if a.resultsView != nil {
				a.refreshResultsView()
				a.state = StateResults
			} else {
				a.navigateBackFromAnalyzing()
			}
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
	if a.resultsView.IsShowingNextSteps() {
		return a.handleNextStepsModalKeys(key)
	}
	switch key {
	case "up", "k":
		a.resultsView.HandleUp()
	case "down", "j":
		a.resultsView.HandleDown()
	case "enter":
		selected := a.resultsView.GetSelectedFile()
		if selected != nil {
			if selected.ID == "engine" {
				a.openYAMLVisualizer(selected)
			} else {
				a.openFileDetail(selected)
			}
		}
	case "n":
		a.resultsView.ShowNextSteps()
	case "esc":
		a.returnToProjectDirWithExisting()
	}
	return nil
}

func (a *App) handleNextStepsModalKeys(key string) tea.Cmd {
	nsv := a.resultsView.GetNextStepsView()
	switch key {
	case "up", "k":
		nsv.HandleUp()
	case "down", "j":
		nsv.HandleDown()
	case "enter":
		action := nsv.GetSelectedAction()
		if action == nil {
			return nil
		}
		a.resultsView.HideNextSteps()
		switch action.ID {
		case "exit":
			return tea.Quit
		case "journey":
			return a.startSimpleAnalysis()
		case "rerun":
			return a.startCodebaseAnalysis()
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
		case "view-files":
			// Already on the dashboard — just close the modal.
		case "open":
			projectDir := a.configMgr.Config.ProjectDir
			if projectDir == "" {
				projectDir, _ = os.Getwd()
			}
			outputDir := filepath.Join(projectDir, constants.OutputDirName)
			_ = browser.OpenURL(outputDir)
		}
	case "esc":
		a.resultsView.HideNextSteps()
	}
	return nil
}

func (a *App) openFileDetail(def *constants.DashboardFile) {
	outputDir := a.getOutputDir()
	a.fileDetailView = views.NewFileDetailView(*def, outputDir)
	a.fileDetailView.SetSize(a.width, a.height)
	a.state = StateFileDetail
}

func (a *App) openEngineVisualizerIfExists() {
	engineDef := &constants.DashboardFile{
		ID:          "engine",
		DisplayName: "Growth Features",
		Filename:    constants.EngineFile,
	}
	a.openYAMLVisualizer(engineDef)
}

// engineFileExists reports whether engine.yaml is present in the output dir.
func (a *App) engineFileExists() bool {
	_, err := os.Stat(filepath.Join(a.getOutputDir(), constants.EngineFile))
	return err == nil
}

func (a *App) openYAMLVisualizer(def *constants.DashboardFile) {
	filePath := filepath.Join(a.getOutputDir(), def.Filename)
	if _, err := os.Stat(filePath); err != nil {
		return
	}

	if a.visualizerServer != nil {
		a.visualizerServer.Stop()
	}

	a.visualizerServer = visualizer.NewServer(filePath, def.DisplayName)
	url, err := a.visualizerServer.Start()
	if err != nil {
		return
	}
	_ = browser.OpenURL(url)
}

func (a *App) handleFileDetailKeys(key string) tea.Cmd {
	switch key {
	case "up", "k":
		a.fileDetailView.HandleUp()
	case "down", "j":
		a.fileDetailView.HandleDown()
	case "esc":
		a.refreshResultsView()
		a.state = StateResults
	}
	return nil
}

func (a *App) getOutputDir() string {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}
	return filepath.Join(projectDir, constants.OutputDirName)
}

func (a *App) getProjectName() string {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}
	if projectDir == "." || projectDir == "./" {
		return "./"
	}
	return "./" + filepath.Base(projectDir)
}

func (a *App) createResultsView() *views.ResultsView {
	rv := views.NewResultsView(a.getProjectName(), a.getOutputDir())
	return rv
}

func (a *App) handleErrorKeys(key string) tea.Cmd {
	switch key {
	case "r":
		if a.errorView != nil && a.errorView.IsRetryable() {
			a.state = a.prevState
		}
	case "esc":
		a.navigateBackFromError()
	}
	return nil
}

func (a *App) handleGameKeys(msg tea.KeyMsg) tea.Cmd {
	key := msg.String()
	switch key {
	case "up":
		a.game.MoveUp()
	case "down":
		a.game.MoveDown()
	case "enter":
		a.game.Start()
	case "r":
		if a.game.IsGameOver() {
			a.game.Start()
		}
	case "esc":
		if a.game != nil {
			a.game.ClearProgressInfo()
		}
		if a.prevState == StateAnalyzing && a.resultsView != nil && a.analyzingView != nil && a.analyzingView.IsDone() && !a.analyzingView.HasFailed() && a.analyzingOrigin == StateProjectDir {
			if a.journeyAnalysis {
				if a.engineFileExists() {
					a.projectDirView.SetNoSchemaDetected(false)
					a.openEngineVisualizerIfExists()
				} else {
					a.projectDirView.SetNoSchemaDetected(true)
				}
			} else {
				a.projectDirView.SetNoSchemaDetected(false)
			}
			a.returnToProjectDirWithExisting()
		} else {
			a.state = a.prevState
		}
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

		authBaseURL := resolveSkeneAuthURL()
		authURL := fmt.Sprintf("%s?callback=%s", authBaseURL, url.QueryEscape(callbackServer.GetCallbackURL()))

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

func (a *App) returnToProjectDirWithExisting() {
	if a.projectDirView != nil {
		a.projectDirView.ResetExistingChoice()
		a.projectDirView.SetSize(a.width, a.height)
	}
	a.state = StateProjectDir
}

func (a *App) transitionToResultsFromExisting() {
	a.resultsView = a.createResultsView()
	a.resultsView.SetSize(a.width, a.height)
	a.state = StateResults
}

func (a *App) refreshResultsView() {
	if a.resultsView == nil {
		return
	}
	a.resultsView.RefreshContent(a.getOutputDir())
}

func (a *App) applyJourneyConfig() {
	a.configMgr.Config.UseGrowth = true
	a.configMgr.Config.Verbose = true
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
		a.state = StateResults
	case StateProjectDir:
		a.returnToProjectDirWithExisting()
	default:
		a.returnToProjectDirWithExisting()
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
	}
	a.state = target
}

// ═══════════════════════════════════════════════════════════════════
// ASYNC OPERATIONS
// ═══════════════════════════════════════════════════════════════════

func (a *App) startJourneyAnalysis() tea.Cmd {
	a.applyJourneyConfig()
	a.journeyAnalysis = true
	a.analyzingView = views.NewCommandView(constants.StepNameJourneyAnalysis)
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateProjectDir
	a.state = StateAnalyzing
	return a.startSimpleAnalysisCmd(a.program)
}

func (a *App) startCodebaseAnalysis() tea.Cmd {
	a.journeyAnalysis = false
	a.analyzingView = views.NewCommandView(constants.StepNameCodebaseAnalysis)
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateNextSteps
	a.state = StateAnalyzing
	return a.startRealAnalysisCmd(a.program)
}

func (a *App) startSimpleAnalysis() tea.Cmd {
	a.journeyAnalysis = true
	a.analyzingView = views.NewCommandView(constants.StepNameJourneyAnalysis)
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateNextSteps
	a.state = StateAnalyzing
	return a.startSimpleAnalysisCmd(a.program)
}

func (a *App) startSimpleAnalysisCmd(p *tea.Program) tea.Cmd {
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

		result := engine.RunJourney(ctx)
		if result.Error != nil {
			return AnalysisDoneMsg{Error: result.Error, Result: result}
		}
		return AnalysisDoneMsg{Error: nil, Result: result}
	}
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
	a.analyzingOrigin = StateProjectDir
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
			APIKey:   result.APIKey,
			Model:    result.Model,
			Upstream: result.Upstream,
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
	if a.analyzingView != nil {
		a.analyzingView.SetSize(a.width, a.height)
	}
	if a.resultsView != nil {
		a.resultsView.SetSize(a.width, a.height)
	}
	if a.fileDetailView != nil {
		a.fileDetailView.SetSize(a.width, a.height)
	}
	if a.nextStepsView != nil {
		a.nextStepsView.SetSize(a.width, a.height)
	}
	if a.errorView != nil {
		a.errorView.SetSize(a.width, a.height)
	}
	if a.game != nil {
		a.game.SetSize(a.width, a.height)
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
	case StateAnalyzing:
		if a.analyzingView != nil {
			content = a.analyzingView.Render()
		}
	case StateResults:
		if a.resultsView != nil {
			content = a.resultsView.Render()
		}
	case StateFileDetail:
		if a.fileDetailView != nil {
			content = a.fileDetailView.Render()
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
	case StateAnalyzing:
		if a.analyzingView != nil {
			return a.analyzingView.GetHelpItems()
		}
	case StateResults:
		if a.resultsView != nil {
			return a.resultsView.GetHelpItems()
		}
	case StateFileDetail:
		if a.fileDetailView != nil {
			return a.fileDetailView.GetHelpItems()
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
		outputDir = constants.DefaultOutputDir
	}
	if !filepath.IsAbs(outputDir) {
		outputDir = filepath.Join(projectDir, outputDir)
	}

	cfg := a.configMgr.Config

	ec := growth.EngineConfig{
		Provider:       cfg.Provider,
		Model:          cfg.Model,
		APIKey:         cfg.APIKey,
		BaseURL:        cfg.BaseURL,
		ProjectDir:     projectDir,
		OutputDir:      outputDir,
		UseGrowth:      cfg.UseGrowth,
		Upstream:       cfg.Upstream,
		UpstreamAPIKey: cfg.UpstreamAPIKey,
	}

	if cfg.Provider == "skene" {
		ec.Model = constants.SkeneDefaultModel
		ec.BaseURL = skeneBaseURL()
		ec.APIKey = resolveSkeneAPIKey(cfg)
		ec.UpstreamAPIKey = ec.APIKey
	}

	return ec
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

// isSkeneTestMode returns true when SKENE_TEST_MODE=1.
func isSkeneTestMode() bool {
	return os.Getenv("SKENE_TEST_MODE") == "1"
}

// resolveSkeneAuthURL returns the auth base URL.
// Priority: SKENE_AUTH_URL env → test mode (localhost:3000) → production.
func resolveSkeneAuthURL() string {
	if envURL := os.Getenv("SKENE_AUTH_URL"); envURL != "" {
		return envURL
	}
	if isSkeneTestMode() {
		return constants.SkeneTestAuthURL
	}
	return constants.SkeneAuthURL
}

// buildUpstreamURL constructs the full upstream URL from a workspace slug.
// If the slug is already a full URL it is returned as-is.
func buildUpstreamURL(slug string) string {
	if strings.HasPrefix(slug, "http://") || strings.HasPrefix(slug, "https://") {
		return slug
	}
	base := "https://www.skene.ai"
	if isSkeneTestMode() {
		base = "http://localhost:3000"
	}
	return base + "/workspace/" + slug
}

// skeneBaseURL returns the Skene API base URL for the Python CLI.
// The SkeneClient appends /chat/completions itself.
func skeneBaseURL() string {
	if isSkeneTestMode() {
		return "http://localhost:3000/api/v1"
	}
	return "https://www.skene.ai/api/v1"
}

// Cleanup releases resources held by the app (e.g. background servers).
// Call after the Bubble Tea program exits.
func (a *App) Cleanup() {
	if a.visualizerServer != nil {
		a.visualizerServer.Stop()
		a.visualizerServer = nil
	}
}

// resolveSkeneAPIKey picks the API key for the skene provider.
// Priority: UpstreamAPIKey → APIKey → SKENE_UPSTREAM_API_KEY env.
func resolveSkeneAPIKey(cfg *config.Config) string {
	if cfg.UpstreamAPIKey != "" {
		return cfg.UpstreamAPIKey
	}
	if cfg.APIKey != "" {
		return cfg.APIKey
	}
	return os.Getenv("SKENE_UPSTREAM_API_KEY")
}
