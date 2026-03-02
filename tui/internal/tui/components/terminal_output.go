package components

import (
	"fmt"
	"regexp"
	"skene/internal/tui/styles"
	"strings"
	"sync"
	"unicode/utf8"

	"github.com/charmbracelet/lipgloss"
	"github.com/mattn/go-runewidth"
)

var ansiRe = regexp.MustCompile(`\x1b\[[0-9;]*[a-zA-Z]`)

func stripANSI(s string) string {
	return ansiRe.ReplaceAllString(s, "")
}

// TerminalOutput displays scrollable terminal/process output in a box
// with word-wrapping and manual scroll support.
type TerminalOutput struct {
	lines      []string
	maxLines   int
	width      int
	height     int
	scrollOff  int
	userScroll bool
	mu         sync.Mutex
}

// NewTerminalOutput creates a new terminal output display
func NewTerminalOutput(visibleLines, maxBuffer int) *TerminalOutput {
	if maxBuffer < visibleLines {
		maxBuffer = visibleLines * 3
	}
	return &TerminalOutput{
		lines:    make([]string, 0),
		maxLines: maxBuffer,
		height:   visibleLines,
	}
}

// SetSize updates the display dimensions
func (t *TerminalOutput) SetSize(width, height int) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.width = width
	t.height = height
}

// AddLine appends a line of output, stripping ANSI escape codes
func (t *TerminalOutput) AddLine(line string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	newLines := strings.Split(line, "\n")
	for _, l := range newLines {
		l = strings.TrimRight(l, "\r")
		l = stripANSI(l)
		t.lines = append(t.lines, l)
	}

	if len(t.lines) > t.maxLines {
		t.lines = t.lines[len(t.lines)-t.maxLines:]
	}

	if !t.userScroll {
		t.scrollOff = 0
	}
}

// AddOutput appends raw output that may contain multiple lines
func (t *TerminalOutput) AddOutput(output string) {
	if output == "" {
		return
	}
	lines := strings.Split(strings.TrimRight(output, "\n"), "\n")
	for _, line := range lines {
		t.AddLine(line)
	}
}

// Clear resets the output
func (t *TerminalOutput) Clear() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.lines = make([]string, 0)
	t.scrollOff = 0
	t.userScroll = false
}

// LineCount returns the number of lines
func (t *TerminalOutput) LineCount() int {
	t.mu.Lock()
	defer t.mu.Unlock()
	return len(t.lines)
}

// ScrollUp scrolls the view up by n display lines
func (t *TerminalOutput) ScrollUp(n int) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.userScroll = true
	contentWidth := t.contentWidth()
	wrapped := t.wrapAllLines(contentWidth)
	maxOff := len(wrapped) - t.visibleCount()
	if maxOff < 0 {
		maxOff = 0
	}
	t.scrollOff += n
	if t.scrollOff > maxOff {
		t.scrollOff = maxOff
	}
}

// ScrollDown scrolls the view down by n display lines
func (t *TerminalOutput) ScrollDown(n int) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.scrollOff -= n
	if t.scrollOff <= 0 {
		t.scrollOff = 0
		t.userScroll = false
	}
}

func (t *TerminalOutput) contentWidth() int {
	w := t.width - 6
	if w < 10 {
		w = 10
	}
	return w
}

func (t *TerminalOutput) visibleCount() int {
	if t.height <= 0 {
		return 8
	}
	return t.height
}

// displayWidth returns the visual width of a string, accounting for
// wide characters (CJK, emoji) and box-drawing characters.
func displayWidth(s string) int {
	return runewidth.StringWidth(s)
}

