package uvresolver

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"skene/internal/constants"
)

// Resolve returns the absolute path to a working uvx binary.
// It checks: (1) system PATH, (2) ~/.skene/bin/ cache, (3) auto-downloads.
func Resolve() (string, error) {
	if path, err := exec.LookPath("uvx"); err == nil {
		return path, nil
	}

	cacheDir, err := cacheDirectory()
	if err != nil {
		return "", fmt.Errorf("cannot determine cache directory: %w", err)
	}

	cachedPath := filepath.Join(cacheDir, uvxBinaryName())
	if _, err := os.Stat(cachedPath); err == nil {
		return cachedPath, nil
	}

	if err := ensureCached(cacheDir); err != nil {
		return "", err
	}

	return cachedPath, nil
}

func cacheDirectory() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, constants.SkeneCacheDir, constants.SkeneCacheBinDir), nil
}

func uvxBinaryName() string {
	if runtime.GOOS == "windows" {
		return "uvx.exe"
	}
	return "uvx"
}

func ensureCached(cacheDir string) error {
	if err := os.MkdirAll(cacheDir, 0755); err != nil {
		return fmt.Errorf("failed to create cache directory %s: %w", cacheDir, err)
	}
	return downloadUV(cacheDir)
}

func downloadUV(cacheDir string) error {
	archive, err := platformArchive()
	if err != nil {
		return err
	}

	url := constants.UVDownloadBaseURL + "/" + archive

	resp, err := http.Get(url)
	if err != nil {
		return fmt.Errorf("failed to download uv from %s: %w", url, err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to download uv: HTTP %d from %s", resp.StatusCode, url)
	}

	if strings.HasSuffix(archive, ".zip") {
		return extractZip(resp.Body, cacheDir)
	}
	return extractTarGz(resp.Body, cacheDir)
}

func platformArchive() (string, error) {
	key := runtime.GOOS + "/" + runtime.GOARCH
	switch key {
	case "darwin/arm64":
		return "uv-aarch64-apple-darwin.tar.gz", nil
	case "darwin/amd64":
		return "uv-x86_64-apple-darwin.tar.gz", nil
	case "linux/amd64":
		return "uv-x86_64-unknown-linux-gnu.tar.gz", nil
	case "linux/arm64":
		return "uv-aarch64-unknown-linux-gnu.tar.gz", nil
	case "windows/amd64":
		return "uv-x86_64-pc-windows-msvc.zip", nil
	case "windows/arm64":
		return "uv-aarch64-pc-windows-msvc.zip", nil
	default:
		return "", fmt.Errorf("unsupported platform: %s/%s", runtime.GOOS, runtime.GOARCH)
	}
}

func extractTarGz(r io.Reader, destDir string) error {
	gz, err := gzip.NewReader(r)
	if err != nil {
		return fmt.Errorf("failed to create gzip reader: %w", err)
	}
	defer func() { _ = gz.Close() }()

	tr := tar.NewReader(gz)
	wantNames := map[string]bool{
		"uv":  true,
		"uvx": true,
	}

	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("tar read error: %w", err)
		}

		baseName := filepath.Base(header.Name)
		if !wantNames[baseName] {
			continue
		}

		destPath := filepath.Join(destDir, baseName)
		f, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
		if err != nil {
			return fmt.Errorf("failed to create %s: %w", destPath, err)
		}
		if _, err := io.Copy(f, tr); err != nil {
			_ = f.Close()
			return fmt.Errorf("failed to write %s: %w", destPath, err)
		}
		_ = f.Close()
	}

	uvxPath := filepath.Join(destDir, "uvx")
	if _, err := os.Stat(uvxPath); os.IsNotExist(err) {
		return fmt.Errorf("uvx binary not found in downloaded archive")
	}

	return nil
}

func extractZip(r io.Reader, destDir string) error {
	tmpFile, err := os.CreateTemp("", "uv-*.zip")
	if err != nil {
		return fmt.Errorf("failed to create temp file: %w", err)
	}
	defer func() { _ = os.Remove(tmpFile.Name()) }()
	defer func() { _ = tmpFile.Close() }()

	if _, err := io.Copy(tmpFile, r); err != nil {
		return fmt.Errorf("failed to download zip: %w", err)
	}
	_ = tmpFile.Close()

	zr, err := zip.OpenReader(tmpFile.Name())
	if err != nil {
		return fmt.Errorf("failed to open zip: %w", err)
	}
	defer func() { _ = zr.Close() }()

	wantNames := map[string]bool{
		"uv.exe":  true,
		"uvx.exe": true,
	}

	for _, f := range zr.File {
		baseName := filepath.Base(f.Name)
		if !wantNames[baseName] {
			continue
		}

		destPath := filepath.Join(destDir, baseName)
		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("failed to open %s in zip: %w", f.Name, err)
		}

		out, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
		if err != nil {
			_ = rc.Close()
			return fmt.Errorf("failed to create %s: %w", destPath, err)
		}
		if _, err := io.Copy(out, rc); err != nil {
			_ = out.Close()
			_ = rc.Close()
			return fmt.Errorf("failed to write %s: %w", destPath, err)
		}
		_ = out.Close()
		_ = rc.Close()
	}

	uvxPath := filepath.Join(destDir, "uvx.exe")
	if _, err := os.Stat(uvxPath); os.IsNotExist(err) {
		return fmt.Errorf("uvx.exe not found in downloaded archive")
	}

	return nil
}
