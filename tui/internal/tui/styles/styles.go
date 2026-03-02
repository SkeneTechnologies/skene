package styles

import (
	"os"

	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"
)

// IsDarkBackground indicates whether the terminal has a dark background.
// Set by Init(); defaults to true if Init() is not called.
var IsDarkBackground = true

// Init detects the terminal background color and applies the appropriate
// color theme. Call this once at startup, before creating any views.
func Init() {
	output := termenv.NewOutput(os.Stdout)
	IsDarkBackground = output.HasDarkBackground()

	if !IsDarkBackground {
		applyLightColors()
	}
	rebuildStyles()
}

// ═══════════════════════════════════════════════════════════════════
// COLOR PALETTE
// ═══════════════════════════════════════════════════════════════════

// Color palette - warm, retro terminal aesthetic (dark-background defaults)
var (
	// Primary colors
	Cream     = lipgloss.Color("#EDC29C")
	Sand      = lipgloss.Color("#C9A97A")
	Charcoal  = lipgloss.Color("#1A1A1A")
	DarkGray  = lipgloss.Color("#2D2D2D")
	MidGray   = lipgloss.Color("#4A4A4A")
	LightGray = lipgloss.Color("#6A6A6A")
	White     = lipgloss.Color("#FFFFFF")

	// Accent colors
	Amber   = lipgloss.Color("#EDC29C")
	Rust    = lipgloss.Color("#D4A574")
	Coral   = lipgloss.Color("#F05D5E")
	Success = lipgloss.Color("#7CB374")
	Warning = lipgloss.Color("#E6B450")

	// Game colors
	GameCyan    = lipgloss.Color("#4CC9F0")
	GameMagenta = lipgloss.Color("#F72585")
	GameYellow  = lipgloss.Color("#FFD93D")
)

// applyLightColors overrides the color palette with values that provide
// strong contrast on light terminal backgrounds while keeping the warm,
// retro aesthetic. Every color here must read clearly on a white (#FFF)
// or near-white background.
func applyLightColors() {
	// Primary colors — dark, high-contrast tones
	Cream = lipgloss.Color("#5C3310")     // Rich dark brown (headings, titles)
	Sand = lipgloss.Color("#5A432E")      // Dark warm brown (subtitles)
	Charcoal = lipgloss.Color("#F5F0EB")  // Off-white (button fill bg)
	DarkGray = lipgloss.Color("#EDE6DD")  // Warm light gray (box bg)
	MidGray = lipgloss.Color("#6B6058")   // Medium-dark warm gray (muted text)
	LightGray = lipgloss.Color("#554A42") // Dark gray (secondary text)
	White = lipgloss.Color("#1A1410")     // Near-black warm brown (body text)

	// Accent colors — bold, saturated tones for visibility
	Amber = lipgloss.Color("#8B4F00")   // Deep amber (primary accent)
	Rust = lipgloss.Color("#7A4420")    // Dark rust
	Coral = lipgloss.Color("#B22020")   // Strong red
	Success = lipgloss.Color("#1B6B14") // Deep green
	Warning = lipgloss.Color("#8A6500") // Dark gold

	// Game colors — vivid and saturated for light backgrounds
	GameCyan = lipgloss.Color("#075E7B")
	GameMagenta = lipgloss.Color("#A01050")
	GameYellow = lipgloss.Color("#7A5D00")
}

// ═══════════════════════════════════════════════════════════════════
// STYLES (rebuilt from current color values)
// ═══════════════════════════════════════════════════════════════════

// Text styles
var (
	Title       lipgloss.Style
	Subtitle    lipgloss.Style
	Body        lipgloss.Style
	Muted       lipgloss.Style
	Accent      lipgloss.Style
	Error       lipgloss.Style
	SuccessText lipgloss.Style
	Label       lipgloss.Style
	Value       lipgloss.Style
)

// Layout styles
var (
	Box           lipgloss.Style
	BoxActive     lipgloss.Style
	RoundedBox    lipgloss.Style
	SectionHeader lipgloss.Style
)

// Button styles
var (
	Button       lipgloss.Style
	ButtonActive lipgloss.Style
	ButtonMuted  lipgloss.Style
)

// Tab styles
var (
	TabBorder = lipgloss.Border{
		Top:         "─",
		Bottom:      " ",
		Left:        "│",
		Right:       "│",
		TopLeft:     "╭",
		TopRight:    "╮",
		BottomLeft:  "┘",
		BottomRight: "└",
	}

	TabInactive lipgloss.Style
	TabActive   lipgloss.Style
)

// List styles
var (
	ListItem                lipgloss.Style
	ListItemSelected        lipgloss.Style
	ListItemDimmed          lipgloss.Style
	ListDescription         lipgloss.Style
	ListDescriptionSelected lipgloss.Style
)

// Progress bar colors
var (
	ProgressFilled lipgloss.Color
	ProgressEmpty  lipgloss.Color
)

// Help styles
var (
	HelpKey       lipgloss.Style
	HelpDesc      lipgloss.Style
	HelpSeparator lipgloss.Style
)

