package game

import (
	"fmt"
	"math"
	"math/rand"
	"skene/internal/constants"
	"skene/internal/tui/components"
	"skene/internal/tui/styles"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

const (
	playerX    = 8
	shootEvery = 3

	terrainAmplitude = 3.0
	terrainFreq      = 0.08
	terrainBorder    = 2
)

var (
	styleShip     lipgloss.Style
	styleBullet   lipgloss.Style
	styleEnemy    lipgloss.Style
	styleTerrain  lipgloss.Style
	styleHUD      lipgloss.Style
	styleExplo    lipgloss.Style
	styleDead     lipgloss.Style
	styleEnemyBul lipgloss.Style
)

// RebuildGameStyles initializes game styles. Call this after styles.Init()
// to ensure theme detection has run.
func RebuildGameStyles() {
	styleShip = styles.AccentStyle()
	styleBullet = lipgloss.NewStyle().Foreground(styles.ErrorColor)
	styleEnemy = lipgloss.NewStyle().Foreground(styles.ErrorColor)
	styleTerrain = styles.AccentStyle()
	styleHUD = lipgloss.NewStyle().Foreground(styles.TextColor).Bold(true)
	styleExplo = lipgloss.NewStyle().Foreground(styles.WarningColor)
	styleDead = lipgloss.NewStyle().Foreground(styles.ErrorColor).Bold(true)
	styleEnemyBul = lipgloss.NewStyle().Foreground(styles.WarningColor)
}

type vec2 struct{ x, y int }

type enemy struct {
	pos        vec2
	alive      bool
	kind       int // 0=fighter, 1=heavy, 2=shooter, 3=boss
	hp         int
	phase      float64
	vy         float64
	shootTimer int
}

type bullet struct {
	pos   vec2
	alive bool
	speed int
}

type explosion struct {
	pos   vec2
	frame int
}

type obstacle struct {
	worldX int
	y      int
	width  int
	height int
}

// Game is the R-Type side-scroller game.
type Game struct {
	termWidth  int
	termHeight int
	width      int
	height     int

	ceil  []int
	floor []int

	playerY     int
	playerVY    float64
	playerHP    int
	score       int
	tick        int
	shootCd     int
	dead        bool
	started     bool
	scroll      int
	scrollSpeed float64
	scrollAccum float64
	rng         *rand.Rand

	bullets      []bullet
	enemyBullets []bullet
	enemies      []enemy
	explosions   []explosion
	obstacles    []obstacle

	spawnTimer    int
	flashTimer    int
	obstacleTimer int

	showProgress    bool
	progressPhase   string
	progressDone    bool
	progressFailed  bool
	progressSpinner *components.Spinner
}

func generateTerrain(offset int, count int, h int) (ceil []int, floor []int) {
	ceil = make([]int, count)
	floor = make([]int, count)
	for x := 0; x < count; x++ {
		col := x + offset
		wave := terrainAmplitude*math.Sin(float64(col)*terrainFreq) +
			terrainAmplitude*0.5*math.Sin(float64(col)*terrainFreq*2.3+1.2)
		mid := float64(h) / 2.0
		ceilRow := int(math.Round(mid - float64(h)/2.0 + terrainBorder + wave))
		floorRow := int(math.Round(mid + float64(h)/2.0 - terrainBorder - wave*0.7))

		if ceilRow < 1 {
			ceilRow = 1
		}
		if ceilRow > h-2-terrainBorder {
			ceilRow = h - 2 - terrainBorder
		}
		if floorRow < ceilRow+4 {
			floorRow = ceilRow + 4
		}
		if floorRow >= h-1 {
			floorRow = h - 2
		}
		ceil[x] = ceilRow
		floor[x] = floorRow
	}
	return
}

// gridDimensions computes the playable grid size from terminal dimensions.
// Layout: HUD(1) + blank(1) + border-top(1) + grid(H) + border-bottom(1) + progress(1) + footer(1) = H+6
// Width: border-left(1) + grid(W) + border-right(1), capped to sectionWidth pattern.
func gridDimensions(termW, termH int) (gridW, gridH int) {
	sectionW := termW - 20
	if sectionW < 40 {
		sectionW = 40
	}
	if sectionW > 120 {
		sectionW = 120
	}
	gridW = sectionW - 2
	gridH = termH - 8
	if gridH < 10 {
		gridH = 10
	}
	if gridH > 30 {
		gridH = 30
	}
	return
}

// NewGame creates a new R-Type game instance.
func NewGame(termW, termH int) *Game {
	gw, gh := gridDimensions(termW, termH)
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	c, f := generateTerrain(0, gw+20, gh)
	midY := (c[playerX] + f[playerX]) / 2
	return &Game{
		termWidth:       termW,
		termHeight:      termH,
		width:           gw,
		height:          gh,
		ceil:            c,
		floor:           f,
		playerY:         midY,
		playerHP:        5,
		scrollSpeed:     0.7,
		rng:             rng,
		spawnTimer:      20,
		progressSpinner: components.NewSpinner(),
	}
}

// SetSize updates game dimensions from terminal size.
func (g *Game) SetSize(termW, termH int) {
	if termW == g.termWidth && termH == g.termHeight {
		return
	}
	g.termWidth = termW
	g.termHeight = termH
	gw, gh := gridDimensions(termW, termH)
	if gw == g.width && gh == g.height {
		return
	}
	g.width = gw
	g.height = gh
	g.ceil, g.floor = generateTerrain(g.scroll, gw+20, gh)
	col := g.scroll + playerX
	if col < len(g.ceil) {
		mid := (g.ceil[playerX] + g.floor[playerX]) / 2
		if g.playerY < g.ceil[playerX]+1 || g.playerY > g.floor[playerX]-1 {
			g.playerY = mid
		}
	}
}

// MoveUp decreases the player Y (thrust up).
func (g *Game) MoveUp() {
	if !g.started || g.dead {
		return
	}
	g.playerY--
}

// MoveDown increases the player Y (thrust down).
func (g *Game) MoveDown() {
	if !g.started || g.dead {
		return
	}
	g.playerY++
}

// Start begins the game from the title screen or restarts after death.
func (g *Game) Start() {
	if g.dead {
		g.Restart()
		g.started = true
		return
	}
	if !g.started {
		g.started = true
	}
}

// IsStarted returns whether the game has been started.
func (g *Game) IsStarted() bool {
	return g.started
}

// Update advances the game by one tick.
func (g *Game) Update() {
	if !g.started || g.dead {
		return
	}
	g.gameTick()
}

func (g *Game) gameTick() {
	g.tick++

	g.scrollSpeed = 0.7 + float64(g.scroll/500)*0.3
	g.scrollAccum += g.scrollSpeed
	for g.scrollAccum >= 1.0 {
		g.scroll++
		g.scrollAccum -= 1.0
	}

	if g.flashTimer > 0 {
		g.flashTimer--
	}

	needed := g.scroll + g.width + 20
	for len(g.ceil) < needed {
		newC, newF := generateTerrain(len(g.ceil), 20, g.height)
		g.ceil = append(g.ceil, newC...)
		g.floor = append(g.floor, newF...)
	}

	if g.playerVY > 3 {
		g.playerVY = 3
	}
	if g.playerVY < -3 {
		g.playerVY = -3
	}
	g.playerY += int(math.Round(g.playerVY))

	col := g.scroll + playerX
	if col < len(g.ceil) {
		if g.playerY <= g.ceil[col] {
			g.playerY = g.ceil[col] + 1
			g.playerVY = 0
			g.playerHP--
			g.flashTimer = 6
			if g.playerHP <= 0 {
				g.dead = true
				return
			}
		}
		if g.playerY >= g.floor[col] {
			g.playerY = g.floor[col] - 1
			g.playerVY = 0
			g.playerHP--
			g.flashTimer = 6
			if g.playerHP <= 0 {
				g.dead = true
				return
			}
		}
	}

	for _, obs := range g.obstacles {
		if col >= obs.worldX && col < obs.worldX+obs.width {
			if g.playerY >= obs.y && g.playerY < obs.y+obs.height {
				g.playerHP--
				g.flashTimer = 6
				if g.playerHP <= 0 {
					g.dead = true
					return
				}
			}
		}
	}

	g.shootCd--
	if g.shootCd <= 0 {
		g.bullets = append(g.bullets, bullet{pos: vec2{playerX + 2, g.playerY}, alive: true, speed: 3})
		g.shootCd = shootEvery
	}

	for i := range g.bullets {
		if !g.bullets[i].alive {
			continue
		}
		g.bullets[i].pos.x += g.bullets[i].speed
		if g.bullets[i].pos.x >= g.width {
			g.bullets[i].alive = false
		}
		bx := g.scroll + g.bullets[i].pos.x
		by := g.bullets[i].pos.y
		if bx < len(g.ceil) {
			if by <= g.ceil[bx] || by >= g.floor[bx] {
				g.bullets[i].alive = false
			}
		}
		for _, obs := range g.obstacles {
			if bx >= obs.worldX && bx < obs.worldX+obs.width {
				if by >= obs.y && by < obs.y+obs.height {
					g.bullets[i].alive = false
					break
				}
			}
		}
	}

	g.spawnTimer--
	if g.spawnTimer <= 0 {
		spawnDelay := 15 - g.score/10
		if spawnDelay < 5 {
			spawnDelay = 5
		}
		g.spawnTimer = spawnDelay + g.rng.Intn(10)

		spawnCol := g.scroll + g.width - 2
		if spawnCol < len(g.ceil) {
			ceilY := g.ceil[spawnCol]
			floorY := g.floor[spawnCol]
			if floorY-ceilY > 4 {
				ey := ceilY + 2 + g.rng.Intn(floorY-ceilY-4)
				kind := 0
				hp := 1
				roll := g.rng.Intn(20)
				if roll < 1 {
					kind = 3
					hp = 8
				} else if roll < 3 {
					kind = 1
					hp = 3
				} else if roll < 10 {
					kind = 2
					hp = 2
				}
				g.enemies = append(g.enemies, enemy{
					pos:        vec2{g.width - 2, ey},
					alive:      true,
					kind:       kind,
					hp:         hp,
					phase:      g.rng.Float64() * math.Pi * 2,
					vy:         (g.rng.Float64() - 0.5) * 0.5,
					shootTimer: 20 + g.rng.Intn(20),
				})
			}
		}
	}

	g.obstacleTimer--
	if g.obstacleTimer <= 0 {
		g.obstacleTimer = 12 + g.rng.Intn(15)
		spawnCol := g.scroll + g.width + 5
		if spawnCol < len(g.ceil) {
			ceilY := g.ceil[spawnCol]
			floorY := g.floor[spawnCol]
			gap := floorY - ceilY
			if gap > 10 {
				h := 3 + g.rng.Intn(3)
				w := 3 + g.rng.Intn(4)
				spawnRange := gap - h - 6
				if spawnRange < 1 {
					spawnRange = 1
				}
				oy := ceilY + 3 + g.rng.Intn(spawnRange)
				g.obstacles = append(g.obstacles, obstacle{
					worldX: spawnCol,
					y:      oy,
					width:  w,
					height: h,
				})
			}
		}
	}

	for i := range g.enemies {
		if !g.enemies[i].alive {
			continue
		}
		g.enemies[i].pos.x--
		g.enemies[i].phase += 0.15
		g.enemies[i].pos.y += int(math.Round(math.Sin(g.enemies[i].phase) * 0.8))

		ec := g.scroll + g.enemies[i].pos.x
		ey := g.enemies[i].pos.y
		if ec >= 0 && ec < len(g.ceil) {
			if ey <= g.ceil[ec] || ey >= g.floor[ec] {
				g.enemies[i].alive = false
				continue
			}
		}

		if g.enemies[i].pos.x < 0 {
			g.enemies[i].alive = false
		}

		hitRangeX := 1
		hitRangeY := 1
		if g.enemies[i].kind == 3 {
			hitRangeX = 3
			hitRangeY = 2
		}
		if iabs(g.enemies[i].pos.x-playerX) <= hitRangeX && iabs(g.enemies[i].pos.y-g.playerY) <= hitRangeY {
			g.enemies[i].alive = false
			g.explosions = append(g.explosions, explosion{pos: vec2{playerX, g.playerY}})
			g.playerHP--
			g.flashTimer = 6
			if g.playerHP <= 0 {
				g.dead = true
				return
			}
		}

		if g.enemies[i].kind == 2 && g.enemies[i].pos.x < g.width-5 {
			g.enemies[i].shootTimer--
			if g.enemies[i].shootTimer <= 0 {
				g.enemies[i].shootTimer = 30 + g.rng.Intn(20)
				g.enemyBullets = append(g.enemyBullets, bullet{
					pos:   vec2{g.enemies[i].pos.x - 1, g.enemies[i].pos.y},
					alive: true,
					speed: -2,
				})
			}
		}
	}

	for i := range g.enemyBullets {
		if !g.enemyBullets[i].alive {
			continue
		}
		g.enemyBullets[i].pos.x += g.enemyBullets[i].speed
		if g.enemyBullets[i].pos.x < 0 {
			g.enemyBullets[i].alive = false
			continue
		}
		bx := g.scroll + g.enemyBullets[i].pos.x
		by := g.enemyBullets[i].pos.y
		if bx >= 0 && bx < len(g.ceil) {
			if by <= g.ceil[bx] || by >= g.floor[bx] {
				g.enemyBullets[i].alive = false
				continue
			}
		}
		for _, obs := range g.obstacles {
			if bx >= obs.worldX && bx < obs.worldX+obs.width {
				if by >= obs.y && by < obs.y+obs.height {
					g.enemyBullets[i].alive = false
					break
				}
			}
		}
		if iabs(g.enemyBullets[i].pos.x-playerX) <= 1 && iabs(g.enemyBullets[i].pos.y-g.playerY) <= 1 {
			g.enemyBullets[i].alive = false
			g.playerHP--
			g.flashTimer = 6
			if g.playerHP <= 0 {
				g.dead = true
				return
			}
		}
	}

	for bi := range g.bullets {
		if !g.bullets[bi].alive {
			continue
		}
		for ei := range g.enemies {
			if !g.enemies[ei].alive {
				continue
			}
			hitX := 1
			hitY := 1
			if g.enemies[ei].kind == 3 {
				hitX = 3
				hitY = 2
			}
			if iabs(g.bullets[bi].pos.x-g.enemies[ei].pos.x) <= hitX &&
				iabs(g.bullets[bi].pos.y-g.enemies[ei].pos.y) <= hitY {
				g.bullets[bi].alive = false
				g.enemies[ei].hp--
				if g.enemies[ei].hp <= 0 {
					g.enemies[ei].alive = false
					g.explosions = append(g.explosions, explosion{pos: g.enemies[ei].pos})
					g.score++
				}
				break
			}
		}
	}

	for i := range g.explosions {
		g.explosions[i].frame++
	}
	live := g.explosions[:0]
	for _, e := range g.explosions {
		if e.frame < 5 {
			live = append(live, e)
		}
	}
	g.explosions = live

	if g.tick%60 == 0 {
		g.gcSlices()
	}
}

func (g *Game) gcSlices() {
	lb := g.bullets[:0]
	for _, b := range g.bullets {
		if b.alive {
			lb = append(lb, b)
		}
	}
	g.bullets = lb

	leb := g.enemyBullets[:0]
	for _, b := range g.enemyBullets {
		if b.alive {
			leb = append(leb, b)
		}
	}
	g.enemyBullets = leb

	le := g.enemies[:0]
	for _, e := range g.enemies {
		if e.alive {
			le = append(le, e)
		}
	}
	g.enemies = le

	lo := g.obstacles[:0]
	for _, o := range g.obstacles {
		if o.worldX+o.width > g.scroll {
			lo = append(lo, o)
		}
	}
	g.obstacles = lo
}

// Restart resets the game to initial state.
func (g *Game) Restart() {
	g.ceil, g.floor = generateTerrain(0, g.width+20, g.height)
	midY := (g.ceil[playerX] + g.floor[playerX]) / 2
	g.playerY = midY
	g.playerVY = 0
	g.playerHP = 5
	g.score = 0
	g.tick = 0
	g.shootCd = 0
	g.dead = false
	g.started = false
	g.scroll = 0
	g.scrollSpeed = 0.7
	g.scrollAccum = 0
	g.bullets = nil
	g.enemyBullets = nil
	g.enemies = nil
	g.explosions = nil
	g.obstacles = nil
	g.spawnTimer = 20
	g.flashTimer = 0
	g.obstacleTimer = 0
	g.rng = rand.New(rand.NewSource(time.Now().UnixNano()))
}

// IsGameOver returns whether the player is dead.
func (g *Game) IsGameOver() bool {
	return g.dead
}

// SetProgressInfo updates the analysis progress indicator shown below the game.
func (g *Game) SetProgressInfo(phase string, done, failed bool) {
	g.showProgress = true
	g.progressPhase = phase
	g.progressDone = done
	g.progressFailed = failed
}

// ClearProgressInfo hides the progress indicator.
func (g *Game) ClearProgressInfo() {
	g.showProgress = false
	g.progressPhase = ""
	g.progressDone = false
	g.progressFailed = false
}

// TickProgressSpinner advances the progress spinner animation.
func (g *Game) TickProgressSpinner() {
	if g.progressSpinner != nil {
		g.progressSpinner.Tick()
	}
}

// Render draws the full game view including HUD, game area, and progress.
func (g *Game) Render() string {
	if !g.started {
		return g.titleScreen()
	}
	if g.dead {
		return g.deathScreen()
	}

	type cell struct {
		ch    rune
		style lipgloss.Style
	}
	blankStyle := lipgloss.NewStyle()
	if g.flashTimer > 0 {
		blankStyle = blankStyle.Background(styles.ErrorColor)
	}
	blank := cell{' ', blankStyle}
	grid := make([][]cell, g.height)
	for y := 0; y < g.height; y++ {
		grid[y] = make([]cell, g.width)
		for x := 0; x < g.width; x++ {
			grid[y][x] = blank
		}
	}

	set := func(x, y int, ch rune, st lipgloss.Style) {
		if x >= 0 && x < g.width && y >= 0 && y < g.height {
			grid[y][x] = cell{ch, st}
		}
	}

	terrainChars := []rune{'░', '▒', '▓', '█'}
	for sx := 0; sx < g.width; sx++ {
		col := g.scroll + sx
		if col >= len(g.ceil) {
			continue
		}
		c := g.ceil[col]
		f := g.floor[col]
		for y := 0; y <= c; y++ {
			distFromEdge := c - y
			idx := distFromEdge
			if idx >= len(terrainChars) {
				idx = len(terrainChars) - 1
			}
			set(sx, y, terrainChars[idx], styleTerrain)
		}
		for y := f; y < g.height; y++ {
			distFromEdge := y - f
			idx := distFromEdge
			if idx >= len(terrainChars) {
				idx = len(terrainChars) - 1
			}
			set(sx, y, terrainChars[idx], styleTerrain)
		}
	}

	for _, obs := range g.obstacles {
		for ox := 0; ox < obs.width; ox++ {
			screenX := obs.worldX - g.scroll + ox
			if screenX < 0 || screenX >= g.width {
				continue
			}
			for oy := 0; oy < obs.height; oy++ {
				distX := ox
				if obs.width-1-ox < distX {
					distX = obs.width - 1 - ox
				}
				distY := oy
				if obs.height-1-oy < distY {
					distY = obs.height - 1 - oy
				}
				dist := distX
				if distY < dist {
					dist = distY
				}
				idx := dist
				if idx >= len(terrainChars) {
					idx = len(terrainChars) - 1
				}
				set(screenX, obs.y+oy, terrainChars[idx], styleTerrain)
			}
		}
	}

	for _, b := range g.bullets {
		if b.alive {
			set(b.pos.x, b.pos.y, '─', styleBullet)
		}
	}

	for _, b := range g.enemyBullets {
		if b.alive {
			set(b.pos.x, b.pos.y, '•', styleEnemyBul)
		}
	}

	for _, e := range g.enemies {
		if !e.alive {
			continue
		}
		if e.kind == 3 {
			set(e.pos.x, e.pos.y, '█', styleEnemy)
			set(e.pos.x-1, e.pos.y, '█', styleEnemy)
			set(e.pos.x-2, e.pos.y, '◀', styleEnemy)
			set(e.pos.x, e.pos.y-1, '▀', styleEnemy)
			set(e.pos.x-1, e.pos.y-1, '▀', styleEnemy)
			set(e.pos.x, e.pos.y+1, '▄', styleEnemy)
			set(e.pos.x-1, e.pos.y+1, '▄', styleEnemy)
		} else {
			ch := '>'
			switch e.kind {
			case 1:
				ch = '✦'
			case 2:
				ch = '◄'
			}
			set(e.pos.x, e.pos.y, ch, styleEnemy)
			if e.kind == 1 {
				set(e.pos.x-1, e.pos.y, '<', styleEnemy)
			}
		}
	}

	explFrames := []rune{'*', '+', '·', ' '}
	for _, ex := range g.explosions {
		if ex.frame < len(explFrames) {
			ch := explFrames[ex.frame]
			set(ex.pos.x, ex.pos.y, ch, styleExplo)
			set(ex.pos.x-1, ex.pos.y, ch, styleExplo)
			set(ex.pos.x+1, ex.pos.y, ch, styleExplo)
			set(ex.pos.x, ex.pos.y-1, ch, styleExplo)
			set(ex.pos.x, ex.pos.y+1, ch, styleExplo)
		}
	}

	if !g.dead {
		set(playerX-1, g.playerY-1, '/', styles.AccentStyle())
		set(playerX-1, g.playerY, 'S', styleShip)
		set(playerX, g.playerY, '►', styleShip)
		set(playerX-1, g.playerY+1, '\\', styles.AccentStyle())
	}

	var sb strings.Builder
	for y := 0; y < g.height; y++ {
		for x := 0; x < g.width; x++ {
			c := grid[y][x]
			sb.WriteString(c.style.Render(string(c.ch)))
		}
		if y < g.height-1 {
			sb.WriteByte('\n')
		}
	}

	hp := strings.Repeat("♥ ", g.playerHP) + strings.Repeat("♡ ", 5-g.playerHP)
	hud := styleHUD.Render(fmt.Sprintf(constants.GameHUDFormat, g.score, hp, g.scroll))

	gameBox := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(styles.MidGray).
		Render(sb.String())

	footer := components.FooterHelp([]components.HelpItem{
		{Key: constants.HelpKeyUpDown, Desc: constants.HelpDescMove},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
	}, g.width)

	var progressIndicator string
	if g.showProgress {
		if g.progressDone {
			if g.progressFailed {
				progressIndicator = styles.Error.Render(constants.StatusIconFailed + " " + constants.StatusFailed)
			} else {
				progressIndicator = styles.SuccessText.Render(constants.StatusIconCompleted + " " + constants.StatusCompleted)
			}
		} else {
			progressIndicator = g.progressSpinner.SpinnerWithText(constants.StatusInProgress)
		}
		progressIndicator = lipgloss.NewStyle().
			Width(g.width).
			Align(lipgloss.Center).
			Render(progressIndicator)
	}

	parts := []string{hud, "", gameBox}
	if progressIndicator != "" {
		parts = append(parts, "", progressIndicator)
	}
	parts = append(parts, "", footer)

	return lipgloss.JoinVertical(lipgloss.Center, parts...)
}

const cardWidth = 48

func (g *Game) titleScreen() string {
	timeTo := styles.Title.Render(constants.GameTitle)

	killArt := styleDead.Render(` ██ ▄█▀ ██▓ ██▓     ██▓
 ██▄█▒ ▓██▒▓██▒    ▓██▒
▓███▄░ ▒██▒▒██░    ▒██░
▓██ █▄ ░██░▒██░    ▒██░
▒██▒ █▄░██░░██████▒░██████▒
▒ ▒▒ ▓▒░▓  ░ ▒░▓  ░░ ▒░▓  ░
░ ░▒ ▒░ ▒ ░░ ░ ▒  ░░ ░ ▒  ░
░ ░░ ░  ▒ ░  ░ ░     ░ ░
░  ░    ░      ░  ░    ░  ░`)

	controls := styles.HelpKey.Render("↑") + " " + styles.HelpDesc.Render(constants.GameThrustUp) + "  " +
		styles.HelpKey.Render("↓") + " " + styles.HelpDesc.Render(constants.GameThrustDown)

	autoFire := styles.Muted.Render(constants.GameAutoFire)

	innerContent := lipgloss.JoinVertical(
		lipgloss.Center,
		timeTo,
		"",
		killArt,
		"",
		"",
		controls,
		"",
		autoFire,
	)

	box := styles.Box.
		Width(cardWidth).
		Align(lipgloss.Center).
		Render(innerContent)

	footer := components.FooterHelp([]components.HelpItem{
		{Key: constants.HelpKeyEnter, Desc: constants.HelpDescStartGame},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
	}, g.width)

	parts := []string{box}
	if g.showProgress {
		parts = append(parts, "", g.renderProgressLine())
	}
	parts = append(parts, "", footer)

	return lipgloss.JoinVertical(lipgloss.Center, parts...)
}

func (g *Game) deathScreen() string {
	skull := styleDead.Render(
		"    ███████████\n" +
			"  ██           ██\n" +
			"██   ██     ██   ██\n" +
			"██               ██\n" +
			"  ██  █ █ █ █  ██\n" +
			"  ██  █ █ █ █  ██\n" +
			"    ██       ██\n" +
			"      ███████")

	gameOverTitle := styleDead.Render(constants.GameOver)

	statsContent := lipgloss.JoinVertical(
		lipgloss.Left,
		styles.Muted.Render(constants.GameStatScore)+styles.Body.Render(fmt.Sprintf("%d", g.score)),
		styles.Muted.Render(constants.GameStatDistance)+styles.Body.Render(fmt.Sprintf("%d meters", g.scroll)),
		styles.Muted.Render(constants.GameStatDefeated)+styles.Body.Render(fmt.Sprintf("%d", g.score)),
	)

	innerContent := lipgloss.JoinVertical(
		lipgloss.Center,
		skull,
		"",
		gameOverTitle,
		"",
		"",
		statsContent,
	)

	box := styles.Box.
		Width(cardWidth).
		Align(lipgloss.Center).
		Render(innerContent)

	footer := components.FooterHelp([]components.HelpItem{
		{Key: constants.HelpKeyR, Desc: constants.HelpDescPlayAgain},
		{Key: constants.HelpKeyEsc, Desc: constants.HelpDescBack},
	}, g.width)

	parts := []string{box}
	if g.showProgress {
		parts = append(parts, "", g.renderProgressLine())
	}
	parts = append(parts, "", footer)

	return lipgloss.JoinVertical(lipgloss.Center, parts...)
}

func (g *Game) renderProgressLine() string {
	if !g.showProgress {
		return ""
	}
	var pi string
	if g.progressDone {
		if g.progressFailed {
			pi = styles.Error.Render(constants.StatusIconFailed + " " + constants.StatusFailed)
		} else {
			pi = styles.SuccessText.Render(constants.StatusIconCompleted + " " + constants.StatusCompleted)
		}
	} else {
		pi = g.progressSpinner.SpinnerWithText(constants.StatusInProgress)
	}
	return pi
}

func iabs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// GameTickMsg is sent for game updates.
type GameTickMsg time.Time

// GameTickCmd returns a command that schedules the next game tick.
func GameTickCmd() tea.Cmd {
	return tea.Tick(time.Millisecond*60, func(t time.Time) tea.Msg {
		return GameTickMsg(t)
	})
}
