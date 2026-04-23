package views

import (
	"os"
	"path/filepath"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/lipgloss"
)

// ExistingAnalysisChoice tracks the user's choice when existing analysis is found
type ExistingAnalysisChoice int

const (
	ChoiceNotAsked ExistingAnalysisChoice = iota
	ChoiceAsking
	ChoiceViewAnalysis
	ChoiceRerunAnalysis
)

// ProjectDirView handles project directory selection
type ProjectDirView struct {
	width       int
	height      int
	textInput   textinput.Model
	buttonGroup *components.ButtonGroup
	inputFocus  bool
	currentDir  string
	isValid     bool
	validMsg    string
	warningMsg  string
	header      *components.WizardHeader
	browsing         bool
	dirBrowser       *components.DirBrowser
	browseButtons    *components.ButtonGroup
	browseFocusList  bool

	// Existing analysis detection
	existingAnalysis      ExistingAnalysisChoice
	existingButtonGroup   *components.ButtonGroup
	hasSkeneContext        bool
	noSchemaDetected       bool // true when the last analyse-journey run didn't produce engine.yaml

	// Next steps modal (shown over the existing analysis prompt)
	showNextSteps bool
	nextStepsView *NextStepsView
}

// NewProjectDirView creates a new project directory view
func NewProjectDirView() *ProjectDirView {
	cwd, _ := os.Getwd()

	ti := textinput.New()
	ti.Placeholder = cwd
	ti.SetValue(cwd)
	ti.CharLimit = 256
	ti.Width = 50
	ti.Focus()

	bg := components.NewButtonGroup(constants.ButtonUseCurrent, constants.ButtonBrowse, constants.ButtonContinue)
	bg.SetActiveIndex(-1)

	v := &ProjectDirView{
		textInput:        ti,
		buttonGroup:      bg,
		inputFocus:       true,
		currentDir:       cwd,
		isValid:          true,
		header:           components.NewTitleHeader(constants.StepNameProjectDir),
		existingAnalysis: ChoiceNotAsked,
	}

	v.validatePath()
	return v
}

// SetSize updates dimensions
func (v *ProjectDirView) SetSize(width, height int) {
	v.width = width
	v.height = height
	v.header.SetWidth(width)
	
	// Update text input width to match available section width
	sectionWidth := width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}
	// Account for box padding (typically 2-4 chars on each side)
	inputWidth := sectionWidth - 4
	if inputWidth < 50 {
		inputWidth = 50
	}
	v.textInput.Width = inputWidth
}

// Update handles text input updates
func (v *ProjectDirView) Update(msg interface{}) {
	if v.inputFocus {
		v.textInput, _ = v.textInput.Update(msg)
		v.validatePath()
	}
}

// HandleTab toggles between input and buttons
func (v *ProjectDirView) HandleTab() {
	v.inputFocus = !v.inputFocus
	if v.inputFocus {
		v.textInput.Focus()
		v.buttonGroup.SetActiveIndex(-1)
	} else {
		v.textInput.Blur()
		v.buttonGroup.SetActiveIndex(0)
	}
}

// HandleLeft handles left key in buttons
func (v *ProjectDirView) HandleLeft() {
	if v.existingAnalysis == ChoiceAsking && v.existingButtonGroup != nil {
		v.existingButtonGroup.Previous()
		return
	}
	if !v.inputFocus {
		v.buttonGroup.Previous()
	}
}

// HandleRight handles right key in buttons
func (v *ProjectDirView) HandleRight() {
	if v.existingAnalysis == ChoiceAsking && v.existingButtonGroup != nil {
		v.existingButtonGroup.Next()
		return
	}
	if !v.inputFocus {
		v.buttonGroup.Next()
	}
}

// IsInputFocused returns if the input is focused
func (v *ProjectDirView) IsInputFocused() bool {
	return v.inputFocus && v.existingAnalysis != ChoiceAsking
}

// GetButtonLabel returns the selected button label
func (v *ProjectDirView) GetButtonLabel() string {
	return v.buttonGroup.GetActiveLabel()
}

// UseCurrentDir sets the current working directory
func (v *ProjectDirView) UseCurrentDir() {
	cwd, _ := os.Getwd()
	v.textInput.SetValue(cwd)
	v.currentDir = cwd
	v.validatePath()
}

// StartBrowsing activates the directory browser from the current path
func (v *ProjectDirView) StartBrowsing() {
	startPath := v.GetProjectDir()
	v.dirBrowser = components.NewDirBrowser(startPath)
	browserHeight := v.height - 16
	if browserHeight < 6 {
		browserHeight = 6
	}
	if browserHeight > 18 {
		browserHeight = 18
	}
	v.dirBrowser.SetHeight(browserHeight)
	v.browseButtons = components.NewButtonGroup(constants.ButtonSelectDir, constants.ButtonCancel)
	v.browseButtons.SetActiveIndex(-1)
	v.browseFocusList = true
	v.browsing = true
	v.textInput.Blur()
}

