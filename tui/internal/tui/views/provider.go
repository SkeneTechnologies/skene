package views

import (
	"fmt"
	"skene/internal/constants"
	"skene/internal/services/config"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// ProviderView handles provider selection
type ProviderView struct {
	width         int
	height        int
	providers     []config.Provider
	selectedIndex int
	scrollOffset  int
	maxVisible    int
	header        *components.WizardHeader
}

// NewProviderView creates a new provider view
func NewProviderView() *ProviderView {
	return &ProviderView{
		providers:     config.GetProviders(),
		selectedIndex: 0,
		maxVisible:    7,
		header:        components.NewWizardHeader(1, constants.StepNameAIProvider),
	}
}

// SetSize updates dimensions
func (v *ProviderView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
	// Adjust max visible based on height
	v.maxVisible = (height - 18) / 3
	if v.maxVisible < 3 {
		v.maxVisible = 3
	}
	if v.maxVisible > 10 {
		v.maxVisible = 10
	}
}

// HandleUp moves selection up
func (v *ProviderView) HandleUp() {
	if v.selectedIndex > 0 {
		v.selectedIndex--
		if v.selectedIndex < v.scrollOffset {
			v.scrollOffset = v.selectedIndex
		}
	}
}

// HandleDown moves selection down
func (v *ProviderView) HandleDown() {
	if v.selectedIndex < len(v.providers)-1 {
		v.selectedIndex++
		if v.selectedIndex >= v.scrollOffset+v.maxVisible {
			v.scrollOffset = v.selectedIndex - v.maxVisible + 1
		}
	}
}

// GetSelectedProvider returns the selected provider
func (v *ProviderView) GetSelectedProvider() *config.Provider {
	if v.selectedIndex >= 0 && v.selectedIndex < len(v.providers) {
		return &v.providers[v.selectedIndex]
	}
	return nil
}

// Render the provider view
func (v *ProviderView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Provider list section
	listSection := v.renderProviderList(sectionWidth)

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

func (v *ProviderView) renderProviderList(width int) string {
	header := styles.SectionHeader.Render("Select AI Provider")

	// Provider count
	count := styles.Muted.Render(fmt.Sprintf("%d / %d providers", v.selectedIndex+1, len(v.providers)))

	// Provider list
	var items []string

	endIdx := v.scrollOffset + v.maxVisible
	if endIdx > len(v.providers) {
		endIdx = len(v.providers)
	}

	descWidth := width - 8
	for i := v.scrollOffset; i < endIdx; i++ {
		p := v.providers[i]
		isSelected := i == v.selectedIndex

		var item string
		if isSelected {
			name := styles.ListItemSelected.Render(p.Name)
			desc := lipgloss.NewStyle().Foreground(styles.Sand).PaddingLeft(2).Width(descWidth).Render(p.Description)
			item = name + "\n" + desc
		} else {
			name := styles.ListItem.Render(p.Name)
			desc := lipgloss.NewStyle().Foreground(styles.MidGray).PaddingLeft(2).Width(descWidth).Render(p.Description)
			item = name + "\n" + desc
		}

		// Add badges
		if p.IsLocal {
			item += "\n" + lipgloss.NewStyle().Foreground(styles.MidGray).PaddingLeft(2).Render("[local]")
		}
		if p.IsGeneric {
			item += "\n" + lipgloss.NewStyle().Foreground(styles.MidGray).PaddingLeft(2).Render("[custom endpoint]")
		}

		items = append(items, item)

		// Add spacing between items (but not after last)
		if i < endIdx-1 {
			items = append(items, "")
		}
	}

	// Scroll indicators
	if v.scrollOffset > 0 {
		items = append([]string{styles.Muted.Render("  ↑ more above")}, items...)
	}
	if endIdx < len(v.providers) {
		items = append(items, styles.Muted.Render("  ↓ more below"))
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
func (v *ProviderView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescSelectProvider},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirmSelection},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
