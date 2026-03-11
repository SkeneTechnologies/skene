package components

import (
	"skene/internal/constants"
	"skene/internal/tui/styles"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// HelpItem represents a single help entry
type HelpItem struct {
	Key  string
	Desc string
}

// HelpOverlay renders a help panel overlay
type HelpOverlay struct {
	Items   []HelpItem
	Title   string
	Visible bool
}

// NewHelpOverlay creates a new help overlay
func NewHelpOverlay() *HelpOverlay {
	return &HelpOverlay{
		Items: []HelpItem{
			{Key: constants.HelpKeyHelp, Desc: constants.HelpDescToggleHelp},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		},
		Title:   "Help",
		Visible: false,
	}
}

// Toggle visibility
func (h *HelpOverlay) Toggle() {
	h.Visible = !h.Visible
}

// SetItems updates help items
func (h *HelpOverlay) SetItems(items []HelpItem) {
	h.Items = items
}

// Render the help overlay
func (h *HelpOverlay) Render(width, height int) string {
	if !h.Visible {
		return ""
	}

	// Build help content
	var lines []string
	lines = append(lines, styles.SectionHeader.Render(h.Title))
	lines = append(lines, "")

	for _, item := range h.Items {
		key := styles.HelpKey.Render(item.Key)
		desc := styles.HelpDesc.Render(item.Desc)
		lines = append(lines, key+"  "+desc)
	}

	content := strings.Join(lines, "\n")

	// Style the box
	box := styles.Box.
		Width(40).
		Render(content)

	// Center in screen
	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, box)
}

// FooterHelp renders inline footer help. Items that would cause the line
// to exceed the terminal width are dropped so the footer never wraps.
func FooterHelp(items []HelpItem, widths ...int) string {
	maxWidth := 0
	if len(widths) > 0 {
		maxWidth = widths[0]
	}

	sep := styles.HelpSeparator.String()
	sepW := lipgloss.Width(sep)

	var parts []string
	totalWidth := 0
	for _, item := range items {
		part := styles.HelpKey.Render(item.Key) + " " + styles.HelpDesc.Render(item.Desc)
		partW := lipgloss.Width(part)
		newWidth := totalWidth + partW
		if len(parts) > 0 {
			newWidth += sepW
		}
		if maxWidth > 0 && newWidth > maxWidth {
			break
		}
		parts = append(parts, part)
		totalWidth = newWidth
	}
	return strings.Join(parts, sep)
}

// WizardSelectHelp returns help for selection screens
func WizardSelectHelp(width int) string {
	return FooterHelp([]HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescNavigate},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSelect},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}, width)
}

// WizardInputHelp returns help for input screens
func WizardInputHelp(width int) string {
	return FooterHelp([]HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSubmit},
		{Key: constants.HelpKeyTab, Desc: constants.HelpDescSwitchFocus},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}, width)
}

// WizardResultsHelp returns help for results screens
func WizardResultsHelp(width int) string {
	return FooterHelp([]HelpItem{
		{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescTabs},
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
		{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}, width)
}
