package tui

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"skene/internal/constants"
	"skene/internal/game"
	"skene/internal/outputdirs"
	"skene/internal/services/auth"
	"skene/internal/services/backend"
	"skene/internal/services/config"
	"skene/internal/services/growth"
	"skene/internal/services/telemetry"
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
	Error error
}

// JourneyProgressMsg carries structured progress from a server-driven
// journey run. Phase (optional) names the coarse step; Message is a
// per-agent/per-tool log line.
type JourneyProgressMsg struct {
	Phase   string
	Message string
}

// NextStepOutputMsg is sent when a next-step command produces output
type NextStepOutputMsg struct {
	Line string
}

// NextStepDoneMsg is sent when a next-step command finishes
type NextStepDoneMsg struct {
	Error error
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
	telemetry *telemetry.Client

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

	// Backend skene server (spawned lazily for journey analysis and the
	// journey visualizer; nil until first needed)
	backendMu     sync.Mutex
	backendServer *backend.Server

	// Auth state
	authCountdown  int
	callbackServer *auth.CallbackServer

	// Push flow — when the user triggers "Deploy to Skene Cloud" without
	// a stored upstream token, we route through the Skene magic-link auth
	// flow first and then automatically run the push.
	pendingPushAfterAuth bool
	pushReturnState      AppState

	// Error state
	currentError *views.ErrorInfo

	// Telemetry: last view name for exit event
	lastView string

	// Telemetry: command currently being executed via runPushCommand
	// ("push"). Used to fire deployment_completed vs deployment_failed
	// when NextStepDoneMsg arrives.
	currentNextStepCommand string

	// Telemetry: timestamp when the current next-step command started,
	// used to attach a duration to its completion event.
	currentNextStepStart time.Time

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

	tc := telemetry.NewClient(configMgr.Config.TelemetryEnabled)
	wv := views.NewWelcomeView()
	wv.SetTelemetryEnabled(configMgr.Config.TelemetryEnabled)

	app := &App{
		state:        StateWelcome,
		configMgr:    configMgr,
		telemetry:    tc,
		welcomeView:  wv,
		providerView: views.NewProviderView(),
		helpOverlay:  components.NewHelpOverlay(),
	}

	tc.Track(constants.EventTUIOpened, nil)

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
			// Real analysis progress is updated via JourneyProgressMsg
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
		cancelled := errors.Is(err, context.Canceled)
		if err != nil && !cancelled {
			a.telemetry.Track(constants.EventAnalysisFailed, nil)
		} else if err == nil {
			elapsed := time.Since(a.analysisStartTime).Truncate(time.Second).String()
			a.telemetry.Track(constants.EventAnalysisCompleted, map[string]string{
				"duration": elapsed,
			})
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
				// The message matters: e.g. a provider quota error looks
				// identical to any other failure without it.
				a.analyzingView.SetCommandFailed(err.Error())
			}
		} else {
			if a.analyzingView != nil {
				a.analyzingView.SetDone()
			}
			a.resultsView = a.createResultsView()
			a.resultsView.SetSize(a.width, a.height)
			if a.state != StateGame && a.analyzingOrigin == StateProjectDir {
				if a.journeyAnalysis {
					if a.userJourneyFileExists() {
						a.projectDirView.SetNoSchemaDetected(false)
						a.openJourneyVisualizerIfExists()
					} else {
						a.projectDirView.SetNoSchemaDetected(true)
					}
				} else {
					a.projectDirView.SetNoSchemaDetected(false)
				}
				a.returnToProjectDirWithExisting()
			}
		}

	case NextStepOutputMsg:
		if a.analyzingView != nil {
			a.analyzingView.UpdatePhase(-1, 0, msg.Line)
		}

	case JourneyProgressMsg:
		if a.analyzingView != nil {
			if msg.Phase != "" {
				a.analyzingView.UpdatePhaseByName(msg.Phase, 0.5, msg.Message)
			} else {
				a.analyzingView.UpdatePhase(-1, 0, msg.Message)
			}
		}
		// Update game progress if game is active
		if a.state == StateGame && a.game != nil && a.analyzingView != nil {
			currentPhase := a.analyzingView.GetCurrentPhase()
			if currentPhase == "" {
				currentPhase = constants.StatusInProgress
			}
			a.game.SetProgressInfo(currentPhase, false, false)
		}

	case NextStepDoneMsg:
		if a.analyzingView != nil {
			if msg.Error != nil {
				a.analyzingView.SetCommandFailed(msg.Error.Error())
			} else {
				a.analyzingView.SetDone()
			}
		}
		duration := time.Since(a.currentNextStepStart).Truncate(time.Second).String()
		var evOK, evFail string
		if a.currentNextStepCommand == "push" {
			evOK, evFail = constants.EventDeploymentCompleted, constants.EventDeploymentFailed
		}
		if evOK != "" && !errors.Is(msg.Error, context.Canceled) {
			if msg.Error != nil {
				a.telemetry.Track(evFail, map[string]string{"duration": duration})
			} else {
				a.telemetry.Track(evOK, map[string]string{"duration": duration})
			}
		}
		a.currentNextStepCommand = ""
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
			a.telemetry.Track(constants.EventAuthFallbackUsed, map[string]string{"trigger": "callback_error"})
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
		a.telemetry.Track(constants.EventAuthSucceeded, nil)
		if a.pendingPushAfterAuth {
			a.pendingPushAfterAuth = false
			origin := a.pushReturnState
			cmds = append(cmds, a.runPushCommand())
			// Override analyzingOrigin if we came from project-dir so
			// back-navigation doesn't try to land on a nil resultsView.
			if origin == StateProjectDir {
				a.analyzingOrigin = StateProjectDir
			}
		} else {
			a.transitionToProjectDir()
		}

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
		// Always reload from disk so the ConfigCheck screen reflects the
		// saved configuration, not whatever the user touched in memory
		// during an abandoned Reconfigure flow. Also discard any
		// half-built views from that flow so later back-navigation
		// (e.g. from StateProjectDir) doesn't land on a stale API key
		// or model screen that belongs to a provider the user backed
		// out of.
		_ = a.configMgr.ReloadConfig()
		a.selectedProvider = nil
		a.selectedModel = nil
		a.apiKeyView = nil
		a.modelView = nil
		a.localModelView = nil
		a.authView = nil
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
			a.trackView("config_check", map[string]string{"has_valid_config": "true"})
		} else {
			a.state = StateProviderSelect
			a.providerView.SetSize(a.width, a.height)
			a.trackView("provider_select", nil)
		}
		return nil
	case "t":
		newState := !a.configMgr.Config.TelemetryEnabled
		// Force-enable the client before tracking so both opt-in
		// and opt-out events reach the server; the real state is
		// applied immediately after.
		a.telemetry.SetEnabled(true)
		a.telemetry.Track(constants.EventTelemetryToggled, map[string]string{
			"enabled": fmt.Sprintf("%t", newState),
		})
		a.configMgr.SetTelemetryEnabled(newState)
		a.telemetry.SetEnabled(newState)
		if a.welcomeView != nil {
			a.welcomeView.SetTelemetryEnabled(newState)
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
			a.telemetry.Track(constants.EventConfigReused, map[string]string{
				"provider": a.configMgr.Config.Provider,
				"model":    a.configMgr.Config.Model,
			})
			a.transitionToProjectDir()
		} else {
			a.telemetry.Track(constants.EventConfigReconfigured, nil)
			a.state = StateProviderSelect
			a.providerView.SetSize(a.width, a.height)
			a.trackView("provider_select", nil)
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
		a.telemetry.Track(constants.EventAuthFallbackUsed, map[string]string{"trigger": "manual"})
	
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
		if a.pendingPushAfterAuth {
			a.pendingPushAfterAuth = false
			returnState := a.pushReturnState
			if returnState == StateResults && a.resultsView == nil {
				returnState = StateProjectDir
			}
			if returnState == StateProjectDir && a.projectDirView == nil {
				returnState = StateWelcome
			}
			if returnState != StateResults && returnState != StateProjectDir {
				returnState = StateWelcome
			}
			a.state = returnState
			return nil
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
			a.telemetry.Track(constants.EventExistingAnalysisAction, map[string]string{
				"action": choice,
			})
			switch choice {
			case constants.ProjectDirViewAnalysis:
				a.openJourneyVisualizerIfExists()
			case constants.ProjectDirRerunAnalysis, constants.ProjectDirRunAnalysis:
				a.projectDirView.SetNoSchemaDetected(false)
				return a.startJourneyAnalysis()
			case constants.ProjectDirDeployToCloud:
				return a.startPushFlow(StateProjectDir)
			}
		case "n":
			pd := a.projectDirView.GetProjectDir()
			rel := a.configMgr.Config.OutputDir
			if rel == "" {
				rel = constants.DefaultOutputDir
			}
			a.projectDirView.ShowNextSteps(
				outputdirs.Bundle(pd),
				outputdirs.Context(pd, rel),
			)
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
					a.trackView("project_dir_existing", nil)
					return nil
				}
				a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
				a.telemetry.Track(constants.EventProjectDirSelected, nil)
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
						a.trackView("project_dir_existing", nil)
						return nil
					}
					a.configMgr.SetProjectDir(a.projectDirView.GetProjectDir())
					a.telemetry.Track(constants.EventProjectDirSelected, nil)
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
		case "push":
			return a.startPushFlow(StateProjectDir)
		case "view-files":
			a.transitionToResultsFromExisting()
		case "open":
			outputDir := filepath.Join(a.projectDirView.GetProjectDir(), constants.OutputDirName)
			_ = browser.OpenURL(outputDir)
			a.telemetry.Track(constants.EventOutputDirOpened, map[string]string{
				"source": "project_dir",
			})
		case "config":
			a.configCheckView = nil
			a.apiKeyView = nil
			a.providerView = views.NewProviderView()
			a.providerView.SetSize(a.width, a.height)
			a.state = StateProviderSelect
			a.trackView("provider_select", nil)
		}
	case "esc":
		a.projectDirView.HideNextSteps()
	}
	return nil
}