// ASCII art style
var (
	ASCII         lipgloss.Style
	ASCIIAnimated lipgloss.Style
)

// Table styles
var (
	TableHeader    lipgloss.Style
	TableRow       lipgloss.Style
	TableSeparator lipgloss.Style
)

// Modal styles
var (
	Modal      lipgloss.Style
	ModalTitle lipgloss.Style
)

// Footer help bar
var FooterHelp lipgloss.Style

// Spinner style
var Spinner lipgloss.Style

// rebuildStyles constructs all lipgloss styles from the current color
// variables. Called by Init() after colors have been set.
func rebuildStyles() {
	// Text styles
	Title = lipgloss.NewStyle().Foreground(Cream).Bold(true)
	Subtitle = lipgloss.NewStyle().Foreground(Sand)
	Body = lipgloss.NewStyle().Foreground(White)
	Muted = lipgloss.NewStyle().Foreground(MidGray)
	Accent = lipgloss.NewStyle().Foreground(Amber)
	Error = lipgloss.NewStyle().Foreground(Coral)
	SuccessText = lipgloss.NewStyle().Foreground(Success)
	Label = lipgloss.NewStyle().Foreground(Cream).Bold(false)
	Value = lipgloss.NewStyle().Foreground(White)

	// Layout styles
	Box = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MidGray).
		Padding(1, 2)
	BoxActive = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(Cream).
		Padding(1, 2)
	RoundedBox = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(MidGray).
		Padding(1, 2)
	SectionHeader = lipgloss.NewStyle().
		Foreground(Cream).
		Bold(false).
		MarginBottom(1)

	// Button styles
	Button = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MidGray).
		Foreground(White).
		Padding(0, 3)
	ButtonActive = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(Charcoal).
		BorderBackground(Cream).
		Foreground(Charcoal).
		Background(Cream).
		Padding(0, 3)
	ButtonMuted = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MidGray).
		Foreground(MidGray).
		Padding(0, 3)

	// Tab styles
	TabInactive = lipgloss.NewStyle().
		Border(TabBorder, true).
		BorderForeground(MidGray).
		Foreground(MidGray).
		Padding(0, 2)
	TabActive = lipgloss.NewStyle().
		Border(TabBorder, true).
		BorderForeground(Cream).
		Foreground(White).
		Padding(0, 2)

	// List styles
	ListItem = lipgloss.NewStyle().
		Foreground(White).
		PaddingLeft(2)
	ListItemSelected = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder(), false, false, false, true).
		BorderForeground(Amber).
		Foreground(Amber).
		PaddingLeft(1)
	ListItemDimmed = lipgloss.NewStyle().
		Foreground(MidGray).
		PaddingLeft(2)
	ListDescription = lipgloss.NewStyle().
		Foreground(MidGray).
		PaddingLeft(2)
	ListDescriptionSelected = lipgloss.NewStyle().
		Foreground(Sand).
		PaddingLeft(2)

	// Progress bar colors
	ProgressFilled = Amber
	ProgressEmpty = MidGray

	// Help styles
	HelpKey = lipgloss.NewStyle().Foreground(Cream).Bold(true)
	HelpDesc = lipgloss.NewStyle().Foreground(MidGray)
	HelpSeparator = lipgloss.NewStyle().Foreground(MidGray).SetString(" • ")

	// ASCII art style
	ASCII = lipgloss.NewStyle().Foreground(Cream)
	ASCIIAnimated = lipgloss.NewStyle().Foreground(Amber)

	// Table styles
	TableHeader = lipgloss.NewStyle().Foreground(MidGray).Bold(false)
	TableRow = lipgloss.NewStyle().Foreground(White)
	TableSeparator = lipgloss.NewStyle().Foreground(MidGray)

	// Modal styles
	Modal = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MidGray).
		Padding(1, 2).
		Align(lipgloss.Center)
	ModalTitle = lipgloss.NewStyle().
		Foreground(White).
		Bold(false).
		MarginBottom(1)

	// Footer help bar
	FooterHelp = lipgloss.NewStyle().Foreground(MidGray).MarginTop(1)

	// Spinner style
	Spinner = lipgloss.NewStyle().Foreground(Amber)
}

// init sets up the default dark-theme styles at package load time.
// This ensures styles are usable even if Init() is not called.
func init() {
	rebuildStyles()
}

// Center helper
func Center(width int) lipgloss.Style {
	return lipgloss.NewStyle().
		Width(width).
		Align(lipgloss.Center)
}

// PlaceCenter centers content in given dimensions
func PlaceCenter(width, height int, content string) string {
	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, content)
}

// Divider creates a horizontal line
func Divider(width int) string {
	return lipgloss.NewStyle().
		Foreground(MidGray).
		Render(repeatString("─", width))
}

func repeatString(s string, n int) string {
	result := ""
	for i := 0; i < n; i++ {
		result += s
	}
	return result
}

// PageTitle creates a centered page title
func PageTitle(title string, width int) string {
	return lipgloss.NewStyle().
		Foreground(Cream).
		Width(width).
		Align(lipgloss.Center).
		Render(title)
}
