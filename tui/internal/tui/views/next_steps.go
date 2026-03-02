package views

import (
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
	selectedIdx int
	header      *components.WizardHeader
}

// NewNextStepsView creates a new next steps view
func NewNextStepsView() *NextStepsView {
	return &NextStepsView{
		selectedIdx: 0,
		header:      components.NewTitleHeader(constants.StepNameNextSteps),
		actions: func() []NextStepAction {
			var actions []NextStepAction
			for _, def := range constants.NextStepActions {
				actions = append(actions, NextStepAction{
					ID:          def.ID,
					Name:        def.Name,
					Description: def.Description,
					Command:     def.Command,
				})
			}
			return actions
		}(),
	}
}

// SetSize updates dimensions
func (v *NextStepsView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
}

// HandleUp moves selection up
func (v *NextStepsView) HandleUp() {
	if v.selectedIdx > 0 {
		v.selectedIdx--
	}
}

// HandleDown moves selection down
func (v *NextStepsView) HandleDown() {
	if v.selectedIdx < len(v.actions)-1 {
		v.selectedIdx++
	}
}

// GetSelectedAction returns the selected action
func (v *NextStepsView) GetSelectedAction() *NextStepAction {
	if v.selectedIdx >= 0 && v.selectedIdx < len(v.actions) {
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
		Render(components.WizardSelectHelp())

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

		var name, desc string
		if isSelected {
			name = styles.ListItemSelected.Render(action.Name)
			desc = lipgloss.NewStyle().Foreground(styles.Sand).PaddingLeft(2).Width(descWidth).Render(action.Description)
		} else {
			name = styles.ListItem.Render(action.Name)
			desc = lipgloss.NewStyle().Foreground(styles.MidGray).PaddingLeft(2).Width(descWidth).Render(action.Description)
		}

		item := name + "\n" + desc
		items = append(items, item)

		// Add spacing between items (but not after last)
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
	cmdValue := lipgloss.NewStyle().
		Foreground(styles.Amber).Width(width - 14).Render(action.Command)
	preview := cmdLabel + cmdValue
	return lipgloss.NewStyle().
		Width(width).
		Render(preview)
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