// wrapLine breaks a line into segments that each fit within width
// display columns, respecting multi-byte character boundaries.
func wrapLine(line string, width int) []string {
	if width <= 0 {
		return []string{line}
	}
	if displayWidth(line) <= width {
		return []string{line}
	}

	var wrapped []string
	for displayWidth(line) > width {
		breakByte := findBreakPoint(line, width)
		wrapped = append(wrapped, line[:breakByte])
		line = line[breakByte:]
		if len(line) > 0 && line[0] == ' ' {
			line = strings.TrimLeft(line, " ")
		}
	}
	if len(line) > 0 {
		wrapped = append(wrapped, line)
	}
	return wrapped
}

// findBreakPoint finds the byte offset at which to break the line so that
// the first part fits within width display columns. Prefers breaking at
// spaces within the last 30% of the width.
func findBreakPoint(line string, width int) int {
	dw := 0
	lastSpace := -1
	spaceThreshold := width * 7 / 10
	breakByte := 0

	for i := 0; i < len(line); {
		r, size := utf8.DecodeRuneInString(line[i:])
		rw := runewidth.RuneWidth(r)
		if dw+rw > width {
			break
		}
		dw += rw
		if r == ' ' && dw >= spaceThreshold {
			lastSpace = i
		}
		i += size
		breakByte = i
	}

	if lastSpace > 0 {
		return lastSpace
	}
	return breakByte
}

func (t *TerminalOutput) wrapAllLines(contentWidth int) []string {
	var result []string
	for _, line := range t.lines {
		parts := wrapLine(line, contentWidth)
		result = append(result, parts...)
	}
	return result
}

// Render the terminal output box
func (t *TerminalOutput) Render(width int) string {
	t.mu.Lock()
	defer t.mu.Unlock()

	if width < 20 {
		width = 20
	}

	contentWidth := width - 6
	if contentWidth < 10 {
		contentWidth = 10
	}

	visibleCount := t.visibleCount()
	wrapped := t.wrapAllLines(contentWidth)

	totalWrapped := len(wrapped)
	endIdx := totalWrapped - t.scrollOff
	if endIdx < 0 {
		endIdx = 0
	}
	startIdx := endIdx - visibleCount
	if startIdx < 0 {
		startIdx = 0
	}

	var displayLines []string

	defaultStyle := lipgloss.NewStyle().
		Foreground(styles.Cream).
		Width(contentWidth)
	errorStyle := lipgloss.NewStyle().
		Foreground(styles.Coral).
		Width(contentWidth)
	successStyle := lipgloss.NewStyle().
		Foreground(styles.Success).
		Width(contentWidth)
	warningStyle := lipgloss.NewStyle().
		Foreground(styles.Warning).
		Width(contentWidth)

	for i := startIdx; i < endIdx && i < totalWrapped; i++ {
		line := wrapped[i]

		upper := strings.ToUpper(line)
		var styled string
		if strings.Contains(upper, "ERROR") || strings.Contains(upper, "FAILED") ||
			strings.Contains(upper, "TRACEBACK") || strings.Contains(upper, "EXCEPTION") {
			styled = errorStyle.Render(line)
		} else if strings.Contains(line, "✓") || strings.Contains(upper, "SUCCESS") ||
			strings.Contains(upper, "COMPLETE") || strings.Contains(upper, "DONE") {
			styled = successStyle.Render(line)
		} else if strings.Contains(upper, "WARNING") || strings.Contains(upper, "WARN") {
			styled = warningStyle.Render(line)
		} else {
			styled = defaultStyle.Render(line)
		}
		displayLines = append(displayLines, styled)
	}

	for len(displayLines) < visibleCount {
		displayLines = append(displayLines, "")
	}

	content := strings.Join(displayLines, "\n")

	var scrollIndicator string
	if t.scrollOff > 0 {
		scrollIndicator = lipgloss.NewStyle().
			Foreground(styles.Amber).
			Render(fmt.Sprintf("  ↑↓ scroll • %d more below", t.scrollOff))
	}

	boxStyle := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(styles.MidGray).
		Padding(0, 1).
		Width(width - 2)

	result := boxStyle.Render(content)
	if scrollIndicator != "" {
		result += "\n" + scrollIndicator
	}

	return result
}
