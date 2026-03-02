package syscheck

import (
	"os/exec"
	"strings"

	"skene/internal/services/uvresolver"
)

// CheckStatus represents the result of a single check
type CheckStatus int

const (
	StatusPending CheckStatus = iota
	StatusRunning
	StatusPassed
	StatusFailed
	StatusWarning
	StatusSkipped
)

// CheckResult holds the result of a system check
type CheckResult struct {
	Name       string
	Status     CheckStatus
	Message    string
	Detail     string
	FixCommand string
	FixURL     string
	Version    string
	Required   bool
}

// SystemCheckResult holds all system check results
type SystemCheckResult struct {
	UV         CheckResult
	AllPassed  bool
	CanProceed bool
}

// Checker performs system prerequisite checks
type Checker struct {
	results *SystemCheckResult
}

// NewChecker creates a new system checker
func NewChecker() *Checker {
	return &Checker{
		results: &SystemCheckResult{
			AllPassed:  true,
			CanProceed: true,
		},
	}
}

// GetResults returns the current results
func (c *Checker) GetResults() *SystemCheckResult {
	return c.results
}

// RunAllChecks verifies that a uvx binary is available (system PATH or auto-provisioned).
func (c *Checker) RunAllChecks() *SystemCheckResult {
	c.checkUVX()
	return c.results
}

func (c *Checker) checkUVX() {
	c.results.UV = CheckResult{
		Name:     "uvx runtime",
		Required: true,
	}

	uvxPath, err := uvresolver.Resolve()
	if err != nil {
		c.results.UV.Status = StatusFailed
		c.results.UV.Message = "uvx could not be provisioned: " + err.Error()
		c.results.UV.Detail = "The CLI tried to download uv automatically but failed. Check your internet connection."
		c.results.AllPassed = false
		c.results.CanProceed = false
		return
	}

	out, err := exec.Command(uvxPath, "--version").Output()
	if err != nil {
		c.results.UV.Status = StatusWarning
		c.results.UV.Message = "uvx found but version check failed"
		return
	}

	version := strings.TrimSpace(string(out))
	c.results.UV.Status = StatusPassed
	c.results.UV.Message = "uvx ready"
	c.results.UV.Version = version
}

// GetAlternativeInstallCommands returns alternative install methods
func (c *Checker) GetAlternativeInstallCommands() []string {
	return []string{
		"curl -LsSf https://astral.sh/uv/install.sh | sh",
		"pip install uv",
		"brew install uv",
	}
}
