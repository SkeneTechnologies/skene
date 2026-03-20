package styles

import (
	"os"

	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"
)

// IsDarkBackground indicates whether the terminal has a dark background.
// Set by Init(); defaults to true if Init() is not called.
var IsDarkBackground = true

// HasCustomTheme indicates whether the terminal appears to have a
// non-standard foreground color (e.g. green, amber). When true the
// lipgloss renderer is forced to ANSI (16-color) so that
// CompleteAdaptiveColor picks the ANSI tier, which uses the user's
// theme palette instead of brand hex values.
var HasCustomTheme = false

// Init detects the terminal background color and whether the user has
// a custom ANSI theme. Call this once at startup, before creating any
// views.
func Init() {
	output := termenv.NewOutput(os.Stdout)
	IsDarkBackground = output.HasDarkBackground()

	if detectCustomTheme(output) {
		HasCustomTheme = true
		lipgloss.SetColorProfile(termenv.ANSI)
	}

	rebuildStyles()
}

// detectCustomTheme queries the terminal's foreground color and returns
// true when it appears to be a non-standard (saturated) color. Standard
// terminals use white, gray, or black foregrounds which all have very
// low saturation. A green, amber, or other tinted foreground indicates
// a custom theme.
func detectCustomTheme(output *termenv.Output) bool {
	fg := output.ForegroundColor()
	if fg == nil {
		return false
	}

	c := termenv.ConvertToRGB(fg)
	_, s, _ := c.Hsl()

	const saturationThreshold = 0.20
	return s > saturationThreshold
}

// ═══════════════════════════════════════════════════════════════════
// COLOR PALETTE
//
// Two tiers:
//   TrueColor  – Skene brand hex values (used on standard modern terminals)
//   ANSI       – 16-color indices that adapt to the user's theme
//
// When a custom theme is detected, the renderer is forced to ANSI so
// CompleteAdaptiveColor always picks the ANSI tier.
// ═══════════════════════════════════════════════════════════════════

var (
	TextColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#FFFFFF", ANSI: "15"},
		Light: lipgloss.CompleteColor{TrueColor: "#1A1410", ANSI: "0"},
	}

	// BoldTextColor is the raw accent color value. Use AccentStyle() for
	// foreground text — it handles custom ANSI themes correctly. Use this
	// directly only for borders, backgrounds, or other non-foreground uses.
	BoldTextColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#FEC089", ANSI: "15"},
		Light: lipgloss.CompleteColor{TrueColor: "#CE6100", ANSI: "0"},
	}

	// InvertedTextColor is dark-on-light / light-on-dark — for text on
	// accent-colored backgrounds.
	InvertedTextColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#1A1410", ANSI: "0"},
		Light: lipgloss.CompleteColor{TrueColor: "#FFFFFF", ANSI: "15"},
	}

	MutedColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#4A4A4A", ANSI: "8"},
		Light: lipgloss.CompleteColor{TrueColor: "#E1D8D1", ANSI: "15"},
	}

	ErrorColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#F25246", ANSI: "9"},
		Light: lipgloss.CompleteColor{TrueColor: "#F33E31", ANSI: "1"},
	}

	SuccessColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#D7F4AB", ANSI: "10"},
		Light: lipgloss.CompleteColor{TrueColor: "#578908", ANSI: "2"},
	}

	WarningColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#E6B450", ANSI: "11"},
		Light: lipgloss.CompleteColor{TrueColor: "#8A6500", ANSI: "3"},
	}

	// SpinnerColor — activity / loading indicator (distinct from brand accent).
	SpinnerColor lipgloss.TerminalColor = lipgloss.CompleteAdaptiveColor{
		Dark:  lipgloss.CompleteColor{TrueColor: "#7EC8E3", ANSI: "14"},
		Light: lipgloss.CompleteColor{TrueColor: "#0D6E8D", ANSI: "6"},
	}
)


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
	ProgressFilled lipgloss.TerminalColor
	ProgressEmpty  lipgloss.TerminalColor
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

// UpdateNotice style — framed box for update + hint
var UpdateNotice lipgloss.Style

// UpdateNoticeText style — main update message
var UpdateNoticeText lipgloss.Style

