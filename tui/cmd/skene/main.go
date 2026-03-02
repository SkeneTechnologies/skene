package main

import (
	"fmt"
	"os"

	"skene/internal/tui"
	"skene/internal/tui/styles"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	// Detect terminal background (light vs dark) and apply the
	// appropriate color theme. Must run before bubbletea takes over.
	styles.Init()

	// Create the application
	app := tui.NewApp()

	// Create the program with alt screen
	p := tea.NewProgram(
		app,
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(),
	)

	// Set program reference for background task communication
	app.SetProgram(p)

	// Run the program
	if _, err := p.Run(); err != nil {
		fmt.Printf("Error running program: %v\n", err)
		os.Exit(1)
	}
}
