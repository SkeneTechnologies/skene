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
	width  int
	height int
	error  *ErrorInfo
	header *components.WizardHeader
}

// NewErrorView creates a new error view
func NewErrorView(err *ErrorInfo) *ErrorView {
	return &ErrorView{
		error:  err,
		header: components.NewWizardHeader(0, "Error"),
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

// IsRetryable returns whether the error supports retry
func (v *ErrorView) IsRetryable() bool {
	return v.error != nil && v.error.Retryable
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

	var severityIcon, severityLabel string
	var titleColor lipgloss.TerminalColor
	switch v.error.Severity {
	case SeverityWarning:
		severityIcon = "!"
		severityLabel = "WARNING"
		titleColor = styles.WarningColor
	case SeverityError:
		severityIcon = "X"
		severityLabel = "ERROR"
		titleColor = styles.ErrorColor
	case SeverityCritical:
		severityIcon = "!!"
		severityLabel = "CRITICAL"
		titleColor = styles.ErrorColor
	}

	severityStyle := lipgloss.NewStyle().Foreground(titleColor).Bold(true)

	errorHeader := severityStyle.Render(severityIcon+" "+severityLabel) +
		"  " + styles.Muted.Render("["+v.error.Code+"]")

	title := lipgloss.NewStyle().Foreground(titleColor).Bold(true).Render(v.error.Title)

	messageStyle := lipgloss.NewStyle().Foreground(styles.TextColor).Width(sectionWidth - 8)
	message := messageStyle.Render(v.error.Message)

	suggestionHeader := styles.SectionHeader.Render("Suggested Fix")
	suggestion := lipgloss.NewStyle().
		Foreground(styles.SuccessColor).
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

	helpItems := []components.HelpItem{}
	if v.error.Retryable {
		helpItems = append(helpItems, components.HelpItem{Key: constants.HelpKeyR, Desc: constants.HelpDescRetry})
	}
	helpItems = append(helpItems,
		components.HelpItem{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		components.HelpItem{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	)

	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp(helpItems, v.width))

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		mainBox,
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
	items := []components.HelpItem{}
	if v.error != nil && v.error.Retryable {
		items = append(items, components.HelpItem{Key: constants.HelpKeyR, Desc: constants.HelpDescRetry})
	}
	items = append(items,
		components.HelpItem{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		components.HelpItem{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	)
	return items
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
		Message:    "pip failed to install skene package.",
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
