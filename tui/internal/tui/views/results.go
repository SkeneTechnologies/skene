package views

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// fileEntry tracks a dashboard file's presence on disk.
type fileEntry struct {
	def     constants.DashboardFile
	present bool
}

// ResultsView shows the analysis output files as a selectable list.
type ResultsView struct {
	width       int
	height      int
	files       []fileEntry
	selectedIdx int
	projectName string
	outputDir   string

	showNextSteps    bool
	nextStepsView    *NextStepsView
}

// NewResultsView creates a dashboard view. projectName is displayed as the
// heading; outputDir is the skene output directory to scan for files.
func NewResultsView(projectName, outputDir string) *ResultsView {
	v := &ResultsView{
		projectName:   projectName,
		outputDir:     outputDir,
		nextStepsView: NewNextStepsView(),
	}
	v.scanFiles()
	v.selectFirstPresent()
	return v
}

// scanFiles checks which output files exist on disk.
func (v *ResultsView) scanFiles() {
	v.files = make([]fileEntry, len(constants.DashboardFiles))
	for i, def := range constants.DashboardFiles {
		path := filepath.Join(v.outputDir, def.Filename)
		_, err := os.Stat(path)
		v.files[i] = fileEntry{def: def, present: err == nil}
	}
}

// selectFirstPresent moves the cursor to the first present file.
func (v *ResultsView) selectFirstPresent() {
	for i, f := range v.files {
		if f.present {
			v.selectedIdx = i
			return
		}
	}
	v.selectedIdx = 0
}

// SetSize updates dimensions.
func (v *ResultsView) SetSize(width, height int) {
	v.width = width
	v.height = height
	if v.nextStepsView != nil {
		v.nextStepsView.SetSize(width, height)
	}
}

// HandleUp moves selection up, skipping missing files.
func (v *ResultsView) HandleUp() {
	if v.showNextSteps {
		v.nextStepsView.HandleUp()
		return
	}
	for i := v.selectedIdx - 1; i >= 0; i-- {
		if v.files[i].present {
			v.selectedIdx = i
			return
		}
	}
}

// HandleDown moves selection down, skipping missing files.
func (v *ResultsView) HandleDown() {
	if v.showNextSteps {
		v.nextStepsView.HandleDown()
		return
	}
	for i := v.selectedIdx + 1; i < len(v.files); i++ {
		if v.files[i].present {
			v.selectedIdx = i
			return
		}
	}
}

// GetSelectedFile returns the currently selected file definition, or nil
// if the selection is on a missing file.
func (v *ResultsView) GetSelectedFile() *constants.DashboardFile {
	if v.selectedIdx < 0 || v.selectedIdx >= len(v.files) {
		return nil
	}
	entry := v.files[v.selectedIdx]
	if !entry.present {
		return nil
	}
	return &entry.def
}

// IsShowingNextSteps returns whether the next-steps modal is visible.
func (v *ResultsView) IsShowingNextSteps() bool {
	return v.showNextSteps
}

// ShowNextSteps opens the next-steps modal overlay.
func (v *ResultsView) ShowNextSteps() {
	v.showNextSteps = true
	v.nextStepsView = NewNextStepsViewWithContext(v.outputDir)
	v.nextStepsView.SetSize(v.width, v.height)
}

// HideNextSteps closes the next-steps modal overlay.
func (v *ResultsView) HideNextSteps() {
	v.showNextSteps = false
}

// GetNextStepsView returns the embedded next-steps view.
func (v *ResultsView) GetNextStepsView() *NextStepsView {
	return v.nextStepsView
}

// RefreshContent rescans files from disk.
func (v *ResultsView) RefreshContent(outputDir string) {
	v.outputDir = outputDir
	v.scanFiles()
}

