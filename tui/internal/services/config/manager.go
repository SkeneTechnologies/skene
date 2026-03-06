package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"skene/internal/constants"
)

// Config represents the skene configuration
type Config struct {
	Provider   string
	Model      string
	APIKey     string
	OutputDir  string
	Verbose    bool
	ProjectDir string
	BaseURL    string
	UseGrowth  bool
}

// Manager handles configuration file operations
type Manager struct {
	ProjectConfigPath string
	UserConfigPath    string
	Config            *Config
}

// NewManager creates a new config manager
func NewManager(projectDir string) *Manager {
	homeDir, _ := os.UserHomeDir()

	return &Manager{
		ProjectConfigPath: filepath.Join(projectDir, constants.ProjectConfigFile),
		UserConfigPath:    filepath.Join(homeDir, constants.UserConfigDir, constants.UserConfigFile),
		Config: &Config{
			OutputDir: constants.DefaultOutputDir,
			Verbose:   true,
			UseGrowth: true,
		},
	}
}

// ConfigStatus represents config file status
type ConfigStatus struct {
	Type   string
	Path   string
	Found  bool
	Config *Config
}

// CheckConfigs checks for existing configuration files
func (m *Manager) CheckConfigs() []ConfigStatus {
	statuses := []ConfigStatus{
		{
			Type:  "Project",
			Path:  m.ProjectConfigPath,
			Found: fileExists(m.ProjectConfigPath),
		},
		{
			Type:  "User",
			Path:  m.UserConfigPath,
			Found: fileExists(m.UserConfigPath),
		},
	}

	// Load existing configs
	for i, status := range statuses {
		if status.Found {
			config, err := m.loadConfigFile(status.Path)
			if err == nil {
				statuses[i].Config = config
			}
		}
	}

	return statuses
}

// LoadConfig loads configuration from files.
// User config is loaded first, then project config is merged on top
// (project values take precedence), matching the Python CLI behaviour.
func (m *Manager) LoadConfig() error {
	if fileExists(m.UserConfigPath) {
		if cfg, err := m.loadConfigFile(m.UserConfigPath); err == nil {
			mergeConfig(m.Config, cfg)
		}
	}

	if fileExists(m.ProjectConfigPath) {
		if cfg, err := m.loadConfigFile(m.ProjectConfigPath); err == nil {
			mergeConfig(m.Config, cfg)
		}
	}

	return nil
}

func mergeConfig(dst, src *Config) {
	if src.Provider != "" {
		dst.Provider = src.Provider
	}
	if src.Model != "" {
		dst.Model = src.Model
	}
	if src.APIKey != "" {
		dst.APIKey = src.APIKey
	}
	if src.BaseURL != "" {
		dst.BaseURL = src.BaseURL
	}
	if src.OutputDir != "" {
		dst.OutputDir = src.OutputDir
	}
	if src.ProjectDir != "" {
		dst.ProjectDir = src.ProjectDir
	}
}

func (m *Manager) loadConfigFile(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	kv := parseTOML(string(data))
	config := &Config{}
	for key, value := range kv {
		switch key {
		case "provider":
			config.Provider = value
		case "model":
			config.Model = value
		case "api_key":
			config.APIKey = value
		case "output_dir":
			config.OutputDir = value
		case "base_url":
			config.BaseURL = value
		case "verbose":
			config.Verbose = strings.EqualFold(value, "true")
		case "use_growth":
			config.UseGrowth = strings.EqualFold(value, "true")
		case "project_dir":
			config.ProjectDir = value
		}
	}
	return config, nil
}

// SaveConfig saves configuration to project config file in TOML format.
func (m *Manager) SaveConfig() error {
	return m.writeConfigToPath(m.ProjectConfigPath)
}

// SaveUserConfig saves configuration to user config file in TOML format.
func (m *Manager) SaveUserConfig() error {
	return m.writeConfigToPath(m.UserConfigPath)
}

