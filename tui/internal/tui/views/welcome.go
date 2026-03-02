package views

import (
	tea "github.com/charmbracelet/bubbletea"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// WelcomeView renders the wizard welcome screen
type WelcomeView struct {
	width  int
	height int
	time   float64
	anim   components.ASCIIMotionModel
}

// NewWelcomeView creates a new welcome view
func NewWelcomeView() *WelcomeView {
	return &WelcomeView{
		anim: components.NewASCIIMotion(styles.IsDarkBackground),
	}
}

// SetSize updates dimensions
func (v *WelcomeView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.anim.SetSize(width, height)
}

// SetTime updates animation time
func (v *WelcomeView) SetTime(t float64) {
	v.time = t
}

// UpdateAnimation updates the animation model with a message
func (v *WelcomeView) UpdateAnimation(msg tea.Msg) tea.Cmd {
	var cmd tea.Cmd
	updatedModel, cmd := v.anim.Update(msg)
	v.anim = updatedModel.(components.ASCIIMotionModel)
	return cmd
}

// InitAnimation returns the initialization command for the animation
func (v *WelcomeView) InitAnimation() tea.Cmd {
	return v.anim.Init()
}

// ResetAnimation recreates the animation so it plays from the start
func (v *WelcomeView) ResetAnimation() tea.Cmd {
	v.anim = components.NewASCIIMotion(styles.IsDarkBackground)
	v.anim.SetSize(v.width, v.height)
	return v.anim.Init()
}

// Render the welcome view
func (v *WelcomeView) Render() string {
	// Content width for consistent centering
	contentWidth := 60
	if v.width > 0 && v.width < contentWidth {
		contentWidth = v.width - 4
	}

	center := lipgloss.NewStyle().Width(contentWidth).Align(lipgloss.Center)

	// Animated logo
	logo := v.anim.View()

	// Subtitle
	subtitle := center.Render(styles.Subtitle.Render(constants.WelcomeSubtitle))

	// Call to action
	enterKey := styles.Accent.Bold(true).Render(constants.WelcomeCTA)
	cta := center.Render(enterKey)

	// Version info
	version := center.Render(styles.Muted.Render(constants.Version + " • " + constants.Repository))

	// Footer help
	footer := components.FooterHelp([]components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescStart},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	})

	// Combine elements
	content := lipgloss.JoinVertical(
		lipgloss.Center,
		logo,
		"",
		"",
		cta,
		"",
		subtitle,
		"",
		version,
	)

	centered := lipgloss.Place(
		v.width,
		v.height-3,
		lipgloss.Center,
		lipgloss.Top,
		lipgloss.NewStyle().PaddingTop(2).Render(content),
	)

	// Footer pinned at bottom
	footerStyled := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		MarginTop(1).
		Render(footer)

	return centered + "\n" + footerStyled
}

// GetHelpItems returns context-specific help
func (v *WelcomeView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescStart},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
