package views

import (
	"fmt"
	"net/url"
	"skene/internal/constants"
	"skene/internal/services/config"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// AuthView handles Skene auth with magic link and fallback
type AuthView struct {
	width        int
	height       int
	provider     *config.Provider
	countdown    int // seconds remaining
	authURL      string
	showFallback bool
	header       *components.WizardHeader
	spinner      *components.Spinner
	authState    AuthState
}

// AuthState represents the authentication state
type AuthState int

const (
	AuthStateCountdown AuthState = iota
	AuthStateBrowserOpen
	AuthStateWaiting
	AuthStateVerifying
	AuthStateSuccess
	AuthStateFallback
)

// NewAuthView creates a new auth view
func NewAuthView(provider *config.Provider) *AuthView {
	authURL := constants.SkeneAuthURL
	if provider != nil && provider.AuthURL != "" {
		authURL = provider.AuthURL
	}

	return &AuthView{
		provider:     provider,
		countdown:    3,
		authURL:      authURL,
		showFallback: false,
		header:       components.NewWizardHeader(2, constants.StepNameAuthentication),
		spinner:      components.NewSpinner(),
		authState:    AuthStateCountdown,
	}
}

// SetSize updates dimensions
func (v *AuthView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// SetCountdown updates countdown value
func (v *AuthView) SetCountdown(seconds int) {
	v.countdown = seconds
}

// GetCountdown returns current countdown
func (v *AuthView) GetCountdown() int {
	return v.countdown
}

// GetAuthURL returns the auth URL
func (v *AuthView) GetAuthURL() string {
	return v.authURL
}

// SetAuthURL updates the auth URL (e.g., with callback parameter)
func (v *AuthView) SetAuthURL(u string) {
	v.authURL = u
}

// getDisplayURL returns a clean URL for display (without query params)
func (v *AuthView) getDisplayURL() string {
	parsed, err := url.Parse(v.authURL)
	if err != nil {
		return v.authURL
	}
	return fmt.Sprintf("%s://%s%s", parsed.Scheme, parsed.Host, parsed.Path)
}

// SetAuthState updates the auth state
func (v *AuthView) SetAuthState(state AuthState) {
	v.authState = state
}

// ShowFallback enables fallback mode
func (v *AuthView) ShowFallback() {
	v.showFallback = true
	v.authState = AuthStateFallback
}

// IsFallbackShown returns if fallback is shown
func (v *AuthView) IsFallbackShown() bool {
	return v.showFallback
}

// TickSpinner advances the spinner
func (v *AuthView) TickSpinner() {
	v.spinner.Tick()
}

// Render the auth view
func (v *AuthView) Render() string {
	if v.showFallback {
		return v.renderFallback()
	}

	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header — match box width for alignment
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Auth content based on state
	var authContent string
	switch v.authState {
	case AuthStateCountdown:
		authContent = v.renderCountdown(sectionWidth)
	case AuthStateBrowserOpen, AuthStateWaiting:
		authContent = v.renderWaiting(sectionWidth)
	case AuthStateVerifying:
		authContent = v.renderVerifying(sectionWidth)
	case AuthStateSuccess:
		authContent = v.renderSuccess(sectionWidth)
	default:
		authContent = v.renderCountdown(sectionWidth)
	}

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyM, Desc: constants.HelpDescManualEntry},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescCancel},
		}))

	// Combine
	fullContent := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		"",
		authContent,
	)

	padded := lipgloss.NewStyle().PaddingTop(2).Render(fullContent)

	centered := lipgloss.Place(
		v.width,
		v.height-3,
		lipgloss.Center,
		lipgloss.Top,
		padded,
	)

	return centered + "\n" + footer
}

func (v *AuthView) renderCountdown(width int) string {
	message := styles.Body.Render(constants.AuthOpeningBrowser)
	url := lipgloss.NewStyle().Foreground(styles.Amber).Width(width-8).Render(v.getDisplayURL())

	countdownText := fmt.Sprintf(constants.AuthRedirectingIn, v.countdown)
	countdownStyled := styles.Muted.Render(countdownText)

	// Countdown visual
	var countdownVisual string
	switch v.countdown {
	case 3:
		countdownVisual = styles.Accent.Render("● ● ●")
	case 2:
		countdownVisual = styles.Accent.Render("● ●") + styles.Muted.Render(" ○")
	case 1:
		countdownVisual = styles.Accent.Render("●") + styles.Muted.Render(" ○ ○")
	default:
		countdownVisual = styles.Muted.Render("○ ○ ○")
	}

	content := lipgloss.JoinVertical(
		lipgloss.Center,
		message,
		"",
		url,
		"",
		countdownStyled,
		"",
		countdownVisual,
	)

	return styles.Box.
		Width(width).
		Align(lipgloss.Center).
		Render(content)
}

func (v *AuthView) renderWaiting(width int) string {
	message := v.spinner.SpinnerWithText(constants.AuthWaiting)
	subMessage := styles.Muted.Render(constants.AuthWaitingSub)
	url := lipgloss.NewStyle().Foreground(styles.Amber).Width(width-8).Render(v.getDisplayURL())

	content := lipgloss.JoinVertical(
		lipgloss.Center,
		message,
		"",
		subMessage,
		"",
		url,
	)

	return styles.Box.
		Width(width).
		Align(lipgloss.Center).
		Render(content)
}

func (v *AuthView) renderVerifying(width int) string {
	message := v.spinner.SpinnerWithText(constants.AuthVerifying)
	subMessage := styles.Muted.Render(constants.AuthVerifyingSub)

	content := lipgloss.JoinVertical(
		lipgloss.Center,
		message,
		"",
		subMessage,
	)

	return styles.Box.
		Width(width).
		Align(lipgloss.Center).
		Render(content)
}

func (v *AuthView) renderSuccess(width int) string {
	message := styles.SuccessText.Render("✓ " + constants.AuthSuccess)
	subMessage := styles.Muted.Render("API key received and saved")

	content := lipgloss.JoinVertical(
		lipgloss.Center,
		message,
		"",
		subMessage,
	)

	return styles.Box.
		Width(width).
		Align(lipgloss.Center).
		Render(content)
}

func (v *AuthView) renderFallback() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	message := lipgloss.NewStyle().Foreground(styles.White).Width(sectionWidth-8).Render(constants.AuthFallbackMessage)
	subMessage := lipgloss.NewStyle().Foreground(styles.MidGray).Width(sectionWidth-8).Render(constants.AuthFallbackSub)
	hint := lipgloss.NewStyle().Foreground(styles.Amber).Width(sectionWidth-8).Render(constants.AuthFallbackHint)

	content := lipgloss.JoinVertical(
		lipgloss.Center,
		message,
		"",
		subMessage,
		"",
		hint,
	)

	box := styles.Box.
		Width(sectionWidth).
		Align(lipgloss.Center).
		Render(content)

	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescContinue},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		}))

	fullContent := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		"",
		box,
	)

	padded := lipgloss.NewStyle().PaddingTop(2).Render(fullContent)

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
func (v *AuthView) GetHelpItems() []components.HelpItem {
	if v.showFallback {
		return []components.HelpItem{
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescContinueManual},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBackToProvider},
		}
	}
	return []components.HelpItem{
		{Key: constants.HelpKeyM, Desc: constants.HelpDescSkipManualEntry},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescCancelGoBack},
	}
}
