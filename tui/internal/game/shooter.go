package game

import (
	"fmt"
	"math/rand"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Entity types
type EntityType int

const (
	EntityPlayer EntityType = iota
	EntityEnemy
	EntityBullet
	EntityPowerUp
)

// Entity represents a game entity
type Entity struct {
	Type   EntityType
	X, Y   int
	Width  int
	Height int
	Alive  bool
	Sprite string
}

// Game represents the space shooter game
type Game struct {
	width        int
	height       int
	player       *Entity
	enemies      []*Entity
	bullets      []*Entity
	powerUps     []*Entity
	score        int
	lives        int
	level        int
	gameOver     bool
	paused       bool
	lastSpawn    time.Time
	spawnRate    time.Duration
	tickCount    int
	enemySpeed   int // enemies move every N ticks
	
	// Analysis progress indicator
	showProgress    bool
	progressPhase   string
	progressDone    bool
	progressFailed  bool
	progressSpinner *components.Spinner
}

// NewGame creates a new game instance
func NewGame(width, height int) *Game {
	g := &Game{
		width:           width,
		height:          height,
		enemies:         make([]*Entity, 0),
		bullets:         make([]*Entity, 0),
		powerUps:        make([]*Entity, 0),
		score:           0,
		lives:           3,
		level:           1,
		gameOver:        false,
		paused:          false,
		lastSpawn:       time.Now(),
		spawnRate:       1200 * time.Millisecond,
		enemySpeed:      3, // move every 3 ticks (150ms)
		showProgress:    false,
		progressSpinner: components.NewSpinner(),
	}

	// Create player
	g.player = &Entity{
		Type:   EntityPlayer,
		X:      width / 2,
		Y:      height - 3,
		Width:  3,
		Height: 2,
		Alive:  true,
		Sprite: " ▲ \n/█\\",
	}

	return g
}

// SetSize updates game dimensions
func (g *Game) SetSize(width, height int) {
	g.width = width
	g.height = height
	
	// Reposition player
	if g.player != nil {
		g.player.Y = height - 3
		if g.player.X > width-3 {
			g.player.X = width - 3
		}
	}
}

// Update game state
func (g *Game) Update() {
	if g.gameOver || g.paused {
		return
	}

	g.tickCount++

	// Move bullets (every tick -- fast)
	for _, b := range g.bullets {
		if b.Alive {
			b.Y--
			if b.Y < 0 {
				b.Alive = false
			}
		}
	}

	// Move enemies (slower -- every N ticks)
	if g.tickCount%g.enemySpeed == 0 {
		for _, e := range g.enemies {
			if e.Alive {
				e.Y++
				if e.Y > g.height {
					e.Alive = false
				}
			}
		}
	}

	// Check collisions
	g.checkCollisions()

	// Spawn new enemies
	if time.Since(g.lastSpawn) > g.spawnRate {
		g.spawnEnemy()
		g.lastSpawn = time.Now()
	}

	// Clean up dead entities
	g.cleanup()

	// Check game over
	if g.lives <= 0 {
		g.gameOver = true
	}
}

// MoveLeft moves player left
func (g *Game) MoveLeft() {
	if g.player.X > 1 {
		g.player.X -= 2
	}
}

// MoveRight moves player right
func (g *Game) MoveRight() {
	if g.player.X < g.width-4 {
		g.player.X += 2
	}
}

// Shoot fires a bullet
func (g *Game) Shoot() {
	bullet := &Entity{
		Type:   EntityBullet,
		X:      g.player.X + 1,
		Y:      g.player.Y - 1,
		Width:  1,
		Height: 1,
		Alive:  true,
		Sprite: "│",
	}
	g.bullets = append(g.bullets, bullet)
}

// spawnEnemy creates a new enemy
func (g *Game) spawnEnemy() {
	enemyTypes := []struct {
		sprite string
		width  int
	}{
		{"<█>", 3},
		{"/▼\\", 3},
		{"[●]", 3},
		{"{◈}", 3},
	}

	et := enemyTypes[rand.Intn(len(enemyTypes))]

	enemy := &Entity{
		Type:   EntityEnemy,
		X:      rand.Intn(g.width-6) + 2,
		Y:      0,
		Width:  et.width,
		Height: 1,
		Alive:  true,
		Sprite: et.sprite,
	}
	g.enemies = append(g.enemies, enemy)
}

// checkCollisions checks for collisions
func (g *Game) checkCollisions() {
	// Bullets vs Enemies
	for _, b := range g.bullets {
		if !b.Alive {
			continue
		}
		for _, e := range g.enemies {
			if !e.Alive {
				continue
			}
			if g.collides(b, e) {
				b.Alive = false
				e.Alive = false
				g.score += 100

				// Level up every 1000 points
				if g.score > 0 && g.score%1000 == 0 {
					g.level++
					if g.spawnRate > 600*time.Millisecond {
						g.spawnRate -= 100 * time.Millisecond
					}
					if g.enemySpeed > 2 {
						g.enemySpeed--
					}
				}
			}
		}
	}

	// Enemies vs Player
	for _, e := range g.enemies {
		if !e.Alive {
			continue
		}
		if g.collides(e, g.player) {
			e.Alive = false
			g.lives--
		}
	}
}

func (g *Game) collides(a, b *Entity) bool {
	return a.X < b.X+b.Width &&
		a.X+a.Width > b.X &&
		a.Y < b.Y+b.Height &&
		a.Y+a.Height > b.Y
}

func (g *Game) cleanup() {
	// Clean bullets
	var aliveBullets []*Entity
	for _, b := range g.bullets {
		if b.Alive {
			aliveBullets = append(aliveBullets, b)
		}
	}
	g.bullets = aliveBullets

	// Clean enemies
	var aliveEnemies []*Entity
	for _, e := range g.enemies {
		if e.Alive {
			aliveEnemies = append(aliveEnemies, e)
		}
	}
	g.enemies = aliveEnemies
}

// Restart resets the game
func (g *Game) Restart() {
	g.enemies = make([]*Entity, 0)
	g.bullets = make([]*Entity, 0)
	g.powerUps = make([]*Entity, 0)
	g.score = 0
	g.lives = 3
	g.level = 1
	g.gameOver = false
	g.paused = false
	g.spawnRate = 1200 * time.Millisecond
	g.enemySpeed = 3
	g.tickCount = 0
	g.player.X = g.width / 2
	g.player.Y = g.height - 3
	g.player.Alive = true
}

// TogglePause toggles pause state
func (g *Game) TogglePause() {
	g.paused = !g.paused
}

// IsGameOver returns if game is over
func (g *Game) IsGameOver() bool {
	return g.gameOver
}

// IsPaused returns if game is paused
func (g *Game) IsPaused() bool {
	return g.paused
}

// GetScore returns current score
func (g *Game) GetScore() int {
	return g.score
}

// SetProgressInfo updates the analysis progress indicator
func (g *Game) SetProgressInfo(phase string, done, failed bool) {
	g.showProgress = true
	g.progressPhase = phase
	g.progressDone = done
	g.progressFailed = failed
}

// ClearProgressInfo hides the progress indicator
func (g *Game) ClearProgressInfo() {
	g.showProgress = false
	g.progressPhase = ""
	g.progressDone = false
	g.progressFailed = false
}

// TickProgressSpinner advances the progress spinner animation
func (g *Game) TickProgressSpinner() {
	if g.progressSpinner != nil {
		g.progressSpinner.Tick()
	}
}

// cellType tracks what entity occupies each cell for coloring
type cellType int

const (
	cellEmpty  cellType = iota
	cellStar
	cellEnemy
	cellBullet
	cellPlayer
)

// Render draws the game
func (g *Game) Render() string {
	// Create game field with type info for coloring
	field := make([][]rune, g.height)
	fieldType := make([][]cellType, g.height)
	for i := range field {
		field[i] = make([]rune, g.width)
		fieldType[i] = make([]cellType, g.width)
		for j := range field[i] {
			field[i][j] = ' '
			fieldType[i][j] = cellEmpty
		}
	}

	// Draw stars (background)
	starPositions := []struct{ x, y int }{
		{5, 3}, {15, 7}, {25, 2}, {35, 8}, {45, 4},
		{10, 12}, {20, 15}, {30, 10}, {40, 13}, {50, 6},
	}
	for _, pos := range starPositions {
		if pos.x < g.width && pos.y < g.height {
			field[pos.y][pos.x] = '·'
			fieldType[pos.y][pos.x] = cellStar
		}
	}

	// Draw enemies
	for _, e := range g.enemies {
		if e.Alive && e.Y >= 0 && e.Y < g.height && e.X >= 0 {
			for i, r := range e.Sprite {
				if e.X+i >= 0 && e.X+i < g.width {
					field[e.Y][e.X+i] = r
					fieldType[e.Y][e.X+i] = cellEnemy
				}
			}
		}
	}

	// Draw bullets
	for _, b := range g.bullets {
		if b.Alive && b.Y >= 0 && b.Y < g.height && b.X >= 0 && b.X < g.width {
			field[b.Y][b.X] = '│'
			fieldType[b.Y][b.X] = cellBullet
		}
	}

	// Draw player
	if g.player.Alive && g.player.Y >= 0 && g.player.Y < g.height {
		if g.player.Y-1 >= 0 && g.player.X+1 < g.width {
			field[g.player.Y-1][g.player.X+1] = '▲'
			fieldType[g.player.Y-1][g.player.X+1] = cellPlayer
		}
		if g.player.X >= 0 && g.player.X < g.width {
			field[g.player.Y][g.player.X] = '/'
			fieldType[g.player.Y][g.player.X] = cellPlayer
		}
		if g.player.X+1 < g.width {
			field[g.player.Y][g.player.X+1] = '█'
			fieldType[g.player.Y][g.player.X+1] = cellPlayer
		}
		if g.player.X+2 < g.width {
			field[g.player.Y][g.player.X+2] = '\\'
			fieldType[g.player.Y][g.player.X+2] = cellPlayer
		}
	}

	// Color styles
	enemyStyle := lipgloss.NewStyle().Foreground(styles.Coral)
	bulletStyle := lipgloss.NewStyle().Foreground(styles.GameYellow)
	playerStyle := lipgloss.NewStyle().Foreground(styles.GameCyan)
	starStyle := lipgloss.NewStyle().Foreground(styles.MidGray)

	// Render per-character with colors
	var lines []string
	for y := 0; y < g.height; y++ {
		var lineBuilder strings.Builder
		for x := 0; x < g.width; x++ {
			ch := string(field[y][x])
			switch fieldType[y][x] {
			case cellEnemy:
				lineBuilder.WriteString(enemyStyle.Render(ch))
			case cellBullet:
				lineBuilder.WriteString(bulletStyle.Render(ch))
			case cellPlayer:
				lineBuilder.WriteString(playerStyle.Render(ch))
			case cellStar:
				lineBuilder.WriteString(starStyle.Render(ch))
			default:
				lineBuilder.WriteString(ch)
			}
		}
		lines = append(lines, lineBuilder.String())
	}

	gameArea := strings.Join(lines, "\n")

	// Header with score
	scoreStr := fmt.Sprintf("%d", g.score)
	livesStr := strings.Repeat("♥", g.lives)
	levelStr := fmt.Sprintf("%d", g.level)

	header := lipgloss.JoinHorizontal(
		lipgloss.Center,
		styles.Accent.Render("SPACE SHOOTER"),
		"  ",
		styles.Body.Render("Score: "),
		styles.Accent.Render(scoreStr),
		"  ",
		styles.Body.Render("Lives: "),
		styles.Error.Render(livesStr),
		"  ",
		styles.Body.Render("Level: "),
		styles.Accent.Render(levelStr),
	)

	// Progress indicator
	var progressIndicator string
	if g.showProgress {
		if g.progressDone {
			progressIndicator = styles.SuccessText.Render("✓ Analysis complete")
		} else if g.progressFailed {
			progressIndicator = styles.Error.Render("✗ Analysis failed")
		} else if g.progressPhase != "" {
			progressIndicator = g.progressSpinner.SpinnerWithText(g.progressPhase)
		} else {
			progressIndicator = g.progressSpinner.SpinnerWithText("Analyzing...")
		}
		progressIndicator = lipgloss.NewStyle().
			Width(g.width).
			Align(lipgloss.Center).
			PaddingTop(0).
			PaddingBottom(1).
			Render(progressIndicator)
	}

	// Game box
	gameBox := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(styles.GameCyan).
		Render(gameArea)

	// Footer
	footer := styles.Muted.Render("← → move • space shoot • p pause • esc exit")

	// Overlay for pause/game over
	var overlay string
	if g.paused {
		overlay = lipgloss.Place(
			g.width,
			g.height,
			lipgloss.Center,
			lipgloss.Center,
			styles.Box.Render(styles.Accent.Render("PAUSED\n\nPress P to continue")),
		)
	} else if g.gameOver {
		gameOverContent := lipgloss.JoinVertical(
			lipgloss.Center,
			styles.Error.Render("GAME OVER"),
			"",
			styles.Body.Render("Final Score: ")+styles.Accent.Render(scoreStr),
			"",
			styles.Muted.Render("Press R to restart • ESC to exit"),
		)
		overlay = lipgloss.Place(
			g.width,
			g.height,
			lipgloss.Center,
			lipgloss.Center,
			styles.Box.Render(gameOverContent),
		)
	}

	// Combine
	var result string
	if progressIndicator != "" {
		result = lipgloss.JoinVertical(
			lipgloss.Center,
			header,
			"",
			gameBox,
			progressIndicator,
			footer,
		)
	} else {
		result = lipgloss.JoinVertical(
			lipgloss.Center,
			header,
			"",
			gameBox,
			"",
			footer,
		)
	}

	if overlay != "" {
		result = overlay
	}

	return result
}

// GameTickMsg is sent for game updates
type GameTickMsg time.Time

// GameTickCmd returns a command for game ticks
func GameTickCmd() tea.Cmd {
	return tea.Tick(time.Millisecond*50, func(t time.Time) tea.Msg {
		return GameTickMsg(t)
	})
}