// Render the dashboard.
func (v *ResultsView) Render() string {
	sectionWidth := v.width - 20
	if sectionWidth < 60 {
		sectionWidth = 60
	}
	if sectionWidth > 80 {
		sectionWidth = 80
	}

	// Project name
	projectHeader := styles.Accent.Render(v.projectName)

	// Info box
	infoTitle := styles.Title.Render(constants.DashboardTitle)
	infoSubtitle := styles.Body.Render(constants.DashboardSubtitle)
	infoBox := styles.Box.Width(sectionWidth).Render(
		lipgloss.JoinVertical(lipgloss.Left, infoTitle, infoSubtitle),
	)

	// Files section
	filesHeader := styles.Title.Render(constants.DashboardFilesHeader)
	filesDesc := lipgloss.NewStyle().
		Foreground(styles.MutedColor).
		Width(sectionWidth - 6).
		Render(constants.DashboardFilesDesc)
	filesList := v.renderFileList(sectionWidth - 6)

	filesContent := lipgloss.JoinVertical(lipgloss.Left,
		filesHeader,
		filesDesc,
		"",
		filesList,
	)
	filesBox := styles.Box.Width(sectionWidth).Render(filesContent)

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(v.renderFooterHelp())

	// Main content
	content := lipgloss.JoinVertical(lipgloss.Left,
		projectHeader,
		"",
		infoBox,
		"",
		filesBox,
	)

	mainContent := lipgloss.Place(
		v.width,
		v.height-3,
		lipgloss.Center,
		lipgloss.Top,
		lipgloss.NewStyle().Padding(1, 2).Render(content),
	)

	rendered := mainContent + "\n" + footer

	if v.showNextSteps {
		rendered = v.renderWithModal(rendered)
	}

	return rendered
}

func (v *ResultsView) renderFileList(maxWidth int) string {
	var items []string
	for i, entry := range v.files {
		items = append(items, v.renderFileItem(i, entry, maxWidth))
		if i < len(v.files)-1 {
			items = append(items, "")
		}
	}
	return lipgloss.JoinVertical(lipgloss.Left, items...)
}

func (v *ResultsView) renderFileItem(idx int, entry fileEntry, maxWidth int) string {
	isSelected := idx == v.selectedIdx && !v.showNextSteps

	if !entry.present {
		name := styles.ListItemDimmed.Render(entry.def.DisplayName)
		desc := lipgloss.NewStyle().
			Foreground(styles.MutedColor).
			PaddingLeft(2).
			Width(maxWidth).
			Render(entry.def.Description + " — not yet generated.")
		return name + "\n" + desc
	}

	var name string
	if isSelected {
		name = styles.ListItemSelected.Render(entry.def.DisplayName)
	} else {
		name = styles.ListItem.Render(entry.def.DisplayName)
	}
	desc := lipgloss.NewStyle().
		Foreground(styles.MutedColor).
		PaddingLeft(2).
		Width(maxWidth).
		Render(entry.def.Description)
	return name + "\n" + desc
}

func (v *ResultsView) renderFooterHelp() string {
	return components.FooterHelp([]components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescNavigate},
		{Key: constants.HelpKeyEnter, Desc: "open"},
		{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}, v.width)
}

func (v *ResultsView) renderWithModal(_ string) string {
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

// GetHelpItems returns help items for the results view.
func (v *ResultsView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescFocus},
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescSelect},
		{Key: constants.HelpKeyN, Desc: constants.HelpDescNextSteps},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}

// FileDetailView shows the content of a single file with scrolling.
type FileDetailView struct {
	width      int
	height     int
	fileDef    constants.DashboardFile
	rawContent string
	content    string
	modTime    string
	formatted  bool // true when content has custom formatting (skip lipgloss re-wrap)
	viewport   scrollableViewport
}

// scrollableViewport is a minimal viewport for scrolling content.
type scrollableViewport struct {
	content string
	offset  int
	height  int
	width   int
	lines   []string
}

func (sv *scrollableViewport) setContent(content string, width int) {
	sv.width = width
	sv.content = content
	sv.offset = 0
	sv.lines = splitLines(content)
}

