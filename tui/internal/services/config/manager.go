package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"skene/internal/constants"
)

// Config represents the skene-growth configuration
type Config struct {
	Provider     string `json:"provider"`
	Model        string `json:"model"`
	APIKey       string `json:"api_key"`
	OutputDir    string `json:"output_dir"`
	Verbose      bool   `json:"verbose"`
	ProjectDir   string `json:"project_dir"`
	BaseURL      string `json:"base_url,omitempty"`
	UseGrowth bool `json:"use_growth"`
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

// LoadConfig loads configuration from files (project takes precedence)
func (m *Manager) LoadConfig() error {
	// Try project config first
	if fileExists(m.ProjectConfigPath) {
		config, err := m.loadConfigFile(m.ProjectConfigPath)
		if err == nil {
			m.Config = config
			return nil
		}
	}

	// Fall back to user config
	if fileExists(m.UserConfigPath) {
		config, err := m.loadConfigFile(m.UserConfigPath)
		if err == nil {
			m.Config = config
			return nil
		}
	}

	// No config found, use defaults
	return nil
}

func (m *Manager) loadConfigFile(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var config Config
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, err
	}

	return &config, nil
}

// SaveConfig saves configuration to project config file
func (m *Manager) SaveConfig() error {
	// Ensure directory exists
	dir := filepath.Dir(m.ProjectConfigPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	data, err := json.MarshalIndent(m.Config, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	if err := os.WriteFile(m.ProjectConfigPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	return nil
}

// SaveUserConfig saves configuration to user config file
func (m *Manager) SaveUserConfig() error {
	// Ensure directory exists
	dir := filepath.Dir(m.UserConfigPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	data, err := json.MarshalIndent(m.Config, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	if err := os.WriteFile(m.UserConfigPath, data, 0644); err != nil {
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
			Models: []Model{
				{ID: "skene-growth-v1", Name: "skene-growth-v1", Description: "Growth analysis model"},
			},
		},
		{
			ID:          "openai",
			Name:        "OpenAI",
			Description: "GPT-4o and GPT-4 models",
			RequiresKey: true,
			Models: []Model{
				{ID: "gpt-4o", Name: "gpt-4o", Description: "Most capable, multimodal"},
				{ID: "gpt-4-turbo", Name: "gpt-4-turbo", Description: "Fast GPT-4 variant"},
				{ID: "gpt-3.5-turbo", Name: "gpt-3.5-turbo", Description: "Fast and affordable"},
			},
		},
		{
			ID:          "anthropic",
			Name:        "Anthropic",
			Description: "Claude models with strong reasoning",
			RequiresKey: true,
			Models: []Model{
				{ID: "claude-opus-4-6", Name: "claude-opus-4-6", Description: "Most capable model for complex tasks"},
				{ID: "claude-sonnet-4-5", Name: "claude-sonnet-4-5", Description: "Best combination of speed and intelligence"},
				{ID: "claude-haiku-4-5", Name: "claude-haiku-4-5", Description: "Fastest model with near-frontier intelligence"},
			},
		},
		{
			ID:          "gemini",
			Name:        "Gemini",
			Description: "Google's Gemini models",
			RequiresKey: true,
			Models: []Model{
				{ID: "gemini-3-flash-preview", Name: "gemini-3-flash-preview", Description: "Fast and efficient"},
				{ID: "gemini-3-pro-preview", Name: "gemini-3-pro-preview", Description: "Advanced capability"},
				{ID: "gemini-2.5-flash", Name: "gemini-2.5-flash", Description: "Balanced performance"},
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
