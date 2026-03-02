package components

import (
	"fmt"
	"skene/internal/constants"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// WizardStep represents a step in the wizard
type WizardStep struct {
	Number int
	Name   string
}

// WizardSteps defines the user-facing wizard flow
var WizardSteps = []WizardStep{
	{Number: 1, Name: constants.StepNameAIProvider},
	{Number: 2, Name: constants.StepNameAuthentication},
	{Number: 3, Name: constants.StepNameProjectSetup},
	{Number: 4, Name: constants.StepNameAnalysingStepper},
}

// WizardHeader renders the wizard progress header
type WizardHeader struct {
	CurrentStep int
	TotalSteps  int
	StepName    string
	Width       int
}

// NewWizardHeader creates a new wizard header
func NewWizardHeader(currentStep int, stepName string) *WizardHeader {
	return &WizardHeader{
		CurrentStep: currentStep,
		TotalSteps:  len(WizardSteps),
		StepName:    stepName,
		Width:       80,
	}
}

// NewTitleHeader creates a header that only shows a title (no step counter or dots)
func NewTitleHeader(title string) *WizardHeader {
	return &WizardHeader{
		CurrentStep: 0,
		TotalSteps:  0,
		StepName:    title,
		Width:       80,
	}
}

// SetWidth sets the header width
func (h *WizardHeader) SetWidth(width int) {
	h.Width = width
}

// SetStep updates the current step
func (h *WizardHeader) SetStep(step int, name string) {
	h.CurrentStep = step
	h.StepName = name
}

// Render the wizard header
func (h *WizardHeader) Render() string {
	// Title-only mode (no step counter or dots)
	if h.TotalSteps == 0 {
		return styles.Title.Render(h.StepName)
	}

	// Step counter
	stepCounter := styles.Muted.Render(fmt.Sprintf(constants.StepCounterFormat, h.CurrentStep, h.TotalSteps))

	// Step name
	stepName := styles.Title.Render(h.StepName)

	// Progress dots
	dots := renderWizardDots(h.CurrentStep, h.TotalSteps)

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		stepCounter,
		stepName,
		dots,
	)

	return content
}

func renderWizardDots(current, total int) string {
	var dots string
	for i := 1; i <= total; i++ {
		if i < current {
			dots += styles.Accent.Render("●")
		} else if i == current {
			dots += styles.Accent.Render("○")
		} else {
			dots += styles.Muted.Render("○")
		}
		if i < total {
			if i < current {
				dots += styles.Accent.Render("─")
			} else {
				dots += styles.Muted.Render("─")
			}
		}
	}
	return dots
}
