package components

import (
	"skene/internal/tui/styles"
)

// Spinner component
type Spinner struct {
	frames []string
	index  int
}

// NewSpinner creates a new spinner
func NewSpinner() *Spinner {
	return &Spinner{
		frames: []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"},
		index:  0,
	}
}

// Tick advances the spinner
func (s *Spinner) Tick() {
	s.index = (s.index + 1) % len(s.frames)
}

// Render the spinner
func (s *Spinner) Render() string {
	return styles.Accent.Render(s.frames[s.index])
}

// SpinnerWithText renders spinner with text
func (s *Spinner) SpinnerWithText(text string) string {
	return s.Render() + " " + styles.Body.Render(text)
}