// StopBrowsing exits the directory browser without selecting
func (v *ProjectDirView) StopBrowsing() {
	v.browsing = false
	v.dirBrowser = nil
	v.browseButtons = nil
	v.inputFocus = false
}

// IsBrowsing returns true if the directory browser is active
func (v *ProjectDirView) IsBrowsing() bool {
	return v.browsing
}

// BrowseFocusOnList returns true if the dir listing has focus (not buttons)
func (v *ProjectDirView) BrowseFocusOnList() bool {
	return v.browseFocusList
}

// BrowseConfirm selects the current browsed directory and exits browsing
func (v *ProjectDirView) BrowseConfirm() {
	if v.dirBrowser == nil {
		return
	}
	selectedPath := v.dirBrowser.CurrentPath()
	v.textInput.SetValue(selectedPath)
	v.currentDir = selectedPath
	v.validatePath()
	v.browsing = false
	v.dirBrowser = nil
	v.browseButtons = nil
	v.inputFocus = false
}

// GetBrowseButtonLabel returns the active browse button label
func (v *ProjectDirView) GetBrowseButtonLabel() string {
	if v.browseButtons == nil {
		return ""
	}
	return v.browseButtons.GetActiveLabel()
}

// HandleBrowseTab toggles focus between dir listing and buttons
func (v *ProjectDirView) HandleBrowseTab() {
	v.browseFocusList = !v.browseFocusList
	if v.browseFocusList {
		v.browseButtons.SetActiveIndex(-1)
	} else {
		v.browseButtons.SetActiveIndex(0)
	}
}

// HandleBrowseLeft handles left key in browse button area
func (v *ProjectDirView) HandleBrowseLeft() {
	if !v.browseFocusList && v.browseButtons != nil {
		v.browseButtons.Previous()
	}
}

// HandleBrowseRight handles right key in browse button area
func (v *ProjectDirView) HandleBrowseRight() {
	if !v.browseFocusList && v.browseButtons != nil {
		v.browseButtons.Next()
	}
}

// HandleBrowseKey handles key input for the directory listing
func (v *ProjectDirView) HandleBrowseKey(key string) {
	if v.dirBrowser == nil {
		return
	}
	switch key {
	case "up", "k":
		v.dirBrowser.CursorUp()
	case "down", "j":
		v.dirBrowser.CursorDown()
	case "enter":
		if v.dirBrowser.SelectedIsDir() {
			v.dirBrowser.Enter()
		}
	case "backspace":
		v.dirBrowser.GoUp()
	case ".":
		v.dirBrowser.ToggleHidden()
	}
}

// GetProjectDir returns the entered/selected directory
func (v *ProjectDirView) GetProjectDir() string {
	val := v.textInput.Value()
	if val == "" {
		return v.currentDir
	}
	if len(val) > 0 && val[0] == '~' {
		home, _ := os.UserHomeDir()
		val = filepath.Join(home, val[1:])
	}
	return val
}

// IsValid returns if the path is valid
func (v *ProjectDirView) IsValid() bool {
	return v.isValid
}

// HasWarning returns true if there's a non-blocking warning
func (v *ProjectDirView) HasWarning() bool {
	return v.warningMsg != ""
}

// CheckForExistingAnalysis checks if a Skene bundle directory exists in the
// selected directory (the new `skene/` name or the legacy `skene-context/`)
// and transitions to the choice prompt if found.
func (v *ProjectDirView) CheckForExistingAnalysis() bool {
	path := v.GetProjectDir()

	if existingBundleDir(path) != "" {
		v.hasSkeneContext = true
		v.existingAnalysis = ChoiceAsking
		v.existingButtonGroup = v.buildExistingButtons(path)
		v.textInput.Blur()
		v.inputFocus = false
		return true
	}

	v.hasSkeneContext = false
	return false
}

// existingBundleDir returns the bundle directory name actually present under
// projectDir, preferring the canonical `skene/` over the legacy `skene-context/`.
// Returns "" when neither exists.
func existingBundleDir(projectDir string) string {
	for _, name := range []string{constants.OutputDirName, constants.LegacyOutputDirName} {
		if info, err := os.Stat(filepath.Join(projectDir, name)); err == nil && info.IsDir() {
			return name
		}
	}
	return ""
}