func (a *App) handleAnalyzingKeys(key string) tea.Cmd {
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
			a.trackView("game", nil)
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
			a.telemetry.Track(constants.EventAnalysisRetried, nil)
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
				a.trackView("results", nil)
			} else {
				a.navigateBackFromAnalyzing()
			}
		} else {
			if a.currentNextStepCommand != "" {
				a.telemetry.Track(constants.EventNextStepCancelled, map[string]string{
					"command": a.currentNextStepCommand,
				})
				a.currentNextStepCommand = ""
			} else {
				analysisType := "codebase"
				if a.journeyAnalysis {
					analysisType = "journey"
				}
				a.telemetry.Track(constants.EventAnalysisCancelled, map[string]string{
					"type": analysisType,
				})
			}
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
	if a.resultsView == nil {
		// Nothing to render — bounce back to a safe state.
		if a.projectDirView != nil {
			a.returnToProjectDirWithExisting()
		} else {
			a.state = StateWelcome
		}
		return nil
	}
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
			if selected.ID == "user-journey" {
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
		case "config":
			a.configCheckView = nil
			a.apiKeyView = nil
			a.providerView = views.NewProviderView()
			a.providerView.SetSize(a.width, a.height)
			a.state = StateProviderSelect
			a.trackView("provider_select", nil)
		case "push":
			return a.startPushFlow(StateResults)
		case "view-files":
			// Already on the dashboard — just close the modal.
		case "open":
			projectDir := a.configMgr.Config.ProjectDir
			if projectDir == "" {
				projectDir, _ = os.Getwd()
			}
			outputDir := filepath.Join(projectDir, constants.OutputDirName)
			_ = browser.OpenURL(outputDir)
			a.telemetry.Track(constants.EventOutputDirOpened, map[string]string{
				"source": "results",
			})
		}
	case "esc":
		a.resultsView.HideNextSteps()
	}
	return nil
}

