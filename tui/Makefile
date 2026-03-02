.PHONY: build run clean install dev test lint fmt release

# Binary name
BINARY_NAME=skene
BUILD_DIR=build

# GitHub release settings (bump VERSION when cutting a new release)
REPO=Px8-fi/skene-cli
VERSION=v030

# Build flags
LDFLAGS=-ldflags "-s -w"
HAS_GO := $(shell which go >/dev/null 2>&1 && echo yes || echo no)

# Default target
all: build

# Build the application -- uses Go if available, otherwise downloads pre-built binary
ifeq ($(HAS_GO),yes)
build:
	@echo "Building $(BINARY_NAME) from source..."
	@mkdir -p $(BUILD_DIR)
	go mod download
	go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) ./cmd/skene
else
build:
	@echo "Go not found. Downloading pre-built binary from GitHub Releases..."
	@mkdir -p $(BUILD_DIR)
	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
	ARCH=$$(uname -m); \
	case "$$ARCH" in \
		x86_64|amd64) ARCH=amd64 ;; \
		arm64|aarch64) ARCH=arm64 ;; \
		*) echo "Error: unsupported architecture $$ARCH"; exit 1 ;; \
	esac; \
	ASSET="$(BINARY_NAME)-$$OS-$$ARCH"; \
	URL="https://github.com/$(REPO)/releases/download/$(VERSION)/$$ASSET.tar.gz"; \
	echo "Downloading $$URL ..."; \
	curl -fSL -o $(BUILD_DIR)/$$ASSET.tar.gz "$$URL" || \
		(echo "Error: download failed. Check that release $(VERSION) exists at https://github.com/$(REPO)/releases"; exit 1); \
	tar -xzf $(BUILD_DIR)/$$ASSET.tar.gz -C $(BUILD_DIR); \
	mv $(BUILD_DIR)/$$ASSET $(BUILD_DIR)/$(BINARY_NAME); \
	rm -f $(BUILD_DIR)/$$ASSET.tar.gz; \
	chmod +x $(BUILD_DIR)/$(BINARY_NAME); \
	xattr -d com.apple.quarantine $(BUILD_DIR)/$(BINARY_NAME) 2>/dev/null || true; \
	echo "Downloaded $(BINARY_NAME) $(VERSION) for $$OS/$$ARCH"
endif

# Run the application (builds first if binary doesn't exist)
run:
	@if [ ! -f $(BUILD_DIR)/$(BINARY_NAME) ]; then \
		$(MAKE) build; \
	fi
	@$(BUILD_DIR)/$(BINARY_NAME)

# Development mode with live reload (requires Go + air)
dev:
	@which air > /dev/null 2>&1 || (echo "Installing air..." && go install github.com/air-verse/air@latest)
	@$$(go env GOPATH)/bin/air

# Clean build artifacts
clean:
	@echo "Cleaning..."
	@go clean 2>/dev/null || true
	rm -rf $(BUILD_DIR)

# Install dependencies (requires Go)
install:
	@echo "Installing dependencies..."
	go mod download
	go mod tidy

# Run tests (requires Go)
test:
	@echo "Running tests..."
	go test -v ./...

# Run linter (requires Go + golangci-lint)
lint:
	@which golangci-lint > /dev/null || (echo "Installing golangci-lint..." && go install github.com/golangci-lint/golangci-lint/cmd/golangci-lint@latest)
	golangci-lint run

# Format code (requires Go)
fmt:
	@echo "Formatting code..."
	gofmt -s -w .

# Build for multiple platforms (requires Go)
build-all: build-linux build-darwin build-windows

build-linux:
	@echo "Building for Linux..."
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-linux-amd64 ./cmd/skene

build-darwin:
	@echo "Building for macOS..."
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-darwin-amd64 ./cmd/skene
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-darwin-arm64 ./cmd/skene

build-windows:
	@echo "Building for Windows..."
	GOOS=windows GOARCH=amd64 go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-windows-amd64.exe ./cmd/skene

# Create release archives (requires Go)
release: clean build-all
	@echo "Packaging releases..."
	tar -czf $(BUILD_DIR)/$(BINARY_NAME)-darwin-arm64.tar.gz -C $(BUILD_DIR) $(BINARY_NAME)-darwin-arm64
	tar -czf $(BUILD_DIR)/$(BINARY_NAME)-darwin-amd64.tar.gz -C $(BUILD_DIR) $(BINARY_NAME)-darwin-amd64
	tar -czf $(BUILD_DIR)/$(BINARY_NAME)-linux-amd64.tar.gz -C $(BUILD_DIR) $(BINARY_NAME)-linux-amd64
	cd $(BUILD_DIR) && zip $(BINARY_NAME)-windows-amd64.zip $(BINARY_NAME)-windows-amd64.exe
	@echo "Release build complete! Archives are in $(BUILD_DIR)/"

# Install binary to system
install-bin: build
	@echo "Installing to /usr/local/bin..."
	sudo cp $(BUILD_DIR)/$(BINARY_NAME) /usr/local/bin/$(BINARY_NAME)

# Show help
help:
	@echo "Available targets:"
	@echo "  build       - Build the application (downloads binary if Go is not installed)"
	@echo "  run         - Run the application"
	@echo "  dev         - Run with live reload (requires Go)"
	@echo "  clean       - Clean build artifacts"
	@echo "  install     - Install Go dependencies"
	@echo "  test        - Run tests (requires Go)"
	@echo "  lint        - Run linter (requires Go)"
	@echo "  fmt         - Format code (requires Go)"
	@echo "  build-all   - Build for all platforms (requires Go)"
	@echo "  release     - Build and package for release (requires Go)"
	@echo "  install-bin - Install binary to system"
	@echo "  help        - Show this help"