// buildExistingButtons creates the button group based on which files exist.
// "View Journey" only appears when engine.yaml is present. When engine.yaml
// is missing, both "Analyse Journey" and "Analyse Codebase" are offered so
// the user can fall back to the full analysis if schema detection failed.
func (v *ProjectDirView) buildExistingButtons(projectDir string) *components.ButtonGroup {
	bundle := existingBundleDir(projectDir)
	if bundle == "" {
		bundle = constants.OutputDirName
	}
	enginePath := filepath.Join(projectDir, bundle, constants.EngineFile)
	if _, err := os.Stat(enginePath); err == nil {
		return components.NewButtonGroup(constants.ProjectDirViewAnalysis, constants.ProjectDirRerunAnalysis)
	}
	return components.NewButtonGroup(constants.ProjectDirRunAnalysis, constants.ProjectDirRunCodebaseAnalysis)
}

// IsAskingExistingChoice returns true if prompting for existing analysis choice
func (v *ProjectDirView) IsAskingExistingChoice() bool {
	return v.existingAnalysis == ChoiceAsking
}

// GetExistingChoiceLabel returns the selected button label for existing analysis
func (v *ProjectDirView) GetExistingChoiceLabel() string {
	if v.existingButtonGroup == nil {
		return ""
	}
	return v.existingButtonGroup.GetActiveLabel()
}

// SetExistingChoice records the user's choice
func (v *ProjectDirView) SetExistingChoice(view bool) {
	if view {
		v.existingAnalysis = ChoiceViewAnalysis
	} else {
		v.existingAnalysis = ChoiceRerunAnalysis
	}
}

// ResetExistingChoice re-checks the output directory and re-triggers the
// existing analysis prompt if a Skene bundle directory still exists.
func (v *ProjectDirView) ResetExistingChoice() {
	if !v.CheckForExistingAnalysis() {
		v.existingAnalysis = ChoiceNotAsked
		v.existingButtonGroup = nil
		v.inputFocus = true
		v.textInput.Focus()
	}
}

// DismissExistingChoice resets the existing analysis prompt
func (v *ProjectDirView) DismissExistingChoice() {
	v.existingAnalysis = ChoiceNotAsked
	v.existingButtonGroup = nil
	v.inputFocus = false
	v.buttonGroup.SetActiveIndex(0)
}

// ShowNextSteps opens the next-steps modal overlay.
func (v *ProjectDirView) ShowNextSteps(outputDir string) {
	v.showNextSteps = true
	v.nextStepsView = NewNextStepsViewWithContext(outputDir)
	v.nextStepsView.SetSize(v.width, v.height)
}

// HideNextSteps closes the next-steps modal overlay.
func (v *ProjectDirView) HideNextSteps() {
	v.showNextSteps = false
}

// IsShowingNextSteps returns whether the next-steps modal is visible.
func (v *ProjectDirView) IsShowingNextSteps() bool {
	return v.showNextSteps
}

// GetNextStepsView returns the embedded next-steps view.
func (v *ProjectDirView) GetNextStepsView() *NextStepsView {
	return v.nextStepsView
}

// HasExistingAnalysis returns true if the skene output directory was detected
func (v *ProjectDirView) HasExistingAnalysis() bool {
	return v.hasSkeneContext
}

// SetNoSchemaDetected marks that the last analyse-journey run did not produce
// engine.yaml, so the prompt should explain the fallback.
func (v *ProjectDirView) SetNoSchemaDetected(detected bool) {
	v.noSchemaDetected = detected
}

// HasNoSchemaDetected returns the no-schema flag.
func (v *ProjectDirView) HasNoSchemaDetected() bool {
	return v.noSchemaDetected
}

func (v *ProjectDirView) validatePath() {
	path := v.GetProjectDir()

	info, err := os.Stat(path)
	if err != nil {
		v.isValid = false
		v.validMsg = constants.ProjectDirNotFound
		v.warningMsg = ""
		v.hasSkeneContext = false
		return
	}

	if !info.IsDir() {
		v.isValid = false
		v.validMsg = constants.ProjectDirNotADir
		v.warningMsg = ""
		v.hasSkeneContext = false
		return
	}

	v.isValid = true
	v.validMsg = ""

	if existingBundleDir(path) != "" {
		v.hasSkeneContext = true
	} else {
		v.hasSkeneContext = false
	}

	// Check for common project indicators
	hasProject := false
	projectMarkers := []string{
		"package.json", "pyproject.toml", "requirements.txt",
		"go.mod", "Cargo.toml", "pom.xml", "build.gradle",
		".git", "Makefile",
	}
	for _, marker := range projectMarkers {
		if _, err := os.Stat(filepath.Join(path, marker)); err == nil {
			hasProject = true
			break
		}
	}

	if !hasProject {
		v.warningMsg = constants.ProjectDirNoProject
	} else {
		v.warningMsg = ""
	}
}