func (m *Manager) writeConfigToPath(path string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	existing := make(map[string]string)
	if data, err := os.ReadFile(path); err == nil {
		existing = parseTOML(string(data))
	}

	if m.Config.APIKey != "" {
		existing["api_key"] = m.Config.APIKey
	}
	if m.Config.Provider != "" {
		existing["provider"] = m.Config.Provider
	}
	if m.Config.Model != "" {
		existing["model"] = m.Config.Model
	}
	if m.Config.BaseURL != "" {
		existing["base_url"] = m.Config.BaseURL
	}
	if m.Config.OutputDir != "" {
		existing["output_dir"] = m.Config.OutputDir
	}

	content := writeTOML(existing)

	if err := os.WriteFile(path, []byte(content), 0600); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}
	return nil
}

// SetProvider sets the LLM provider
func (m *Manager) SetProvider(provider string) {
	m.Config.Provider = provider
}

// SetModel sets the model name
func (m *Manager) SetModel(model string) {
	m.Config.Model = model
}

// SetAPIKey sets the API key
func (m *Manager) SetAPIKey(key string) {
	m.Config.APIKey = key
}

// SetProjectDir sets the project directory
func (m *Manager) SetProjectDir(dir string) {
	m.Config.ProjectDir = dir
}

// SetBaseURL sets the base URL for generic providers
func (m *Manager) SetBaseURL(url string) {
	m.Config.BaseURL = url
}

// GetMaskedAPIKey returns masked API key for display
func (m *Manager) GetMaskedAPIKey() string {
	if len(m.Config.APIKey) <= 8 {
		return "****"
	}
	return m.Config.APIKey[:4] + ".." + m.Config.APIKey[len(m.Config.APIKey)-4:]
}

// HasValidConfig checks if config has minimum required values
func (m *Manager) HasValidConfig() bool {
	return m.Config.Provider != "" && m.Config.Model != "" && m.Config.APIKey != ""
}

// GetShortenedPath returns a shortened path for display
func GetShortenedPath(path string, maxLen int) string {
	if len(path) <= maxLen {
		return path
	}
	return "..." + path[len(path)-maxLen+3:]
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// parseTOML parses a flat TOML file (no nested tables) into key-value pairs.
func parseTOML(content string) map[string]string {
	result := make(map[string]string)
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "[") {
			continue
		}
		idx := strings.Index(line, "=")
		if idx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])
		value = unquoteTOML(value)
		result[key] = value
	}
	return result
}

