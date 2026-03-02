package components

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"skene/internal/tui/styles"

	"github.com/charmbracelet/lipgloss"
)

// DirEntry represents a single entry in the directory browser
type DirEntry struct {
	Name  string
	IsDir bool
}

// DirBrowser is an interactive directory browser component
type DirBrowser struct {
	currentPath string
	entries     []DirEntry
	cursor      int
	height      int // visible rows
	scrollOff   int // scroll offset
	err         error
	showHidden  bool
}

// NewDirBrowser creates a new directory browser starting at the given path
func NewDirBrowser(startPath string) *DirBrowser {
	b := &DirBrowser{
		height:     12,
		showHidden: false,
	}
	b.Navigate(startPath)
	return b
}

// SetHeight sets the number of visible rows
func (b *DirBrowser) SetHeight(h int) {
	if h < 4 {
		h = 4
	}
	b.height = h
}

// Navigate changes the current directory and refreshes the listing
func (b *DirBrowser) Navigate(path string) {
	// Expand ~
	if len(path) > 0 && path[0] == '~' {
		home, _ := os.UserHomeDir()
		path = filepath.Join(home, path[1:])
	}

	abs, err := filepath.Abs(path)
	if err != nil {
		b.err = err
		return
	}

	info, err := os.Stat(abs)
	if err != nil {
		b.err = err
		return
	}
	if !info.IsDir() {
		abs = filepath.Dir(abs)
	}

	b.currentPath = abs
	b.cursor = 0
	b.scrollOff = 0
	b.err = nil
	b.loadEntries()
}

// loadEntries reads the current directory
func (b *DirBrowser) loadEntries() {
	dirEntries, err := os.ReadDir(b.currentPath)
	if err != nil {
		b.err = err
		return
	}

	b.entries = nil

	// Add parent directory entry if not at root
	if b.currentPath != "/" {
		b.entries = append(b.entries, DirEntry{Name: "..", IsDir: true})
	}

	// Collect directories first, then files
	var dirs []DirEntry
	var files []DirEntry

	for _, e := range dirEntries {
		name := e.Name()

		// Skip hidden files/dirs unless toggled
		if !b.showHidden && strings.HasPrefix(name, ".") {
			continue
		}

		if e.IsDir() {
			dirs = append(dirs, DirEntry{Name: name, IsDir: true})
		} else {
			files = append(files, DirEntry{Name: name, IsDir: false})
		}
	}

	sort.Slice(dirs, func(i, j int) bool {
		return strings.ToLower(dirs[i].Name) < strings.ToLower(dirs[j].Name)
	})
	sort.Slice(files, func(i, j int) bool {
		return strings.ToLower(files[i].Name) < strings.ToLower(files[j].Name)
	})

	b.entries = append(b.entries, dirs...)
	b.entries = append(b.entries, files...)
}

// CursorUp moves the cursor up
func (b *DirBrowser) CursorUp() {
	if b.cursor > 0 {
		b.cursor--
		if b.cursor < b.scrollOff {
			b.scrollOff = b.cursor
		}
	}
}

// CursorDown moves the cursor down
func (b *DirBrowser) CursorDown() {
	if b.cursor < len(b.entries)-1 {
		b.cursor++
		if b.cursor >= b.scrollOff+b.height {
			b.scrollOff = b.cursor - b.height + 1
		}
	}
}

// Enter navigates into the selected directory, returns true if navigated
func (b *DirBrowser) Enter() bool {
	if b.cursor < 0 || b.cursor >= len(b.entries) {
		return false
	}

	entry := b.entries[b.cursor]
	if !entry.IsDir {
		return false
	}

	if entry.Name == ".." {
		b.Navigate(filepath.Dir(b.currentPath))
	} else {
		b.Navigate(filepath.Join(b.currentPath, entry.Name))
	}
	return true
}

