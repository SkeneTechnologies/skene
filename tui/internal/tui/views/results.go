package views

import (
	"os"
	"path/filepath"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/bubbles/viewport"
	"github.com/charmbracelet/lipgloss"
)

// ResultsFocus represents which element is focused
type ResultsFocus int

const (
	ResultsFocusTabs ResultsFocus = iota
	ResultsFocusContent
)

// ResultsView shows the analysis results in a tabbed dashboard
type ResultsView struct {
	width     int
	height    int
	tabs      []string
	activeTab int
	contents  map[string]string
	viewport  viewport.Model
	focus     ResultsFocus
	header    *components.WizardHeader
}

// NewResultsView creates a new results view with default placeholder content
func NewResultsView() *ResultsView {
	return NewResultsViewWithContent("", "", "")
}

// NewResultsViewWithContent creates a new results view with custom content.
// Parameters: growthPlan (growth-plan.md), manifest (growth-manifest.json),
// growthTemplate (growth-template.json).
func NewResultsViewWithContent(growthPlan, manifest, growthTemplate string) *ResultsView {
	vp := viewport.New(60, 20)

	v := &ResultsView{
		tabs:      []string{constants.TabGrowthManifest, constants.TabGrowthTemplate, constants.TabGrowthPlan},
		activeTab: 0,
		contents:  make(map[string]string),
		viewport:  vp,
		focus:     ResultsFocusTabs,
		header:    components.NewTitleHeader(constants.StepNameResults),
	}

	if manifest != "" {
		v.contents[constants.TabGrowthManifest] = manifest
	} else {
		v.contents[constants.TabGrowthManifest] = constants.PlaceholderGrowthManifest
	}
	if growthTemplate != "" {
		v.contents[constants.TabGrowthTemplate] = growthTemplate
	} else {
		v.contents[constants.TabGrowthTemplate] = constants.PlaceholderGrowthTemplate
	}
	if growthPlan != "" {
		v.contents[constants.TabGrowthPlan] = growthPlan
	} else {
		v.contents[constants.TabGrowthPlan] = constants.PlaceholderGrowthPlan
	}

	wrapped := lipgloss.NewStyle().Width(v.viewport.Width).Render(v.contents[constants.TabGrowthManifest])
	v.viewport.SetContent(wrapped)

	return v
}

// SetSize updates dimensions
func (v *ResultsView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)

	vpWidth := width - 10
	if vpWidth < 40 {
		vpWidth = 40
	}
	if vpWidth > 100 {
		vpWidth = 100
	}

	vpHeight := height - 16
	if vpHeight < 10 {
		vpHeight = 10
	}

	v.viewport.Width = vpWidth
	v.viewport.Height = vpHeight
	v.updateContent()
}

// HandleLeft moves tab left
func (v *ResultsView) HandleLeft() {
	if v.focus == ResultsFocusTabs && v.activeTab > 0 {
		v.activeTab--
		v.updateContent()
	}
}

// HandleRight moves tab right
func (v *ResultsView) HandleRight() {
	if v.focus == ResultsFocusTabs && v.activeTab < len(v.tabs)-1 {
		v.activeTab++
		v.updateContent()
	}
}

// HandleUp scrolls content up
func (v *ResultsView) HandleUp() {
	if v.focus == ResultsFocusContent {
		v.viewport.ScrollUp(3)
	}
}

// HandleDown scrolls content down
func (v *ResultsView) HandleDown() {
	if v.focus == ResultsFocusContent {
		v.viewport.ScrollDown(3)
	}
}

// HandleTab cycles focus
func (v *ResultsView) HandleTab() {
	if v.focus == ResultsFocusTabs {
		v.focus = ResultsFocusContent
	} else {
		v.focus = ResultsFocusTabs
	}
}

func (v *ResultsView) updateContent() {
	tabName := v.tabs[v.activeTab]
	if content, ok := v.contents[tabName]; ok {
		wrapped := lipgloss.NewStyle().Width(v.viewport.Width).Render(content)
		v.viewport.SetContent(wrapped)
		v.viewport.GotoTop()
	}
}

// Render the results view
func (v *ResultsView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Success banner
	banner := styles.SuccessText.Render(constants.ResultsBanner)

	// Tabs
	tabsView := v.renderTabs()

	// Content
	contentBox := v.renderContentBox()

	// Footer with next steps integrated
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardResultsHelp())

	// Combine
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		banner,
		"",
		tabsView,
		contentBox,
	)

	mainContent := lipgloss.Place(
		v.width,
		v.height-3,
		lipgloss.Center,
		lipgloss.Top,
		lipgloss.NewStyle().Padding(1, 2).Render(content),
	)

	return mainContent + "\n" + footer
}

func (v *ResultsView) renderTabs() string {
	var tabs []string
	for i, tab := range v.tabs {
		var style lipgloss.Style
		if i == v.activeTab {
			style = styles.TabActive
		} else {
			style = styles.TabInactive
		}
		tabs = append(tabs, style.Render(tab))
	}
	return lipgloss.JoinHorizontal(lipgloss.Bottom, tabs...)
}

func (v *ResultsView) renderContentBox() string {
	borderColor := styles.MidGray
	if v.focus == ResultsFocusContent {
		borderColor = styles.Cream
	}

	boxStyle := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(borderColor).
		Padding(1, 2).
		Width(v.viewport.Width + 6)

	return boxStyle.Render(v.viewport.View())
}

// GetHelpItems returns context-specific help
func (v *ResultsView) GetHelpItems() []components.HelpItem {
	if v.focus == ResultsFocusTabs {
		return []components.HelpItem{
			{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescSwitchTabs},
			{Key: constants.HelpKeyTab, Desc: constants.HelpDescFocusContent},
			{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}
	}
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
		{Key: constants.HelpKeyTab, Desc: constants.HelpDescFocusTabs},
		{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}

// RefreshContent reloads file content from the given directory
func (v *ResultsView) RefreshContent(outputDir string) {
	manifest := loadResultFile(outputDir, constants.GrowthManifestFile)
	if manifest != "" {
		v.contents[constants.TabGrowthManifest] = manifest
	}
	template := loadResultFile(outputDir, constants.GrowthTemplateFile)
	if template != "" {
		v.contents[constants.TabGrowthTemplate] = template
	}
	plan := loadResultFile(outputDir, constants.GrowthPlanFile)
	if plan != "" {
		v.contents[constants.TabGrowthPlan] = plan
	}
	v.updateContent()
}

func loadResultFile(dir, filename string) string {
	data, err := os.ReadFile(filepath.Join(dir, filename))
	if err != nil {
		return ""
	}
	return string(data)
}

