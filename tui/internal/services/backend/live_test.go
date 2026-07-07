package backend

// Live smoke test against a real skene server. Skipped unless
// SKENE_SERVER_URL points at a running server, e.g.:
//
//	(cd .. && uv run skene serve --port 4917) &
//	SKENE_SERVER_URL=http://127.0.0.1:4917 go test ./internal/services/backend -run TestLive -v
//
// It exercises the attach path, the SSE reader against real framing, and
// the error surfaces the TUI depends on (404 journey, 503 analyse without
// credentials). It does not run a full analysis (needs LLM credentials).

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"skene/internal/api"
)

func TestLiveServerSmoke(t *testing.T) {
	url := os.Getenv("SKENE_SERVER_URL")
	if url == "" {
		t.Skip("SKENE_SERVER_URL not set")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	server, err := Connect(ctx, Config{}, nil)
	if err != nil {
		t.Fatalf("Connect: %v", err)
	}

	dir := t.TempDir()

	// GET /journey on a fresh workspace is a clean "no data yet".
	journey, err := server.JourneyJSON(ctx, dir)
	if err != nil {
		t.Fatalf("JourneyJSON: %v", err)
	}
	if journey != nil {
		t.Fatalf("expected no journey for fresh workspace, got %v", journey)
	}

	// The SSE stream greets with server.connected.
	streamCtx, stopStream := context.WithCancel(ctx)
	defer stopStream()
	events, closeEvents, err := server.openEvents(streamCtx, dir)
	if err != nil {
		t.Fatalf("openEvents: %v", err)
	}
	defer closeEvents()
	select {
	case e := <-events:
		if e.Type != "server.connected" {
			t.Fatalf("expected server.connected first, got %s", e.Type)
		}
	case <-ctx.Done():
		t.Fatal("no server.connected event before timeout")
	}

	// Without LLM credentials the analyse route must fail fast with the
	// configuration hint (503), not create a doomed session. A server with
	// credentials accepts instead — abort the run and check the abort path.
	if sessionID, err := server.startAnalysis(ctx, dir); err == nil {
		t.Log("startAnalysis accepted (server has credentials); exercising abort instead")
		server.abort(sessionID)
	} else if !strings.Contains(err.Error(), "credentials") {
		t.Fatalf("expected credentials error from startAnalysis, got: %v", err)
	}
}

// TestLiveFullJourney drives a complete analysis through RunJourney against
// a tiny fixture repo. Requires a running server *with LLM credentials* and
// spends real tokens — hence its own opt-in flag:
//
//	SKENE_SERVER_URL=... SKENE_LIVE_FULL=1 go test ./internal/services/backend -run TestLiveFullJourney -v
func TestLiveFullJourney(t *testing.T) {
	url := os.Getenv("SKENE_SERVER_URL")
	if url == "" || os.Getenv("SKENE_LIVE_FULL") == "" {
		t.Skip("SKENE_SERVER_URL and SKENE_LIVE_FULL not set")
	}

	dir := t.TempDir()
	writeFixture := func(name, content string) {
		t.Helper()
		if err := os.WriteFile(dir+"/"+name, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	writeFixture("auth.py", `
def signup(email, password):
    """Create an account and send the verification email."""
    user = db.create_user(email, password)
    analytics.track("user_signed_up", user.id)
    send_verification_email(user)
    return user

def verify_email(token):
    user = db.verify(token)
    analytics.track("email_verified", user.id)
`)
	writeFixture("billing.py", `
def start_subscription(user, plan):
    """Upgrade a verified user to a paid plan."""
    charge = stripe.subscribe(user, plan)
    analytics.track("subscription_started", user.id, plan)
    return charge
`)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	server, err := Connect(ctx, Config{}, nil)
	if err != nil {
		t.Fatalf("Connect: %v", err)
	}

	result := server.RunJourney(ctx, dir, func(u Update) {
		t.Logf("progress: phase=%q %s", u.Phase, u.Message)
	})
	if result.Err != nil {
		t.Fatalf("RunJourney: %v", result.Err)
	}
	if result.ArtifactPath == "" {
		t.Fatal("run finished without an artifact part")
	}
	if _, err := os.Stat(result.ArtifactPath); err != nil {
		t.Fatalf("artifact missing on disk: %v", err)
	}

	journey, err := server.JourneyJSON(ctx, dir)
	if err != nil || journey == nil {
		t.Fatalf("GET /journey after run: %v (nil=%v)", err, journey == nil)
	}
	t.Logf("journey keys: %v; milestones streamed: %d", mapKeys(journey), result.Milestones)
}

func mapKeys(m map[string]interface{}) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

func TestLiveSpawnedServer(t *testing.T) {
	if os.Getenv("SKENE_LIVE_SPAWN") == "" {
		t.Skip("SKENE_LIVE_SPAWN not set")
	}
	// Force the spawn path even if SKENE_SERVER_URL is set for the other test.
	t.Setenv("SKENE_SERVER_URL", "")

	ctx, cancel := context.WithTimeout(context.Background(), startupTimeout)
	defer cancel()

	var statusLines []string
	server, err := Connect(ctx, Config{}, func(line string) { statusLines = append(statusLines, line) })
	if err != nil {
		t.Fatalf("Connect (spawn): %v\nstatus: %s", err, strings.Join(statusLines, "\n"))
	}
	defer server.Stop()

	if err := server.checkHealth(ctx); err != nil {
		t.Fatalf("health after spawn: %v", err)
	}

	var _ api.EventEnvelope // keep the api import if assertions above change
}
