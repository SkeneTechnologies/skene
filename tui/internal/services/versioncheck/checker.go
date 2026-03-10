package versioncheck

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"skene/internal/constants"
)

// Result holds the outcome of a version check.
type Result struct {
	// NewVersion is set when an update is available (e.g. "v0.4.0").
	NewVersion string
	// UpdateCmd is the command users can run to update.
	UpdateCmd string
}

// githubRelease is the subset of the GitHub API response we care about.
type githubRelease struct {
	TagName string `json:"tag_name"`
}

// Check queries GitHub for the latest TUI release and compares it to the
// running binary's version. Returns nil when already up-to-date or when
// the check cannot be performed (network error, dev build, etc.).
func Check() *Result {
	if constants.Version == "dev" {
		return nil
	}

	client := &http.Client{Timeout: 3 * time.Second}

	// List recent releases and find the latest tui-v* tag.
	// constants.Repository includes the "github.com/" prefix, strip it for the API.
	repo := strings.TrimPrefix(constants.Repository, "github.com/")
	url := fmt.Sprintf("https://api.github.com/repos/%s/releases?per_page=20", repo)
	resp, err := client.Get(url)
	if err != nil || resp.StatusCode != http.StatusOK {
		return nil
	}
	defer resp.Body.Close()

	var releases []githubRelease
	if err := json.NewDecoder(resp.Body).Decode(&releases); err != nil {
		return nil
	}

	latest := latestTUITag(releases)
	if latest == "" {
		return nil
	}

	// Strip "tui-" prefix to compare just the version part.
	latestVersion := strings.TrimPrefix(latest, "tui-")
	if latestVersion == constants.Version {
		return nil
	}

	return &Result{
		NewVersion: latestVersion,
		UpdateCmd:  "curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash",
	}
}

// latestTUITag returns the first tui-v* tag from the releases list,
// which GitHub returns in reverse chronological order. Pre-release
// tags are skipped.
func latestTUITag(releases []githubRelease) string {
	for _, r := range releases {
		if strings.HasPrefix(r.TagName, "tui-v") && !isPreRelease(r.TagName) {
			return r.TagName
		}
	}
	return ""
}

// isPreRelease returns true for tags like tui-v0.3.0rc1, tui-v0.3.0a1, etc.
func isPreRelease(tag string) bool {
	v := strings.TrimPrefix(tag, "tui-")
	for _, suffix := range []string{"rc", "alpha", "beta"} {
		if strings.Contains(v, suffix) {
			return true
		}
	}
	// Check for "a" or "b" followed by a digit (e.g. v0.3.0a1)
	for i := 0; i < len(v)-1; i++ {
		if (v[i] == 'a' || v[i] == 'b') && v[i+1] >= '0' && v[i+1] <= '9' {
			// Make sure it's not part of a hex-like version segment
			if i == 0 || v[i-1] == '.' || v[i-1] >= '0' && v[i-1] <= '9' {
				return true
			}
		}
	}
	return false
}