func (sv *scrollableViewport) scrollUp(n int) {
	sv.offset -= n
	if sv.offset < 0 {
		sv.offset = 0
	}
}

func (sv *scrollableViewport) scrollDown(n int) {
	maxOffset := len(sv.lines) - sv.height
	if maxOffset < 0 {
		maxOffset = 0
	}
	sv.offset += n
	if sv.offset > maxOffset {
		sv.offset = maxOffset
	}
}

func (sv *scrollableViewport) view() string {
	if len(sv.lines) == 0 {
		return ""
	}
	end := sv.offset + sv.height
	if end > len(sv.lines) {
		end = len(sv.lines)
	}
	start := sv.offset
	if start > len(sv.lines) {
		start = len(sv.lines)
	}
	visible := sv.lines[start:end]
	result := ""
	for i, line := range visible {
		if i > 0 {
			result += "\n"
		}
		result += line
	}
	return result
}

func splitLines(s string) []string {
	if s == "" {
		return nil
	}
	var lines []string
	current := ""
	for _, ch := range s {
		if ch == '\n' {
			lines = append(lines, current)
			current = ""
		} else {
			current += string(ch)
		}
	}
	lines = append(lines, current)
	return lines
}

// NewFileDetailView creates a file detail view for the given file.
func NewFileDetailView(def constants.DashboardFile, outputDir string) *FileDetailView {
	filePath := filepath.Join(outputDir, def.Filename)
	rawContent := ""
	modTime := ""

	data, err := os.ReadFile(filePath)
	if err == nil {
		rawContent = string(data)
	}

	info, err := os.Stat(filePath)
	if err == nil {
		modTime = fmt.Sprintf(constants.FileDetailUpdatedFormat, info.ModTime().Format("02.01.2006 15:04:05"))
	}

	return &FileDetailView{
		fileDef:    def,
		rawContent: rawContent,
		content:    rawContent,
		modTime:    modTime,
	}
}

// formatNewFeatures parses the new-features.yaml JSON array and returns a
// human-readable summary of each feature. contentWidth controls divider and
// wrap width; pass 0 to use a sensible default.
func formatNewFeatures(raw string, contentWidth int) string {
	var features []struct {
		Name        string `json:"name"`
		Key         string `json:"key"`
		Source      string `json:"source"`
		HowItWorks  string `json:"how_it_works"`
		MatchIntent string `json:"match_intent"`
		Action      *struct {
			Use string `json:"use"`
		} `json:"action"`
	}

	if err := json.Unmarshal([]byte(raw), &features); err != nil {
		return ""
	}

	if contentWidth < 40 {
		contentWidth = 60
	}
	w2 := contentWidth - 2 // "  " prefix

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("  %d feature(s) planned\n", len(features)))

	for i, f := range features {
		sb.WriteString("\n")
		sb.WriteString(styles.Divider(contentWidth))
		sb.WriteString("\n\n")

		title := f.Name
		if title == "" {
			title = f.Key
		}
		styledTitle := styles.AccentStyle().Bold(true).Render(fmt.Sprintf("%d. %s", i+1, title))
		sb.WriteString("  " + styledTitle + "\n\n")

		sb.WriteString(fmt.Sprintf("  Source:  %s\n", f.Source))
		if f.Action != nil {
			sb.WriteString(fmt.Sprintf("  Action:  %s\n", f.Action.Use))
		}

		if f.HowItWorks != "" {
			sb.WriteString("\n")
			for _, line := range wrapText(f.HowItWorks, w2) {
				sb.WriteString("  " + line + "\n")
			}
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Divider(contentWidth))
	return sb.String()
}

// formatForDisplay routes a file to its human-readable formatter.
func formatForDisplay(fileID, raw string, width int) string {
	switch fileID {
	case "new-features":
		return formatNewFeatures(raw, width)
	case "manifest":
		return formatManifest(raw, width)
	case "template":
		return formatTemplate(raw, width)
	default:
		return ""
	}
}