// Render the project directory view
func (v *ProjectDirView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Wizard header
	wizHeader := lipgloss.NewStyle().Width(sectionWidth).Render(v.header.Render())

	if v.browsing && v.dirBrowser != nil {
		browserSection := v.dirBrowser.Render(sectionWidth)

		browseBtns := lipgloss.NewStyle().
			Width(sectionWidth).
			Align(lipgloss.Center).
			Render(v.browseButtons.Render())

		footer := lipgloss.NewStyle().
			Width(v.width).
			Align(lipgloss.Center).
			Render(components.FooterHelp([]components.HelpItem{
				{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescNavigate},
				{Key: constants.HelpKeyEnter, Desc: constants.HelpDescOpenFolder},
				{Key: constants.HelpKeyTab, Desc: constants.HelpDescSwitchFocus},
				{Key: constants.HelpKeyEsc, Desc: constants.HelpDescCancel},
			}, v.width))

		content := lipgloss.JoinVertical(
			lipgloss.Left,
			wizHeader,
			"",
			browserSection,
			"",
			browseBtns,
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

	// Existing analysis choice view
	if v.existingAnalysis == ChoiceAsking {
		rendered := v.renderExistingAnalysisChoice(wizHeader, sectionWidth)
		if v.showNextSteps {
			rendered = v.renderNextStepsModal()
		}
		return rendered
	}

	// Directory selection section
	dirSection := v.renderDirSection(sectionWidth)

	// Buttons
	buttons := lipgloss.NewStyle().
		Width(sectionWidth).
		Align(lipgloss.Center).
		Render(v.buttonGroup.Render())

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.WizardInputHelp(v.width))

	// Combine
	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		dirSection,
		"",
		buttons,
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

func (v *ProjectDirView) renderExistingAnalysisChoice(wizHeader string, width int) string {
	headerText := constants.ProjectDirExistingHeader
	msgText := constants.ProjectDirExistingMsg
	if v.noSchemaDetected {
		headerText = constants.ProjectDirNoSchemaHeader
		msgText = constants.ProjectDirNoSchemaMsg
	}

	header := styles.SectionHeader.Render(headerText)
	msg := lipgloss.NewStyle().Width(width - 8).Render(styles.Body.Render(msgText))
	bundle := existingBundleDir(v.GetProjectDir())
	if bundle == "" {
		bundle = constants.OutputDirName
	}
	path := lipgloss.NewStyle().
		Foreground(styles.MutedColor).Width(width-8).
		Render("Found: " + filepath.Join(v.GetProjectDir(), bundle) + "/")
	question := styles.Accent.Render(constants.ProjectDirExistingQ)

	buttons := lipgloss.NewStyle().
		Width(width).
		Align(lipgloss.Center).
		Render(v.existingButtonGroup.Render())

	innerContent := lipgloss.JoinVertical(
		lipgloss.Left,
		header,
		msg,
		path,
		"",
		question,
	)

	box := styles.Box.Width(width).Render(innerContent)

	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp([]components.HelpItem{
			{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescSelect},
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirm},
			{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}, v.width))

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		wizHeader,
		"",
		box,
		"",
		buttons,
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

func (v *ProjectDirView) renderNextStepsModal() string {
	modalWidth := 60
	if v.width < 70 {
		modalWidth = v.width - 10
	}
	if modalWidth < 45 {
		modalWidth = 45
	}
	modalContent := v.nextStepsView.RenderModal(modalWidth)
	return lipgloss.Place(v.width, v.height, lipgloss.Center, lipgloss.Center, modalContent)
}

func (v *ProjectDirView) renderDirSection(width int) string {
	header := styles.SectionHeader.Render(constants.ProjectDirHeader)
	subtitle := styles.Muted.Render(constants.ProjectDirSubtitle)

	// Directory input
	dirLabel := styles.Label.Render("Directory:")
	inputField := v.textInput.View()

	// Validation status
	var validationLine string
	if !v.isValid && v.validMsg != "" {
		validationLine = styles.Error.Render("X " + v.validMsg)
	} else if v.warningMsg != "" {
		validationLine = lipgloss.NewStyle().Foreground(styles.WarningColor).Width(width-8).Render("! " + v.warningMsg)
	} else if v.isValid && v.hasSkeneContext {
		validationLine = styles.SuccessText.Render(constants.ProjectDirValidExisting)
	} else if v.isValid {
		validationLine = styles.SuccessText.Render(constants.ProjectDirValid)
	}

	content := lipgloss.JoinVertical(
		lipgloss.Left,
		header,
		subtitle,
		"",
		dirLabel,
		inputField,
		"",
		validationLine,
	)

	return styles.Box.Width(width).Render(content)
}

// GetHelpItems returns context-specific help
func (v *ProjectDirView) GetHelpItems() []components.HelpItem {
	if v.existingAnalysis == ChoiceAsking {
		return []components.HelpItem{
			{Key: constants.HelpKeyLeftRight, Desc: constants.HelpDescSelectOption},
			{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirm},
			{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
			{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
		}
	}
	return []components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescConfirm},
		{Key: constants.HelpKeyTab, Desc: constants.HelpDescSwitchFocus},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescGoBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