// AccentStyle returns a style with the accent color applied. On standard
// terminals this is the brand foreground; on custom ANSI themes it uses
// Bold so the terminal's own theme color shows through. Use this (or the
// pre-built Accent variable) for all accent-colored text. Chain
// .Bold(true) yourself if you also want bold weight.
func AccentStyle() lipgloss.Style {
	if HasCustomTheme {
		return lipgloss.NewStyle().Bold(true)
	}
	return lipgloss.NewStyle().Foreground(BoldTextColor)
}

// rebuildStyles constructs all lipgloss styles from the current color
// variables. Called by Init() after colors have been set.
func rebuildStyles() {
	accent := AccentStyle()

	// Text styles
	Title = accent.Bold(true)
	Subtitle = accent
	Body = lipgloss.NewStyle().Foreground(TextColor)
	Muted = lipgloss.NewStyle().Foreground(MutedColor)
	Accent = accent
	Error = lipgloss.NewStyle().Foreground(ErrorColor)
	SuccessText = lipgloss.NewStyle().Foreground(SuccessColor)
	Label = accent
	Value = lipgloss.NewStyle().Foreground(TextColor)

	// Layout styles
	Box = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MutedColor).
		Padding(1, 2)
	BoxActive = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(BoldTextColor).
		Padding(1, 2)
	RoundedBox = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(MutedColor).
		Padding(1, 2)
	SectionHeader = accent.MarginBottom(1)

	// Button styles
	Button = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MutedColor).
		Foreground(TextColor).
		Padding(0, 3)
	ButtonActive = lipgloss.NewStyle().
		Reverse(true).
		Padding(1, 4)
	ButtonMuted = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MutedColor).
		Foreground(MutedColor).
		Padding(0, 3)

	// Tab styles
	TabInactive = lipgloss.NewStyle().
		Border(TabBorder, true).
		BorderForeground(MutedColor).
		Foreground(MutedColor).
		Padding(0, 2)
	TabActive = lipgloss.NewStyle().
		Border(TabBorder, true).
		BorderForeground(BoldTextColor).
		Foreground(TextColor).
		Padding(0, 2)

	// List styles
	ListItem = lipgloss.NewStyle().
		Foreground(TextColor).
		PaddingLeft(2)
	ListItemSelected = accent.
		Border(lipgloss.NormalBorder(), false, false, false, true).
		BorderForeground(BoldTextColor).
		PaddingLeft(1)
	ListItemDimmed = lipgloss.NewStyle().
		Foreground(MutedColor).
		PaddingLeft(2)
	ListDescription = lipgloss.NewStyle().
		Foreground(MutedColor).
		PaddingLeft(2)
	ListDescriptionSelected = lipgloss.NewStyle().
		Foreground(MutedColor).
		PaddingLeft(2)

	// Progress bar colors
	ProgressFilled = BoldTextColor
	ProgressEmpty = MutedColor

	// Help styles
	HelpKey = accent.Bold(true)
	HelpDesc = lipgloss.NewStyle().Foreground(MutedColor)
	HelpSeparator = lipgloss.NewStyle().Foreground(MutedColor).SetString(" • ")

	// ASCII art style
	ASCII = accent
	ASCIIAnimated = accent

	// Table styles
	TableHeader = lipgloss.NewStyle().Foreground(MutedColor).Bold(false)
	TableRow = lipgloss.NewStyle().Foreground(TextColor)
	TableSeparator = lipgloss.NewStyle().Foreground(MutedColor)

	// Modal styles
	Modal = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(MutedColor).
		Padding(1, 2).
		Align(lipgloss.Center)
	ModalTitle = lipgloss.NewStyle().
		Foreground(TextColor).
		Bold(false).
		MarginBottom(1)

	// Footer help bar
	FooterHelp = lipgloss.NewStyle().Foreground(MutedColor).MarginTop(1)

	// Spinner style
	Spinner = lipgloss.NewStyle().Foreground(SpinnerColor)

	// UpdateNotice — bordered box for update + hint (no bg; centered text)
	UpdateNotice = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(MutedColor).
		Padding(1, 1).
		Align(lipgloss.Center).
		MarginTop(1)
	UpdateNoticeText = lipgloss.NewStyle().Foreground(TextColor)
}

// init sets up the default styles at package load time.
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
		Foreground(MutedColor).
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
	return AccentStyle().Bold(true).
		Width(width).
		Align(lipgloss.Center).
		Render(title)
}