// formatManifest renders growth-manifest.json as a readable summary.
func formatManifest(raw string, contentWidth int) string {
	var m struct {
		ProjectName string `json:"project_name"`
		Description string `json:"description"`
		TechStack   struct {
			Framework      string   `json:"framework"`
			Language       string   `json:"language"`
			Database       string   `json:"database"`
			Auth           string   `json:"auth"`
			Deployment     string   `json:"deployment"`
			PackageManager string   `json:"package_manager"`
			Services       []string `json:"services"`
		} `json:"tech_stack"`
		Industry struct {
			Primary   string   `json:"primary"`
			Secondary []string `json:"secondary"`
		} `json:"industry"`
		CurrentGrowthFeatures []struct {
			FeatureName     string   `json:"feature_name"`
			DetectedIntent  string   `json:"detected_intent"`
			ConfidenceScore float64  `json:"confidence_score"`
			GrowthPotential []string `json:"growth_potential"`
		} `json:"current_growth_features"`
		GrowthOpportunities []struct {
			FeatureName string `json:"feature_name"`
			Description string `json:"description"`
			Priority    string `json:"priority"`
		} `json:"growth_opportunities"`
	}

	if err := json.Unmarshal([]byte(raw), &m); err != nil {
		return ""
	}

	if contentWidth < 40 {
		contentWidth = 60
	}
	// Wrap widths accounting for indentation prefixes
	w2 := contentWidth - 2  // "  " prefix
	w5 := contentWidth - 5  // "     " prefix

	var sb strings.Builder

	// Project header
	sb.WriteString("  " + styles.AccentStyle().Bold(true).Render(m.ProjectName) + "\n\n")
	for _, line := range wrapText(m.Description, w2) {
		sb.WriteString("  " + line + "\n")
	}

	// Tech stack
	sb.WriteString("\n")
	sb.WriteString(styles.Divider(contentWidth))
	sb.WriteString("\n\n")
	sb.WriteString("  " + styles.AccentStyle().Bold(true).Render("Tech Stack") + "\n\n")
	if m.TechStack.Framework != "" {
		sb.WriteString(fmt.Sprintf("  Framework:  %s\n", m.TechStack.Framework))
	}
	if m.TechStack.Language != "" {
		sb.WriteString(fmt.Sprintf("  Language:   %s\n", m.TechStack.Language))
	}
	if m.TechStack.Database != "" {
		sb.WriteString(fmt.Sprintf("  Database:   %s\n", m.TechStack.Database))
	}
	if m.TechStack.Auth != "" {
		sb.WriteString(fmt.Sprintf("  Auth:       %s\n", m.TechStack.Auth))
	}
	if m.TechStack.Deployment != "" {
		sb.WriteString(fmt.Sprintf("  Deployment: %s\n", m.TechStack.Deployment))
	}
	if len(m.TechStack.Services) > 0 {
		sb.WriteString(fmt.Sprintf("  Services:   %s\n", strings.Join(m.TechStack.Services, ", ")))
	}

	// Industry
	if m.Industry.Primary != "" {
		sb.WriteString("\n")
		sb.WriteString(styles.Divider(contentWidth))
		sb.WriteString("\n\n")
		sb.WriteString("  " + styles.AccentStyle().Bold(true).Render("Industry") + "\n\n")
		sb.WriteString(fmt.Sprintf("  Primary:    %s\n", m.Industry.Primary))
		if len(m.Industry.Secondary) > 0 {
			sb.WriteString(fmt.Sprintf("  Secondary:  %s\n", strings.Join(m.Industry.Secondary, ", ")))
		}
	}

	// Current growth features
	if len(m.CurrentGrowthFeatures) > 0 {
		sb.WriteString("\n")
		sb.WriteString(styles.Divider(contentWidth))
		sb.WriteString("\n\n")
		sb.WriteString("  " + styles.AccentStyle().Bold(true).Render(
			fmt.Sprintf("Current Growth Features (%d)", len(m.CurrentGrowthFeatures)),
		) + "\n")

		for i, f := range m.CurrentGrowthFeatures {
			sb.WriteString("\n")
			sb.WriteString(fmt.Sprintf("  %d. %s", i+1, f.FeatureName))
			if f.ConfidenceScore > 0 {
				sb.WriteString(fmt.Sprintf("  (%.0f%%)", f.ConfidenceScore*100))
			}
			sb.WriteString("\n")
			if f.DetectedIntent != "" {
				for _, line := range wrapText(f.DetectedIntent, w5) {
					sb.WriteString("     " + line + "\n")
				}
			}
		}
	}

	// Growth opportunities
	if len(m.GrowthOpportunities) > 0 {
		sb.WriteString("\n")
		sb.WriteString(styles.Divider(contentWidth))
		sb.WriteString("\n\n")
		sb.WriteString("  " + styles.AccentStyle().Bold(true).Render(
			fmt.Sprintf("Growth Opportunities (%d)", len(m.GrowthOpportunities)),
		) + "\n")

		for i, o := range m.GrowthOpportunities {
			sb.WriteString("\n")
			priority := strings.ToUpper(o.Priority)
			sb.WriteString(fmt.Sprintf("  %d. %s  [%s]\n", i+1, o.FeatureName, priority))
			if o.Description != "" {
				for _, line := range wrapText(o.Description, w5) {
					sb.WriteString("     " + line + "\n")
				}
			}
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Divider(contentWidth))
	return sb.String()
}

// formatTemplate renders growth-template.json as a readable lifecycle summary.
func formatTemplate(raw string, contentWidth int) string {
	var t struct {
		Title       string `json:"title"`
		Description string `json:"description"`
		Lifecycles  []struct {
			Name        string `json:"name"`
			Description string `json:"description"`
			Milestones  []struct {
				Title       string `json:"title"`
				Description string `json:"description"`
			} `json:"milestones"`
			Metrics []struct {
				Name             string `json:"name"`
				HowToMeasure     string `json:"howToMeasure"`
				HealthyBenchmark string `json:"healthyBenchmark"`
			} `json:"metrics"`
		} `json:"lifecycles"`
	}

	if err := json.Unmarshal([]byte(raw), &t); err != nil {
		return ""
	}

	if contentWidth < 40 {
		contentWidth = 60
	}
	w2 := contentWidth - 2
	w4 := contentWidth - 4
	w5 := contentWidth - 5

	var sb strings.Builder

	// Header
	title := t.Title
	if title == "" {
		title = "Growth Template"
	}
	sb.WriteString("  " + styles.AccentStyle().Bold(true).Render(title) + "\n\n")
	if t.Description != "" {
		for _, line := range wrapText(t.Description, w2) {
			sb.WriteString("  " + line + "\n")
		}
	}

	// Lifecycles
	for _, lc := range t.Lifecycles {
		sb.WriteString("\n")
		sb.WriteString(styles.Divider(contentWidth))
		sb.WriteString("\n\n")

		header := lc.Name
		if lc.Description != "" {
			header += " — " + lc.Description
		}
		sb.WriteString("  " + styles.AccentStyle().Bold(true).Render(header) + "\n")

		// Milestones
		if len(lc.Milestones) > 0 {
			sb.WriteString("\n  Milestones:\n")
			for i, ms := range lc.Milestones {
				sb.WriteString(fmt.Sprintf("\n  %d. %s\n", i+1, ms.Title))
				if ms.Description != "" {
					for _, line := range wrapText(ms.Description, w5) {
						sb.WriteString("     " + line + "\n")
					}
				}
			}
		}

		// Metrics
		if len(lc.Metrics) > 0 {
			sb.WriteString("\n  Metrics:\n")
			for _, mt := range lc.Metrics {
				sb.WriteString(fmt.Sprintf("\n  • %s", mt.Name))
				if mt.HealthyBenchmark != "" {
					sb.WriteString(fmt.Sprintf("  [%s]", mt.HealthyBenchmark))
				}
				sb.WriteString("\n")
				if mt.HowToMeasure != "" {
					for _, line := range wrapText(mt.HowToMeasure, w4) {
						sb.WriteString("    " + line + "\n")
					}
				}
			}
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Divider(contentWidth))
	return sb.String()
}

// wrapText breaks text into lines of at most maxWidth characters,
// splitting on word boundaries.
func wrapText(text string, maxWidth int) []string {
	words := strings.Fields(text)
	if len(words) == 0 {
		return nil
	}
	var lines []string
	current := words[0]
	for _, w := range words[1:] {
		if len(current)+1+len(w) > maxWidth {
			lines = append(lines, current)
			current = w
		} else {
			current += " " + w
		}
	}
	lines = append(lines, current)
	return lines
}

// SetSize updates dimensions.
func (v *FileDetailView) SetSize(width, height int) {
	v.width = width
	v.height = height

	sectionWidth := v.sectionWidth()

	// Content width inside the bordered box (subtract border + padding: 2 border + 4 padding = 6)
	vpWidth := sectionWidth - 6
	if vpWidth < 30 {
		vpWidth = 30
	}

	// Re-format content for files that need special rendering
	v.formatted = false
	if v.rawContent != "" {
		if formatted := formatForDisplay(v.fileDef.ID, v.rawContent, vpWidth); formatted != "" {
			v.content = formatted
			v.formatted = true
		}
	}

	// back indicator (1) + blank (1) + info box (~8) + blank (1) + content box chrome (border+padding ~4) + footer (3) + outer padding (2)
	vpHeight := height - 20
	if vpHeight < 5 {
		vpHeight = 5
	}
	if vpHeight > 30 {
		vpHeight = 30
	}

	v.viewport.height = vpHeight

	if v.formatted {
		v.viewport.setContent(v.content, vpWidth)
	} else {
		wrapped := lipgloss.NewStyle().Width(vpWidth).Render(v.content)
		v.viewport.setContent(wrapped, vpWidth)
	}
}

// HandleUp scrolls content up.
func (v *FileDetailView) HandleUp() {
	v.viewport.scrollUp(3)
}

// HandleDown scrolls content down.
func (v *FileDetailView) HandleDown() {
	v.viewport.scrollDown(3)
}

func (v *FileDetailView) sectionWidth() int {
	w := v.width - 20
	if w < 60 {
		w = 60
	}
	if w > 80 {
		w = 80
	}
	return w
}

// Render the file detail view.
func (v *FileDetailView) Render() string {
	sectionWidth := v.sectionWidth()

	// Back indicator (top-left)
	backIndicator := styles.AccentStyle().Render("← " + constants.DashboardBackLabel)

	// File info box: title + description + last modified
	fileTitle := styles.AccentStyle().Render(v.fileDef.DisplayName)
	fileDesc := styles.Body.Render(v.fileDef.Description)

	var infoLines []string
	infoLines = append(infoLines, fileTitle, "", fileDesc)
	if v.modTime != "" {
		infoLines = append(infoLines, "", styles.Muted.Render(v.modTime))
	}
	infoBox := styles.Box.Width(sectionWidth).Render(
		lipgloss.JoinVertical(lipgloss.Left, infoLines...),
	)

	// Content box uses the same width as the info box
	contentBox := styles.Box.Width(sectionWidth).Render(v.viewport.view())

	// Footer
	footer := lipgloss.NewStyle().
		Width(v.width).
		Align(lipgloss.Center).
		Render(components.FooterHelp(v.GetHelpItems(), v.width))

	content := lipgloss.JoinVertical(lipgloss.Left,
		backIndicator,
		"",
		infoBox,
		"",
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

// GetHelpItems returns help items for the file detail view.
func (v *FileDetailView) GetHelpItems() []components.HelpItem {
	return []components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescScroll},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
		{Key: constants.HelpKeyCtrlC, Desc: constants.HelpDescQuit},
	}
}