func (a *App) openFileDetail(def *constants.DashboardFile) {
	a.fileDetailView = views.NewFileDetailView(*def, a.getBundleOutputDir(), a.getContextOutputDir())
	a.fileDetailView.SetSize(a.width, a.height)
	a.state = StateFileDetail
	a.trackView("file_detail", map[string]string{"file_id": def.ID})
}

func (a *App) openJourneyVisualizerIfExists() {
	journeyDef := &constants.DashboardFile{
		ID:          "journey",
		DisplayName: "Journey",
		Filename:    constants.JourneyFile,
	}
	a.openYAMLVisualizer(journeyDef)
}

// userJourneyFileExists reports whether journey.yaml is present in the
// bundle or context directory.
func (a *App) userJourneyFileExists() bool {
	primary := filepath.Join(a.getBundleOutputDir(), constants.JourneyFile)
	if _, err := os.Stat(primary); err == nil {
		return true
	}
	ctx := filepath.Join(a.getContextOutputDir(), constants.JourneyFile)
	_, err := os.Stat(ctx)
	return err == nil
}

func (a *App) openYAMLVisualizer(def *constants.DashboardFile) {
	filePath := views.ResolveDashboardFilePath(*def, a.getBundleOutputDir(), a.getContextOutputDir())
	if _, err := os.Stat(filePath); err != nil {
		return
	}

	if a.visualizerServer != nil {
		a.visualizerServer.Stop()
	}

	if def.Filename == constants.JourneyFile {
		// The journey visualizer reads the server's GET /journey instead of
		// parsing journey.yaml itself.
		a.visualizerServer = visualizer.NewServer(def.DisplayName, a.journeyDataSource())
	} else {
		a.visualizerServer = visualizer.NewFileServer(filePath, def.DisplayName)
	}
	url, err := a.visualizerServer.Start()
	if err != nil {
		return
	}
	_ = browser.OpenURL(url)
	a.telemetry.Track(constants.EventVisualizerOpened, nil)
}

