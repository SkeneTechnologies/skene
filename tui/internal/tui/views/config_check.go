package views

import (
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

type configOption struct {
	name string
	desc string
}

var configCheckOptions = []configOption{
	{name: "Use this configuration", desc: "Continue to project selection with the settings above"},
	{name: "Reconfigure", desc: "Choose a different provider, model, or API key"},
}

// ConfigCheckView shows the detected LLM configuration and lets the user
// choose between using it or reconfiguring.
type ConfigCheckView struct {
	width         int
	height        int
	providerName  string
	modelName     string
	maskedAPIKey  string
	selectedIndex int
	header        *components.WizardHeader
}

// NewConfigCheckView creates a config check view showing the loaded values.
func NewConfigCheckView(providerName, modelName, maskedAPIKey string) *ConfigCheckView {
	return &ConfigCheckView{
		providerName:  providerName,
		modelName:     modelName,
		maskedAPIKey:  maskedAPIKey,
		selectedIndex: 0,
		header:        components.NewTitleHeader("Existing Configuration Found"),
	}
}

func (v *ConfigCheckView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

func (v *ConfigCheckView) HandleUp() {
	if v.selectedIndex > 0 {
		v.selectedIndex--
	}
}

func (v *ConfigCheckView) HandleDown() {
	if v.selectedIndex < len(configCheckOptions)-1 {
		v.selectedIndex++
	}
}

// SelectedUseExisting returns true when the user chose "Use this configuration".
func (v *ConfigCheckView) SelectedUseExisting() bool {
	return v.selectedIndex == 0
}

func (v *ConfigCheckView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	listSection := v.renderList(sectionWidth)

	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardSelectHelp(v.width))

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		listSection,
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

func (v *ConfigCheckView) renderList(width int) string {
	sectionHeader := styles.SectionHeader.Render("Current LLM Settings")

	valueWidth := width - 20
	if valueWidth < 30 {
		valueWidth = 30
	}
	configRows := lipgloss.JoinVertical(lipgloss.Left,
		styles.Label.Render("Provider:  ")+lipgloss.NewStyle().Foreground(styles.TextColor).Width(valueWidth).Render(v.providerName),
		styles.Label.Render("Model:     ")+lipgloss.NewStyle().Foreground(styles.TextColor).Width(valueWidth).Render(v.modelName),
		styles.Label.Render("API Key:   ")+lipgloss.NewStyle().Foreground(styles.TextColor).Width(valueWidth).Render(v.maskedAPIKey),
	)

	separator := styles.Muted.Render("How would you like to proceed?")

	descWidth := width - 8
	var items []string
	for i, opt := range configCheckOptions {
		isSelected := i == v.selectedIndex

		var item string
		if isSelected {
			name := styles.ListItemSelected.Render(opt.name)
			desc := lipgloss.NewStyle().Foreground(styles.MutedColor).PaddingLeft(2).Width(descWidth).Render(opt.desc)
			item = name + "\n" + desc
		} else {
			name := styles.ListItem.Render(opt.name)
			desc := lipgloss.NewStyle().Foreground(styles.MutedColor).PaddingLeft(2).Width(descWidth).Render(opt.desc)
			item = name + "\n" + desc
		}

		items = append(items, item)
		if i < len(configCheckOptions)-1 {
			items = append(items, "")
		}
	}

	list := lipgloss.JoinVertical(lipgloss.Left, items...)

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		sectionHeader,
		"",
		configRows,
		"",
		separator,
		"",
		list,
	)

	return styles.Box.Width(width).Render(content)
}

func (v *ConfigCheckView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescNavigate},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirmSelection},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
