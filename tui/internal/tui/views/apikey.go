package views

import (
	"fmt"
	"skene/internal/constants"
	"skene/internal/services/config"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/lipgloss"
)

// APIKeyView handles API key entry with validation
type APIKeyView struct {
	width        int
	height       int
	provider     *config.Provider
	model        *config.Model
	textInput    textinput.Model
	error        string
	validating   bool
	validated    bool
	header       *components.WizardHeader
	spinner      *components.Spinner
	retryCount   int
	baseURLInput textinput.Model // For generic providers
	showBaseURL  bool
}

// NewAPIKeyView creates a new API key view
func NewAPIKeyView(provider *config.Provider, model *config.Model) *APIKeyView {
	ti := textinput.New()
	ti.Placeholder = "Enter API Key"
	ti.CharLimit = 256
	ti.Width = 45
	ti.EchoMode = textinput.EchoPassword
	ti.EchoCharacter = '•'
	ti.Focus()

	urlInput := textinput.New()
	urlInput.Placeholder = "https://your-api.com/v1"
	urlInput.CharLimit = 256
	urlInput.Width = 45

	showBaseURL := provider != nil && provider.IsGeneric

	return &APIKeyView{
		provider:     provider,
		model:        model,
		textInput:    ti,
		header:       components.NewWizardHeader(2, constants.StepNameAuthentication),
		spinner:      components.NewSpinner(),
		baseURLInput: urlInput,
		showBaseURL:  showBaseURL,
	}
}

// SetProvider updates provider and model
func (v *APIKeyView) SetProvider(provider *config.Provider, model *config.Model) {
	v.provider = provider
	v.model = model
	v.showBaseURL = provider != nil && provider.IsGeneric
}

// SetSize updates dimensions
func (v *APIKeyView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// Update handles text input updates, routing to whichever input is focused
func (v *APIKeyView) Update(msg interface{}) {
	if v.baseURLInput.Focused() {
		v.baseURLInput, _ = v.baseURLInput.Update(msg)
	} else {
		v.textInput, _ = v.textInput.Update(msg)
	}
}

// HandleTab toggles between API key and Base URL inputs
func (v *APIKeyView) HandleTab() {
	if !v.showBaseURL {
		return // Nothing to cycle to
	}
	// Toggle between API key and Base URL
	if v.textInput.Focused() {
		v.textInput.Blur()
		v.baseURLInput.Focus()
	} else {
		v.baseURLInput.Blur()
		v.textInput.Focus()
	}
}

// GetAPIKey returns the entered API key
func (v *APIKeyView) GetAPIKey() string {
	return v.textInput.Value()
}

// GetBaseURL returns the entered base URL
func (v *APIKeyView) GetBaseURL() string {
	return v.baseURLInput.Value()
}

// GetTextInput returns the text input model
func (v *APIKeyView) GetTextInput() *textinput.Model {
	return &v.textInput
}

// SetValidating sets the validating state
func (v *APIKeyView) SetValidating(validating bool) {
	v.validating = validating
}

// SetValidated marks the key as validated
func (v *APIKeyView) SetValidated() {
	v.validated = true
	v.validating = false
	v.error = ""
}

// SetValidationError sets a validation error
func (v *APIKeyView) SetValidationError(msg string) {
	v.error = msg
	v.validating = false
	v.retryCount++
}

// TickSpinner advances the spinner
func (v *APIKeyView) TickSpinner() {
	v.spinner.Tick()
}

// Validate checks if the API key is valid (basic validation)
func (v *APIKeyView) Validate() bool {
	key := v.textInput.Value()

	// Provider-specific validation
	if v.provider != nil {
		switch v.provider.ID {
		case "openai":
			if !strings.HasPrefix(key, "sk-") || len(key) < 20 {
				v.error = constants.OpenAIKeyFormat
				return false
			}
		case "anthropic":
			if !strings.HasPrefix(key, "sk-ant-") && len(key) < 20 {
				v.error = constants.AnthropicKeyFormat
				return false
			}
		case "gemini":
			if len(key) < 10 {
				v.error = constants.APIKeyTooShort
				return false
			}
		default:
			if len(key) < 8 {
				v.error = constants.APIKeyTooShort
				return false
			}
		}
	} else if len(key) < 8 {
		v.error = constants.APIKeyTooShort
		return false
	}

	if v.showBaseURL && v.baseURLInput.Value() == "" {
		v.error = constants.APIKeyBaseURLRequired
		return false
	}

	v.error = ""
	return true
}

// Render the API key view
func (v *APIKeyView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Main content section
	contentSection := v.renderContent(sectionWidth)

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardInputHelp())

	// Combine
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		contentSection,
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

func (v *APIKeyView) renderContent(width int) string {
	// Provider info
	providerName := ""
	modelName := ""
	if v.provider != nil {
		providerName = v.provider.Name
	}
	if v.model != nil {
		modelName = v.model.Name
	}

	header := styles.SectionHeader.Render(constants.APIKeyHeader)

	// Provider/model info
	infoRows := []string{
		styles.Label.Render("Provider: ") + styles.Body.Render(providerName),
	}
	if modelName != "" {
		infoRows = append(infoRows, styles.Label.Render("Model:    ") + styles.Body.Render(modelName))
	}

	// Get API key URL hint
	urlHint := ""
	if v.provider != nil {
		switch v.provider.ID {
		case "openai":
			urlHint = "Get key: " + constants.OpenAIKeyURL
		case "anthropic":
			urlHint = "Get key: " + constants.AnthropicKeyURL
		case "gemini":
			urlHint = "Get key: " + constants.GeminiKeyURL
		case "skene":
			urlHint = "Get key: " + constants.SkeneKeyURL
		}
	}

	// API Key input
	apiKeyLabel := styles.Label.Render("API Key:")
	inputField := v.textInput.View()

	var elements []string
	elements = append(elements, header, "")
	elements = append(elements, infoRows...)
	elements = append(elements, "")

	if urlHint != "" {
		elements = append(elements, lipgloss.NewStyle().
			Foreground(styles.MidGray).Width(width-8).Render(urlHint), "")
	}

	elements = append(elements, apiKeyLabel, inputField)

	// Base URL field for generic providers
	if v.showBaseURL {
		elements = append(elements, "")
		elements = append(elements, styles.Label.Render("Base URL:"))
		elements = append(elements, v.baseURLInput.View())
	}

	// Validating state
	if v.validating {
		elements = append(elements, "")
		elements = append(elements, v.spinner.SpinnerWithText(constants.APIKeyValidating))
	}

	// Error message
	if v.error != "" {
		elements = append(elements, "")
		elements = append(elements, lipgloss.NewStyle().
			Foreground(styles.Coral).Width(width-8).Render("✗ "+v.error))
		if v.retryCount > 0 {
			elements = append(elements, styles.Muted.Render(fmt.Sprintf("  Attempt %d", v.retryCount+1)))
		}
	}

	// Validated message
	if v.validated {
		elements = append(elements, "")
		elements = append(elements, styles.SuccessText.Render("✓ "+constants.APIKeyValidated))
	}

	content := lipgloss.JoinVertical(lipgloss.Left, elements...)
	return styles.Box.Width(width).Render(content)
}

// GetHelpItems returns context-specific help
func (v *APIKeyView) GetHelpItems() []components.HelpItem {
	if v.showBaseURL {
		return []components.HelpItem{
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSubmit},
			{Key: constants.HelpKeyTab, Desc: constants.HelpDescSwitchField},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}
	}
	return []components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSubmit},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