// journeyDataSource returns a visualizer data source that serves the parsed
// journey from the skene server (spawning it on first use). It captures the
// current project directory; runs on visualizer HTTP handler goroutines.
func (a *App) journeyDataSource() visualizer.DataFunc {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}
	cfg := a.buildBackendConfig()

	return func() (interface{}, error) {
		server, err := a.ensureBackend(context.Background(), cfg, nil)
		if err != nil {
			return nil, err
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		return server.JourneyJSON(ctx, projectDir)
	}
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

func (a *App) getBundleOutputDir() string {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}
	return outputdirs.Bundle(projectDir)
}

func (a *App) getContextOutputDir() string {
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}
	rel := a.configMgr.Config.OutputDir
	if rel == "" {
		rel = constants.DefaultOutputDir
	}
	return outputdirs.Context(projectDir, rel)
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
	rv := views.NewResultsView(a.getProjectName(), a.getBundleOutputDir(), a.getContextOutputDir())
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
				if a.userJourneyFileExists() {
					a.projectDirView.SetNoSchemaDetected(false)
					a.openJourneyVisualizerIfExists()
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
	a.telemetry.Track(constants.EventProviderSelected, map[string]string{
		"provider": provider.ID,
	})

	// Branch based on provider type
	if provider.ID == "skene" {
		return a.startSkeneAuth(provider)
	}

	if provider.IsLocal {
		// Local model: detect runtime
		a.localModelView = views.NewLocalModelView(provider.ID)
		a.localModelView.SetSize(a.width, a.height)
		a.state = StateLocalModel
		a.trackView("local_model", map[string]string{"provider": provider.ID})
		return a.detectLocalModels()
	}

	// Regular providers: go to model selection
	a.modelView = views.NewModelView(provider)
	a.modelView.SetSize(a.width, a.height)
	a.state = StateModelSelect
	a.trackView("model_select", map[string]string{"provider": provider.ID})
	return nil
}

// startSkeneAuth spins up the magic-link callback server and transitions
// the TUI into StateAuth. Extracted from selectProvider so flows other
// than provider selection (e.g. the push-with-no-token flow) can reuse it.
func (a *App) startSkeneAuth(provider *config.Provider) tea.Cmd {
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
	a.trackView("auth", map[string]string{
		"is_push_flow": fmt.Sprintf("%t", a.pendingPushAfterAuth),
	})
	return tea.Batch(countdown(3), a.waitForAuthCallback())
}