// GoUp navigates to the parent directory
func (b *DirBrowser) GoUp() {
	parent := filepath.Dir(b.currentPath)
	if parent != b.currentPath {
		b.Navigate(parent)
	}
}

// ToggleHidden toggles hidden file/dir visibility
func (b *DirBrowser) ToggleHidden() {
	b.showHidden = !b.showHidden
	b.loadEntries()
	if b.cursor >= len(b.entries) {
		b.cursor = len(b.entries) - 1
	}
}

// CurrentPath returns the current directory path
func (b *DirBrowser) CurrentPath() string {
	return b.currentPath
}

// SelectedPath returns the full path of the currently highlighted entry
func (b *DirBrowser) SelectedPath() string {
	if b.cursor < 0 || b.cursor >= len(b.entries) {
		return b.currentPath
	}
	entry := b.entries[b.cursor]
	if entry.Name == ".." {
		return filepath.Dir(b.currentPath)
	}
	return filepath.Join(b.currentPath, entry.Name)
}

// SelectedIsDir returns true if the highlighted entry is a directory
func (b *DirBrowser) SelectedIsDir() bool {
	if b.cursor < 0 || b.cursor >= len(b.entries) {
		return false
	}
	return b.entries[b.cursor].IsDir
}

// Render renders the directory browser
func (b *DirBrowser) Render(width int) string {
	if width < 30 {
		width = 30
	}

	// Path header
	pathStyle := lipgloss.NewStyle().
		Foreground(styles.Cream).
		Bold(true)

	displayPath := b.currentPath
	maxPathLen := width - 6
	if len(displayPath) > maxPathLen {
		displayPath = "..." + displayPath[len(displayPath)-maxPathLen+3:]
	}
	pathLine := pathStyle.Render(displayPath)

	// Error state
	if b.err != nil {
		errLine := styles.Error.Render("Error: " + b.err.Error())
		content := lipgloss.JoinVertical(lipgloss.Left, pathLine, "", errLine)
		return styles.Box.Width(width).Render(content)
	}

	// Build visible entries
	var lines []string

	end := b.scrollOff + b.height
	if end > len(b.entries) {
		end = len(b.entries)
	}

	for i := b.scrollOff; i < end; i++ {
		entry := b.entries[i]

		var icon string
		if entry.IsDir {
			icon = "/"
		} else {
			icon = " "
		}

		name := entry.Name + icon

		// Truncate long names
		maxNameLen := width - 10
		if len(name) > maxNameLen {
			name = name[:maxNameLen-1] + "~"
		}

		if i == b.cursor {
			line := styles.ListItemSelected.Render(name)
			lines = append(lines, line)
		} else if entry.IsDir {
			line := styles.ListItem.Render(name)
			lines = append(lines, line)
		} else {
			line := styles.ListItemDimmed.Render(name)
			lines = append(lines, line)
		}
	}

	// Scroll indicators
	var scrollInfo string
	if len(b.entries) > b.height {
		scrollInfo = styles.Muted.Render(
			"  " + strings.Repeat(".", 3) + " " +
				lipgloss.NewStyle().Render(
					formatScrollPos(b.scrollOff+1, end, len(b.entries)),
				),
		)
	}

	listing := lipgloss.JoinVertical(lipgloss.Left, lines...)

	// Help line
	helpLine := styles.Muted.Render("arrows: navigate  enter: open  .: hidden  esc: cancel")

	parts := []string{pathLine, "", listing}
	if scrollInfo != "" {
		parts = append(parts, scrollInfo)
	}
	parts = append(parts, "", helpLine)

	content := lipgloss.JoinVertical(lipgloss.Left, parts...)

	return styles.Box.Width(width).Render(content)
}

func formatScrollPos(start, end, total int) string {
	return lipgloss.NewStyle().Foreground(styles.MidGray).Render(
		"[" + itoa(start) + "-" + itoa(end) + " of " + itoa(total) + "]",
	)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	return s
}
