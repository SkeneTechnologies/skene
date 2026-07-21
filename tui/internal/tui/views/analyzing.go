package views

import (
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// AnalysisPhase represents a phase of the analysis
type AnalysisPhase struct {
	Name     string
	Progress float64
	Done     bool
	Active   bool
	Error    string
}

// AnalyzingView shows analysis progress with live terminal output
type AnalyzingView struct {
	width       int
	height      int
	phases      []AnalysisPhase
	header      *components.WizardHeader
	spinner     *components.Spinner
	terminal    *components.TerminalOutput
	failed      bool
	done        bool
	failMessage string
	currentIdx  int

	// showActivity enables the transient activity ticker: the terminal box
	// keeps only step-level progress, while high-frequency detail lines
	// scroll through the last few ticker slots at the bottom of the box.
	showActivity bool
	activity     []string
}

// activityLines is how many detail lines the ticker retains — older
// activity scrolls away automatically.
const activityLines = 3

// NewCommandView creates a view for running a generic command with terminal output
func NewCommandView(title string) *AnalyzingView {
	return &AnalyzingView{
		phases:   []AnalysisPhase{},
		header:   components.NewTitleHeader(title),
		spinner:  components.NewSpinner(),
		terminal: components.NewTerminalOutput(14, 300),
	}
}

// NewAnalysisView creates the journey-analysis view: the terminal box shows
// only the important steps (persistent), and per-tool activity scrolls
// through a small ticker underneath so users still see work happening.
func NewAnalysisView(title string) *AnalyzingView {
	v := NewCommandView(title)
	v.showActivity = true
	return v
}

// AddActivity pushes a detail line onto the transient ticker. On views
// without a ticker it falls back to the terminal log.
func (v *AnalyzingView) AddActivity(line string) {
	if !v.showActivity {
		v.terminal.AddLine(line)
		return
	}
	v.activity = append(v.activity, line)
	if len(v.activity) > activityLines {
		v.activity = v.activity[len(v.activity)-activityLines:]
	}
}

// SetSize updates dimensions
func (v *AnalyzingView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
	termHeight := height - 16
	if termHeight < 6 {
		termHeight = 6
	}
	v.terminal.SetSize(width, termHeight)
}

// TickSpinner advances spinner animation
func (v *AnalyzingView) TickSpinner() {
	v.spinner.Tick()
}

// UpdatePhase updates a phase's progress and logs the message to terminal
// Legacy method kept for backward compatibility with NextStepOutputMsg
func (v *AnalyzingView) UpdatePhase(index int, progress float64, message string) {
	// For generic output messages (index == -1), just log to terminal
	if index == -1 {
		if message != "" {
			v.terminal.AddLine(message)
		}
		return
	}
	// For valid indices, update existing phase (legacy support)
	if index >= 0 && index < len(v.phases) {
		v.phases[index].Progress = progress
		v.phases[index].Active = progress < 1.0
		if progress >= 1.0 {
			v.phases[index].Done = true
			v.phases[index].Active = false
			// Activate next phase
			if index+1 < len(v.phases) {
				v.phases[index+1].Active = true
				v.currentIdx = index + 1
			}
		}
	}
	// Log the message to terminal output
	if message != "" {
		v.terminal.AddLine(message)
	}
}

// UpdatePhaseByName updates or creates a phase by name
func (v *AnalyzingView) UpdatePhaseByName(phaseName string, progress float64, message string) {
	// Find existing phase or create new one
	var phase *AnalysisPhase
	var phaseIdx int
	found := false
	for i := range v.phases {
		if v.phases[i].Name == phaseName {
			phase = &v.phases[i]
			phaseIdx = i
			found = true
			break
		}
	}

	if !found {
		// Create new phase
		v.phases = append(v.phases, AnalysisPhase{
			Name:     phaseName,
			Progress: progress,
			Active:   progress < 1.0,
			Done:     progress >= 1.0,
		})
		phaseIdx = len(v.phases) - 1
	} else {
		// Update existing phase
		phase.Progress = progress
		phase.Active = progress < 1.0
		phase.Done = progress >= 1.0
	}

	// Deactivate all other phases
	for i := range v.phases {
		if i != phaseIdx {
			v.phases[i].Active = false
		}
	}

	v.currentIdx = phaseIdx

	// Log the message to terminal output
	if message != "" {
		v.terminal.AddLine(message)
	}
}

// SetDone marks the command as successfully completed
func (v *AnalyzingView) SetDone() {
	v.done = true
	v.terminal.AddLine(constants.StatusIconCompleted + " " + constants.StatusDone)
}

// SetCommandFailed marks the view as failed with the error visible in terminal
func (v *AnalyzingView) SetCommandFailed(errMsg string) {
	v.failed = true
	v.failMessage = errMsg
	if errMsg != "" {
		v.terminal.AddLine("")
		v.terminal.AddLine("ERROR: " + errMsg)
	}
}

// IsDone returns true if the command completed (success or failure)
func (v *AnalyzingView) IsDone() bool {
	return v.done || v.failed
}

// SetPhaseError marks a phase as failed
func (v *AnalyzingView) SetPhaseError(index int, errMsg string) {
	if index >= 0 && index < len(v.phases) {
		v.phases[index].Error = errMsg
		v.phases[index].Active = false
		v.failed = true
	}
	if errMsg != "" {
		v.terminal.AddLine("ERROR: " + errMsg)
	}
}

// AllPhasesDone returns true if all phases are complete
func (v *AnalyzingView) AllPhasesDone() bool {
	for _, p := range v.phases {
		if !p.Done {
			return false
		}
	}
	return true
}

// HasFailed returns true if analysis failed
func (v *AnalyzingView) HasFailed() bool {
	return v.failed
}

// ScrollUp scrolls the terminal output up
func (v *AnalyzingView) ScrollUp(n int) {
	v.terminal.ScrollUp(n)
}

// ScrollDown scrolls the terminal output down
func (v *AnalyzingView) ScrollDown(n int) {
	v.terminal.ScrollDown(n)
}

// GetCurrentPhase returns the current active phase name, or empty string if none
func (v *AnalyzingView) GetCurrentPhase() string {
	for _, p := range v.phases {
		if p.Active {
			return p.Name
		}
	}
	return ""
}

// Render the analyzing view
func (v *AnalyzingView) Render() string {
	sectionWidth := v.width - 8
	if sectionWidth < 60 {
		sectionWidth = 60
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	// Current phase status
	var statusLine string
	if v.failed {
		statusLine = styles.Error.Render(constants.StatusIconFailed + " " + constants.StatusFailed)
		if v.failMessage != "" {
			statusLine += "\n" + lipgloss.NewStyle().
				Foreground(styles.MutedColor).
				Width(sectionWidth).
				Render("  "+v.failMessage)
		}
	} else if v.done {
		statusLine = styles.SuccessText.Render(constants.StatusIconCompleted + " " + constants.StatusCompleted)
	} else if len(v.phases) > 0 && v.AllPhasesDone() {
		statusLine = styles.SuccessText.Render(constants.StatusIconCompleted + " " + constants.StatusCompleted)
	} else {
		currentPhase := ""
		for _, p := range v.phases {
			if p.Active {
				currentPhase = p.Name
				break
			}
		}
		if currentPhase != "" {
			statusLine = v.spinner.Render() + " " + styles.Body.Render(currentPhase)
		} else {
			statusLine = v.spinner.Render() + " " + styles.Body.Render(constants.StatusInProgress)
		}
	}

	// Terminal output, with the transient activity ticker pinned to the
	// bottom of the box (journey analysis only). The newest line carries
	// the spinner frame so the ticker visibly moves even while a single
	// long-running tool call is in flight.
	var ticker []string
	if v.showActivity && !v.done && !v.failed && len(v.activity) > 0 {
		for i, line := range v.activity {
			if i == len(v.activity)-1 {
				line = v.spinner.Frame() + " " + line
			} else {
				line = "  " + line
			}
			ticker = append(ticker, line)
		}
	}
	termOutput := v.terminal.RenderWithTicker(sectionWidth, ticker)

	// Footer
	var footerContent string
	if v.failed {
		footerContent = components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyR, Desc: constants.HelpDescRetry},
			{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
			{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}, v.width)
	} else if v.done {
		footerContent = components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
			{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}, v.width)
	} else {
		footerContent = components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescCancel},
			{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}, v.width)
	}
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(footerContent)

	// Combine
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		statusLine,
		"",
		termOutput,
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

// GetHelpItems returns context-specific help
func (v *AnalyzingView) GetHelpItems() []components.HelpItem {
	if v.failed {
		return []components.HelpItem{
			{Key: constants.HelpKeyR, Desc: constants.HelpDescRetry},
			{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
			{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}
	}
	if v.done {
		return []components.HelpItem{
			{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
			{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}
	}
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescCancel},
		{Key: constants.HelpKeyG, Desc: constants.HelpDescPlayMiniGame},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