func unquoteTOML(s string) string {
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		s = s[1 : len(s)-1]
		s = strings.ReplaceAll(s, `\"`, `"`)
		s = strings.ReplaceAll(s, `\\`, `\`)
	}
	return s
}

// writeTOML serialises a flat key-value map as TOML with comments.
func writeTOML(kv map[string]string) string {
	var b strings.Builder
	b.WriteString("# skene configuration\n")
	b.WriteString("# See: https://github.com/skene-technologies/skene\n\n")

	ordered := []string{"api_key", "provider", "model", "base_url", "output_dir"}
	written := make(map[string]bool)
	for _, key := range ordered {
		if val, ok := kv[key]; ok && val != "" {
			fmt.Fprintf(&b, "%s = %q\n", key, val)
			written[key] = true
		}
	}

	for key, val := range kv {
		if written[key] || val == "" {
			continue
		}
		fmt.Fprintf(&b, "%s = %q\n", key, val)
	}
	return b.String()
}

// Provider represents an LLM provider with its models
type Provider struct {
	ID          string
	Name        string
	Description string
	Models      []Model
	RequiresKey bool
	AuthURL     string // For browser-based auth
	IsLocal     bool   // For local models (Ollama, LM Studio)
	IsGeneric   bool   // For generic OpenAI-compatible APIs
	DefaultBase string // Default base URL for local/generic providers
	Hidden      bool   // Hidden from provider list (kept for upcoming release)
}

// Model represents an LLM model
type Model struct {
	ID          string
	Name        string
	Description string
}

// GetProviders returns all available providers
func GetProviders() []Provider {
	return []Provider{
		{
			ID:          "skene",
			Name:        "Skene (Recommended)",
			Description: "Built-in LLM optimized for growth analysis",
			RequiresKey: true,
			AuthURL:     constants.SkeneAuthURL,
			Hidden:      true,
			Models: []Model{
				{ID: "skene-v1", Name: "skene-v1", Description: "Growth analysis model"},
			},
		},
		{
			ID:          "openai",
			Name:        "OpenAI",
			Description: "OpenAI GPT models",
			RequiresKey: true,
			Models: []Model{
				{ID: "gpt-5.4", Name: "GPT-5.4", Description: "Most capable model for professional work"},
				{ID: "gpt-5.1", Name: "GPT-5.1", Description: "Best for coding and agentic tasks"},
				{ID: "gpt-5-mini", Name: "GPT-5 mini", Description: "Fast, cost-efficient for well-defined tasks"},
			},
		},
		{
			ID:          "anthropic",
			Name:        "Anthropic",
			Description: "Claude models with strong reasoning",
			RequiresKey: true,
			Models: []Model{
				{ID: "claude-opus-4-6", Name: "claude-opus-4-6", Description: "Most capable model for complex tasks"},
				{ID: "claude-sonnet-4-6", Name: "claude-sonnet-4-6", Description: "Best combination of speed and intelligence"},
			},
		},
		{
			ID:          "gemini",
			Name:        "Gemini",
			Description: "Google's Gemini models",
			RequiresKey: true,
			Models: []Model{
				{ID: "gemini-3-pro", Name: "gemini-3-pro", Description: "Most capable Gemini model"},
				{ID: "gemini-3-flash", Name: "gemini-3-flash", Description: "Fast and efficient"},
				{ID: "gemini-2.5-pro", Name: "gemini-2.5-pro", Description: "Advanced reasoning"},
			},
		},
		// TODO: re-enable local model providers after testing
		// {
		// 	ID:          "ollama",
		// 	Name:        "Ollama (Local)",
		// 	Description: "Run models locally with Ollama",
		// 	RequiresKey: false,
		// 	IsLocal:     true,
		// 	DefaultBase: constants.OllamaDefaultBase,
		// 	Models: []Model{
		// 		{ID: "llama3.3", Name: "llama3.3", Description: "Meta's Llama 3.3"},
		// 		{ID: "mistral", Name: "mistral", Description: "Mistral 7B"},
		// 		{ID: "codellama", Name: "codellama", Description: "Code-focused Llama"},
		// 		{ID: "deepseek-r1", Name: "deepseek-r1", Description: "DeepSeek R1 reasoning"},
		// 	},
		// },
		// {
		// 	ID:          "lmstudio",
		// 	Name:        "LM Studio (Local)",
		// 	Description: "Run models locally with LM Studio",
		// 	RequiresKey: false,
		// 	IsLocal:     true,
		// 	DefaultBase: constants.LMStudioDefaultBase,
		// 	Models: []Model{
		// 		{ID: "auto", Name: "Currently loaded model", Description: "Uses whatever model is loaded in LM Studio"},
		// 	},
		// },
		{
			ID:          "generic",
			Name:        "Other (OpenAI-compatible)",
			Description: "Any OpenAI-compatible API endpoint",
			RequiresKey: true,
			IsGeneric:   true,
			Models: []Model{
				{ID: "custom", Name: "Custom model", Description: "Specify model name manually"},
			},
		},
	}
}

// GetProviderByID returns a provider by ID
func GetProviderByID(id string) *Provider {
	providers := GetProviders()
	for _, p := range providers {
		if p.ID == id {
			return &p
		}
	}
	return nil
}

// IsLocalProvider returns true if the provider runs locally
func IsLocalProvider(id string) bool {
	p := GetProviderByID(id)
	return p != nil && p.IsLocal
}

// IsGenericProvider returns true if the provider is generic
func IsGenericProvider(id string) bool {
	p := GetProviderByID(id)
	return p != nil && p.IsGeneric
}
