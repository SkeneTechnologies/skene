package components

import (
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// Button represents a styled button
type Button struct {
	Label    string
	Active   bool
	Disabled bool
}

// NewButton creates a new button
func NewButton(label string) *Button {
	return &Button{
		Label:    label,
		Active:   false,
		Disabled: false,
	}
}

// SetActive sets button active state
func (b *Button) SetActive(active bool) {
	b.Active = active
}

// SetDisabled sets button disabled state
func (b *Button) SetDisabled(disabled bool) {
	b.Disabled = disabled
}

// Render the button
func (b *Button) Render() string {
	if b.Disabled {
		return styles.ButtonMuted.Render(b.Label)
	}
	if b.Active {
		return styles.ButtonActive.Render(b.Label)
	}
	return styles.Button.Render(b.Label)
}

// ButtonGroup renders a group of buttons
type ButtonGroup struct {
	Buttons      []*Button
	ActiveIndex  int
	Horizontal   bool
	Gap          int
}

// NewButtonGroup creates a horizontal button group
func NewButtonGroup(labels ...string) *ButtonGroup {
	buttons := make([]*Button, len(labels))
	for i, label := range labels {
		buttons[i] = NewButton(label)
	}
	if len(buttons) > 0 {
		buttons[0].SetActive(true)
	}
	return &ButtonGroup{
		Buttons:     buttons,
		ActiveIndex: 0,
		Horizontal:  true,
		Gap:         2,
	}
}

// SetActiveIndex changes which button is active. Pass -1 to deactivate all.
func (bg *ButtonGroup) SetActiveIndex(index int) {
	if index >= len(bg.Buttons) {
		return
	}
	for i := range bg.Buttons {
		bg.Buttons[i].SetActive(i == index)
	}
	bg.ActiveIndex = index
}

// Next moves to next button
func (bg *ButtonGroup) Next() {
	next := (bg.ActiveIndex + 1) % len(bg.Buttons)
	bg.SetActiveIndex(next)
}

// Previous moves to previous button
func (bg *ButtonGroup) Previous() {
	prev := (bg.ActiveIndex - 1 + len(bg.Buttons)) % len(bg.Buttons)
	bg.SetActiveIndex(prev)
}

// GetActiveLabel returns the active button's label
func (bg *ButtonGroup) GetActiveLabel() string {
	if bg.ActiveIndex >= 0 && bg.ActiveIndex < len(bg.Buttons) {
		return bg.Buttons[bg.ActiveIndex].Label
	}
	return ""
}

// Render the button group
func (bg *ButtonGroup) Render() string {
	var rendered []string
	for _, btn := range bg.Buttons {
		rendered = append(rendered, btn.Render())
	}

	if bg.Horizontal {
		gap := lipgloss.NewStyle().Width(bg.Gap).Render("")
		return lipgloss.JoinHorizontal(lipgloss.Center, interleave(rendered, gap)...)
	}

	return lipgloss.JoinVertical(lipgloss.Left, rendered...)
}

// Helper to add gap between elements
func interleave(items []string, sep string) []string {
	if len(items) <= 1 {
		return items
	}
	result := make([]string, len(items)*2-1)
	for i, item := range items {
		result[i*2] = item
		if i < len(items)-1 {
			result[i*2+1] = sep
		}
	}
	return result
}

