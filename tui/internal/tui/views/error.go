package views

import (
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// ErrorSeverity represents error severity level
type ErrorSeverity int

const (
	SeverityWarning ErrorSeverity = iota
	SeverityError
	SeverityCritical
)

// ErrorInfo contains error details
type ErrorInfo struct {
	Code       string
	Title      string
	Message    string
	Suggestion string
	Severity   ErrorSeverity
	Retryable  bool
}

// ErrorView displays errors with suggested fixes and retry
type ErrorView struct {
	width       int
	height      int
	error       *ErrorInfo
	buttonGroup *components.ButtonGroup
	header      *components.WizardHeader
}

// NewErrorView creates a new error view
func NewErrorView(err *ErrorInfo) *ErrorView {
	var buttons *components.ButtonGroup
	if err.Retryable {
		buttons = components.NewButtonGroup("Retry", "Go Back", "Quit")
	} else {
		buttons = components.NewButtonGroup("Go Back", "Quit")
	}

	return &ErrorView{
		error:       err,
		buttonGroup: buttons,
		header:      components.NewWizardHeader(0, "Error"),
	}
}

// SetSize updates dimensions
func (v *ErrorView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// SetError updates the error to display
func (v *ErrorView) SetError(err *ErrorInfo) {
	v.error = err
}

// HandleLeft moves button focus left
func (v *ErrorView) HandleLeft() {
	v.buttonGroup.Previous()
}

// HandleRight moves button focus right
func (v *ErrorView) HandleRight() {
	v.buttonGroup.Next()
}

// GetSelectedButton returns selected button
func (v *ErrorView) GetSelectedButton() string {
	return v.buttonGroup.GetActiveLabel()
}

// Render the error view
func (v *ErrorView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Severity icon and label
	var severityIcon, severityLabel string
	var titleColor lipgloss.Color
	switch v.error.Severity {
	case SeverityWarning:
		severityIcon = "!"
		severityLabel = "WARNING"
		titleColor = styles.Warning
	case SeverityError:
		severityIcon = "X"
		severityLabel = "ERROR"
		titleColor = styles.Coral
	case SeverityCritical:
		severityIcon = "!!"
		severityLabel = "CRITICAL"
		titleColor = styles.Coral
	}

	severityStyle := lipgloss.NewStyle().Foreground(titleColor).Bold(true)

	// Error header with icon and code
	errorHeader := severityStyle.Render(severityIcon+" "+severityLabel) +
		"  " + styles.Muted.Render("["+v.error.Code+"]")

	// Title
	title := lipgloss.NewStyle().Foreground(titleColor).Bold(true).Render(v.error.Title)

	// Message
	messageStyle := lipgloss.NewStyle().Foreground(styles.White).Width(sectionWidth - 8)
	message := messageStyle.Render(v.error.Message)

	// Suggestion box
	suggestionHeader := styles.SectionHeader.Render("Suggested Fix")
	suggestion := lipgloss.NewStyle().
		Foreground(styles.Success).
		Width(sectionWidth - 12).
		Render("> " + v.error.Suggestion)

	suggestionContent := lipgloss.JoinVertical(
		lipgloss.Left,
		suggestionHeader,
		"",
		suggestion,
	)

	suggestionBox := styles.Box.
		Width(sectionWidth - 4).
		Render(suggestionContent)

	// Buttons
	buttons := lipgloss.NewStyle().
		Width(sectionWidth).
		Align(lipgloss.Center).
		Render(v.buttonGroup.Render())

	// Build the main content area
	innerContent := lipgloss.JoinVertical(
		lipgloss.Left,
		errorHeader,
		"",
		title,
		"",
		message,
		"",
		suggestionBox,
	)

	mainBox := styles.Box.
		Width(sectionWidth).
		Render(innerContent)

	// Footer help
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescSelect},
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirm},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}))

	// Combine all sections
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		mainBox,
		"",
		buttons,
	)

	padded := lipgloss.NewStyle().PaddingTop(2).Render(content)

	centered := lipgloss.Place(
		v.width,
		v.height-3,
		lipgloss.Center,
		lipgloss.Top,
		padded,
	)

	return centered + "\n" + footer
}

// GetHelpItems returns context-specific help
func (v *ErrorView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescSelectOption},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirm},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}

// Common errors
var (
	ErrPythonNotFound = &ErrorInfo{
		Code:       "PYTHON_NOT_FOUND",
		Title:      "Python Not Found",
		Message:    "Python 3.11+ is required but was not found in your PATH.",
		Suggestion: "Install Python 3.11+ from python.org or your package manager.",
		Severity:   SeverityError,
		Retryable:  false,
	}

	ErrPipFailed = &ErrorInfo{
		Code:       "PIP_FAILED",
		Title:      "Package Installation Failed",
		Message:    "pip failed to install skene-growth package.",
		Suggestion: "Run 'pip install --upgrade pip' and try again.",
		Severity:   SeverityError,
		Retryable:  true,
	}

	ErrNetworkFailed = &ErrorInfo{
		Code:       "NETWORK_ERROR",
		Title:      "Network Connection Failed",
		Message:    "Could not connect to package registry.",
		Suggestion: "Check your internet connection and try again.",
		Severity:   SeverityWarning,
		Retryable:  true,
	}

	ErrPermissionDenied = &ErrorInfo{
		Code:       "PERMISSION_DENIED",
		Title:      "Permission Denied",
		Message:    "Insufficient permissions to write to target directory.",
		Suggestion: "Check directory permissions or run with elevated privileges.",
		Severity:   SeverityError,
		Retryable:  true,
	}

	ErrInvalidAPIKey = &ErrorInfo{
		Code:       "INVALID_API_KEY",
		Title:      "Invalid API Key",
		Message:    "The provided API key was rejected by the provider.",
		Suggestion: "Double-check your API key and ensure it has the required permissions.",
		Severity:   SeverityError,
		Retryable:  true,
	}

	ErrLocalModelNotFound = &ErrorInfo{
		Code:       "LOCAL_MODEL_NOT_FOUND",
		Title:      "Local Model Runtime Not Found",
		Message:    "Could not detect Ollama or LM Studio running.",
		Suggestion: "Start your local model server and try again.",
		Severity:   SeverityWarning,
		Retryable:  true,
	}

	ErrAnalysisFailed = &ErrorInfo{
		Code:       "ANALYSIS_FAILED",
		Title:      "Analysis Failed",
		Message:    "The codebase analysis encountered an error.",
		Suggestion: "Check the logs for details and try again.",
		Severity:   SeverityError,
		Retryable:  true,
	}

	ErrUVInstallFailed = &ErrorInfo{
		Code:       "UV_INSTALL_FAILED",
		Title:      "uv Installation Failed",
		Message:    "Failed to install the uv package manager.",
		Suggestion: "Try one of these methods:\n1. Create directory first: mkdir -p ~/.local/bin\n2. Install via Homebrew: brew install uv\n3. Use custom path: curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=~/bin sh",
		Severity:   SeverityWarning,
		Retryable:  true,
	}
)
