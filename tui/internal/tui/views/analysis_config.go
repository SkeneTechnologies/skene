package views

import (
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// AnalysisConfigView shows a summary and a Run Analysis button
type AnalysisConfigView struct {
	width        int
	height       int
	header       *components.WizardHeader
	providerName string
	modelName    string
	projectDir   string
}

// NewAnalysisConfigView creates a new analysis configuration view
func NewAnalysisConfigView(provider, model, projectDir string) *AnalysisConfigView {
	return &AnalysisConfigView{
		providerName: provider,
		modelName:    model,
		projectDir:   projectDir,
		header:       components.NewWizardHeader(3, constants.StepNameAnalysisConfig),
	}
}

// SetSize updates dimensions
func (v *AnalysisConfigView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// GetUseGrowth always returns true (only package)
func (v *AnalysisConfigView) GetUseGrowth() bool {
	return true
}

// Render the analysis config view
func (v *AnalysisConfigView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	summarySection := v.renderSummary(sectionWidth)

	button := lipgloss.NewStyle().
		Width(sectionWidth).
		Align(lipgloss.Center).
		Render(styles.ButtonActive.Render(constants.AnalysisConfigRunButton))

	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescStartAnalysis},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}))

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		summarySection,
		"",
		button,
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

func (v *AnalysisConfigView) renderSummary(width int) string {
	header := styles.SectionHeader.Render(constants.AnalysisConfigSummary)

	valueWidth := width - 20
	if valueWidth < 30 {
		valueWidth = 30
	}
	rows := []string{
		styles.Label.Render("Provider:   ") + lipgloss.NewStyle().Foreground(styles.White).Width(valueWidth).Render(v.providerName),
		styles.Label.Render("Model:      ") + lipgloss.NewStyle().Foreground(styles.White).Width(valueWidth).Render(v.modelName),
		styles.Label.Render("Directory:  ") + lipgloss.NewStyle().Foreground(styles.White).Width(valueWidth).Render(v.projectDir),
		styles.Label.Render("Output:     ") + lipgloss.NewStyle().Foreground(styles.White).Width(valueWidth).Render(constants.DefaultOutputDir+"/"),
	}

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		header,
		"",
		lipgloss.JoinVertical(lipgloss.Left, rows...),
	)

	return styles.Box.Width(width).Render(content)
}

// GetHelpItems returns context-specific help
func (v *AnalysisConfigView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescStartAnalysis},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