// startPushFlow kicks off a "Deploy to Skene Cloud" action from the
// next-steps modal. If the user already has an upstream token stored
// in their config we run `uvx skene push` immediately; otherwise we
// route through the Skene magic-link auth flow and auto-run the push
// once authentication succeeds.
func (a *App) startPushFlow(origin AppState) tea.Cmd {
	if a.configMgr.Config.UpstreamAPIKey == "" || a.configMgr.Config.Upstream == "" {
		a.pendingPushAfterAuth = true
		a.pushReturnState = origin

		a.selectedProvider = config.GetProviderByID("skene")
		if a.selectedProvider != nil {
			a.configMgr.SetProvider(a.selectedProvider.ID)
		}

		return a.startSkeneAuth(a.selectedProvider)
	}

	cmd := a.runPushCommand()
	// runPushCommand hardcodes analyzingOrigin = StateProjectDir, which
	// makes navigateBackFromAnalyzing return to the project-dir prompt.
	// That is what we want regardless of whether Deploy was triggered
	// from the results dashboard or the project-dir modal, but keep the
	// explicit override for the project-dir case so back-navigation never
	// lands on a nil resultsView.
	if origin == StateProjectDir {
		a.analyzingOrigin = StateProjectDir
	}
	return cmd
}

func (a *App) selectModel() {
	model := a.modelView.GetSelectedModel()
	if model == nil {
		return
	}

	a.selectedModel = model
	a.configMgr.SetModel(model.ID)
	a.telemetry.Track(constants.EventModelSelected, map[string]string{
		"model": model.ID,
	})

	// Go to API key entry
	a.transitionToAPIKey()
}

func (a *App) transitionToAPIKey() {
	a.apiKeyView = views.NewAPIKeyView(a.selectedProvider, a.selectedModel)
	a.apiKeyView.SetSize(a.width, a.height)
	a.state = StateAPIKey
	providerID := ""
	if a.selectedProvider != nil {
		providerID = a.selectedProvider.ID
	}
	a.trackView("api_key", map[string]string{"provider": providerID})
}

func (a *App) transitionToProjectDir() {
	_ = a.configMgr.SaveUserConfig()
	a.trackView("project_dir", nil)
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
	if a.projectDirView != nil && a.projectDirView.IsAskingExistingChoice() {
		a.trackView("project_dir_existing", nil)
	} else {
		a.trackView("project_dir", nil)
	}
}

func (a *App) transitionToResultsFromExisting() {
	a.resultsView = a.createResultsView()
	a.resultsView.SetSize(a.width, a.height)
	a.state = StateResults
	a.trackView("results", nil)
}

