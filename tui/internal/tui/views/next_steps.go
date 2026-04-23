package views

import (
	"os"
	"path/filepath"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// NextStepAction represents an available next step
type NextStepAction struct {
	ID          string
	Name        string
	Description string
	Command     string
}

// NextStepsView presents available next steps after analysis
type NextStepsView struct {
	width       int
	height      int
	actions     []NextStepAction
	available   []bool
	selectedIdx int
	header      *components.WizardHeader
}

// NewNextStepsView creates a next steps view without availability checks
// (all actions enabled). Used by the results dashboard.
func NewNextStepsView() *NextStepsView {
	return NewNextStepsViewWithContext("")
}

// NewNextStepsViewWithContext creates a next steps view that checks file
// availability relative to outputDir. Pass "" to enable all actions.
func NewNextStepsViewWithContext(outputDir string) *NextStepsView {
	var actions []NextStepAction
	var available []bool

	for _, def := range constants.NextStepActions {
		actions = append(actions, NextStepAction{
			ID:          def.ID,
			Name:        def.Name,
			Description: def.Description,
			Command:     def.Command,
		})
		available = append(available, isActionAvailable(def, outputDir))
	}

	v := &NextStepsView{
		actions:   actions,
		available: available,
		header:    components.NewTitleHeader(constants.StepNameNextSteps),
	}
	v.selectFirstAvailable()
	return v
}

func isActionAvailable(def constants.NextStepDef, outputDir string) bool {
	if outputDir == "" {
		return true
	}
	if def.RequiresDir {
		info, err := os.Stat(outputDir)
		return err == nil && info.IsDir()
	}
	if def.RequiresFile != "" {
		_, err := os.Stat(filepath.Join(outputDir, def.RequiresFile))
		return err == nil
	}
	return true
}

func (v *NextStepsView) selectFirstAvailable() {
	for i, ok := range v.available {
		if ok {
			v.selectedIdx = i
			return
		}
	}
	v.selectedIdx = 0
}

// SetSize updates dimensions
func (v *NextStepsView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// HandleUp moves selection up, skipping unavailable items.
func (v *NextStepsView) HandleUp() {
	for i := v.selectedIdx - 1; i >= 0; i-- {
		if v.available[i] {
			v.selectedIdx = i
			return
		}
	}
}

// HandleDown moves selection down, skipping unavailable items.
func (v *NextStepsView) HandleDown() {
	for i := v.selectedIdx + 1; i < len(v.actions); i++ {
		if v.available[i] {
			v.selectedIdx = i
			return
		}
	}
}

// GetSelectedAction returns the selected action, or nil if unavailable.
func (v *NextStepsView) GetSelectedAction() *NextStepAction {
	if v.selectedIdx >= 0 && v.selectedIdx < len(v.actions) && v.available[v.selectedIdx] {
		return &v.actions[v.selectedIdx]
	}
	return nil
}

// Render the next steps view
func (v *NextStepsView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Success message
	successMsg := styles.SuccessText.Render(constants.NextStepsSuccess)

	// Actions list
	actionsSection := v.renderActions(sectionWidth)

	// Command preview
	commandPreview := v.renderCommandPreview(sectionWidth)

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardSelectHelp(v.width))

	// Combine
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		successMsg,
		"",
		actionsSection,
		"",
		commandPreview,
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

func (v *NextStepsView) renderActions(width int) string {
	var items []string

	descWidth := width - 8
	for i, action := range v.actions {
		isSelected := i == v.selectedIdx
		isAvailable := v.available[i]

		var name string
		switch {
		case !isAvailable:
			name = styles.ListItemDimmed.Render(action.Name)
		case isSelected:
			name = styles.ListItemSelected.Render(action.Name)
		default:
			name = styles.ListItem.Render(action.Name)
		}

		descText := action.Description
		if !isAvailable {
			descText += " — not available"
		}
		desc := lipgloss.NewStyle().Foreground(styles.MutedColor).PaddingLeft(2).Width(descWidth).Render(descText)

		item := name + "\n" + desc
		items = append(items, item)

		if i < len(v.actions)-1 {
			items = append(items, "")
		}
	}

	list := lipgloss.JoinVertical(lipgloss.Left, items...)
	return styles.Box.Width(width).Render(list)
}

func (v *NextStepsView) renderCommandPreview(width int) string {
	action := v.GetSelectedAction()
	if action == nil || action.Command == "" {
		return ""
	}

	cmdLabel := styles.Muted.Render("Command: ")
	cmdValue := styles.AccentStyle().Width(width - 14).Render(action.Command)
	preview := cmdLabel + cmdValue
	return lipgloss.NewStyle().
		Width(width).
		Render(preview)
}

// RenderModal renders the next steps as a compact floating modal.
func (v *NextStepsView) RenderModal(width int) string {
	titleRow := lipgloss.JoinHorizontal(lipgloss.Top,
		styles.Title.Render(constants.StepNameNextSteps),
		lipgloss.NewStyle().
			Width(width-6-lipgloss.Width(constants.StepNameNextSteps)).
			Align(lipgloss.Right).
			Foreground(styles.MutedColor).
			Render(constants.HelpKeyEsc),
	)

	// Flat action list — no inner box
	contentWidth := width - 8
	var items []string
	for i, action := range v.actions {
		isSelected := i == v.selectedIdx
		isAvailable := v.available[i]

		var name string
		switch {
		case !isAvailable:
			name = styles.ListItemDimmed.Render(action.Name)
		case isSelected:
			name = styles.ListItemSelected.Render(action.Name)
		default:
			name = styles.ListItem.Render(action.Name)
		}

		descText := action.Description
		if !isAvailable {
			descText += " — not available"
		}
		desc := lipgloss.NewStyle().
			Foreground(styles.MutedColor).
			PaddingLeft(2).
			Width(contentWidth).
			Render(descText)

		items = append(items, name+"\n"+desc)

		if i < len(v.actions)-1 {
			items = append(items, "")
		}
	}
	list := lipgloss.JoinVertical(lipgloss.Left, items...)

	content := lipgloss.JoinVertical(lipgloss.Left,
		titleRow,
		"",
		list,
	)

	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(styles.MutedColor).
		Padding(1, 2).
		Width(width).
		Render(content)
}

// GetHelpItems returns context-specific help
func (v *NextStepsView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescNavigate},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSelect},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBackToResults},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
