package views

import (
	"fmt"
	"skene/internal/constants"
	"skene/internal/services/config"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// ModelView handles model selection for a provider
type ModelView struct {
	width         int
	height        int
	provider      *config.Provider
	selectedIndex int
	header        *components.WizardHeader
}

// NewModelView creates a new model view
func NewModelView(provider *config.Provider) *ModelView {
	return &ModelView{
		provider:      provider,
		selectedIndex: 0,
		header:        components.NewWizardHeader(1, constants.StepNameSelectModel),
	}
}

// SetProvider updates the provider
func (v *ModelView) SetProvider(provider *config.Provider) {
	v.provider = provider
	v.selectedIndex = 0
}

// SetSize updates dimensions
func (v *ModelView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// HandleUp moves selection up
func (v *ModelView) HandleUp() {
	if v.selectedIndex > 0 {
		v.selectedIndex--
	}
}

// HandleDown moves selection down
func (v *ModelView) HandleDown() {
	if v.provider == nil {
		return
	}
	if v.selectedIndex < len(v.provider.Models)-1 {
		v.selectedIndex++
	}
}

// GetSelectedModel returns the selected model
func (v *ModelView) GetSelectedModel() *config.Model {
	if v.provider == nil || v.selectedIndex < 0 || v.selectedIndex >= len(v.provider.Models) {
		return nil
	}
	return &v.provider.Models[v.selectedIndex]
}

// Render the model view
func (v *ModelView) Render() string {
	if v.provider == nil {
		return "No provider selected"
	}

	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Model list section
	listSection := v.renderModelList(sectionWidth)

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardSelectHelp())

	// Combine
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

func (v *ModelView) renderModelList(width int) string {
	header := styles.SectionHeader.Render(fmt.Sprintf("Select Model for %s", v.provider.Name))

	// Model count
	count := styles.Muted.Render(fmt.Sprintf("%d / %d models", v.selectedIndex+1, len(v.provider.Models)))

	// Model list
	descWidth := width - 8
	var items []string
	for i, m := range v.provider.Models {
		isSelected := i == v.selectedIndex

		var item string
		if isSelected {
			name := styles.ListItemSelected.Render(m.Name)
			desc := lipgloss.NewStyle().Foreground(styles.Sand).PaddingLeft(2).Width(descWidth).Render(m.Description)
			item = name + "\n" + desc
		} else {
			name := styles.ListItem.Render(m.Name)
			desc := lipgloss.NewStyle().Foreground(styles.MidGray).PaddingLeft(2).Width(descWidth).Render(m.Description)
			item = name + "\n" + desc
		}
		items = append(items, item)

		// Add spacing between items (but not after last)
		if i < len(v.provider.Models)-1 {
			items = append(items, "")
		}
	}

	list := lipgloss.JoinVertical(lipgloss.Left, items...)

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		header,
		count,
		"",
		list,
	)

	return styles.Box.Width(width).Render(content)
}

// GetHelpItems returns context-specific help
func (v *ModelView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescSelectModel},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirmSelection},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