func (a *App) refreshResultsView() {
	if a.resultsView == nil {
		return
	}
	a.resultsView.RefreshContent(a.getBundleOutputDir(), a.getContextOutputDir())
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
		if a.resultsView == nil {
			a.returnToProjectDirWithExisting()
			return
		}
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
	a.telemetry.Track(constants.EventAnalysisStarted, map[string]string{
		"type": "journey",
	})
	a.analyzingView = views.NewCommandView(constants.StepNameJourneyAnalysis)
	a.analyzingView.SetSize(a.width, a.height)
	a.analysisStartTime = time.Now()
	a.analyzingOrigin = StateProjectDir
	a.state = StateAnalyzing
	return a.startSimpleAnalysisCmd(a.program)
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

// startSimpleAnalysisCmd runs the journey analysis through the skene server:
// it ensures a server is up, POSTs /journey/analyse, and renders the SSE
// event stream as structured per-agent progress. Cancelling aborts the whole
// child-session tree server-side.
func (a *App) startSimpleAnalysisCmd(p *tea.Program) tea.Cmd {
	cfg := a.buildBackendConfig()
	projectDir := a.configMgr.Config.ProjectDir
	if projectDir == "" {
		projectDir, _ = os.Getwd()
	}

	ctx, cancel := context.WithCancel(context.Background())
	a.cancelFunc = cancel

	return func() tea.Msg {
		defer cancel()
		send := func(phase, message string) {
			if p != nil {
				p.Send(JourneyProgressMsg{Phase: phase, Message: message})
			}
		}

		server, err := a.ensureBackend(ctx, cfg, func(line string) { send("", line) })
		if err != nil {
			if ctx.Err() != nil {
				err = ctx.Err()
			}
			return AnalysisDoneMsg{Error: err}
		}

		result := server.RunJourney(ctx, projectDir, func(update backend.Update) {
			send(update.Phase, update.Message)
		})
		if result.Milestones > 0 {
			send("", fmt.Sprintf("%d candidate milestones collected", result.Milestones))
		}
		if result.Err != nil && result.ArtifactPath != "" && ctx.Err() == nil {
			// The deliverable exists — e.g. the agent's closing turn hit a
			// provider error after finalize_journey had already written the
			// artifact. Surface the error but finish as a success so the
			// results flow (visualizer auto-open) still happens.
			send("", "⚠ run ended with an error after journey.yaml was written: "+result.Err.Error())
			return AnalysisDoneMsg{}
		}
		return AnalysisDoneMsg{Error: result.Err}
	}
}

// buildBackendConfig maps the wizard configuration to the LLM settings the
// spawned skene server needs.
func (a *App) buildBackendConfig() backend.Config {
	ec := a.buildEngineConfig()
	return backend.Config{
		Provider: ec.Provider,
		Model:    ec.Model,
		APIKey:   ec.APIKey,
		BaseURL:  ec.BaseURL,
	}
}

// ensureBackend returns the shared backend server, spawning it on first use.
// Safe to call from tea.Cmd and HTTP-handler goroutines.
func (a *App) ensureBackend(ctx context.Context, cfg backend.Config, onStatus func(string)) (*backend.Server, error) {
	a.backendMu.Lock()
	defer a.backendMu.Unlock()
	if a.backendServer != nil {
		return a.backendServer, nil
	}
	server, err := backend.Connect(ctx, cfg, onStatus)
	if err != nil {
		return nil, err
	}
	a.backendServer = server
	return server, nil
}

// runPushCommand spawns `uvx skene push` (the only remaining uvx-based
// next-step command) and streams its output into the analyzing view.
func (a *App) runPushCommand() tea.Cmd {
	a.telemetry.Track(constants.EventNextStepTriggered, map[string]string{
		"command": "push",
	})
	a.currentNextStepCommand = "push"
	a.currentNextStepStart = time.Now()
	a.telemetry.Track(constants.EventDeploymentStarted, nil)
	a.analyzingView = views.NewCommandView(constants.NextStepPushTitle)
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

		engine := growth.NewEngine(cfg, func(line string) {
			if p != nil {
				p.Send(NextStepOutputMsg{Line: line})
			}
		})

		if p != nil {
			p.Send(NextStepOutputMsg{Line: constants.NextStepPushRunning})
		}
		return NextStepDoneMsg{Error: engine.Push()}
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
	a.trackView("error", map[string]string{"error_code": err.Code})
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

// trackView fires a view_entered event and records the view name for the
// exit event. Pass nil props for views with no extra context.
func (a *App) trackView(view string, props map[string]string) {
	a.lastView = view
	if props == nil {
		props = map[string]string{}
	}
	props["view"] = view
	a.telemetry.Track(constants.EventViewEntered, props)
}

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

	rel := a.configMgr.Config.OutputDir
	if rel == "" {
		rel = constants.DefaultOutputDir
	}

	cfg := a.configMgr.Config

	ec := growth.EngineConfig{
		Provider:       cfg.Provider,
		Model:          cfg.Model,
		APIKey:         cfg.APIKey,
		BaseURL:        cfg.BaseURL,
		ProjectDir:     projectDir,
		OutputDir:      rel,
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
	a.backendMu.Lock()
	if a.backendServer != nil {
		a.backendServer.Stop()
		a.backendServer = nil
	}
	a.backendMu.Unlock()
	if a.telemetry != nil {
		a.telemetry.Track(constants.EventTUIExited, map[string]string{
			"last_view":        a.lastView,
			"session_duration": a.telemetry.SessionDuration(),
		})
		a.telemetry.Close()
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
