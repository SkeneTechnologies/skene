package backend

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"

	"skene/internal/api"
)

func envelope(t *testing.T, raw string) api.EventEnvelope {
	t.Helper()
	var probe struct {
		ID   string `json:"id"`
		Type string `json:"type"`
	}
	if err := json.Unmarshal([]byte(raw), &probe); err != nil {
		t.Fatalf("bad test fixture: %v", err)
	}
	return api.EventEnvelope{ID: probe.ID, Type: probe.Type, Raw: []byte(raw)}
}

func sessionJSON(id, agent, parentID string) string {
	parent := "null"
	if parentID != "" {
		parent = fmt.Sprintf("%q", parentID)
	}
	return fmt.Sprintf(`{"id":%q,"projectId":"prj_1","parentId":%s,"agent":%q,"created":1,"updated":1}`,
		id, parent, agent)
}

func TestRunTrackerFollowsRunToIdle(t *testing.T) {
	var steps, details []string
	tracker := newRunTracker("ses_root", func(u Update) {
		if u.Detail {
			details = append(details, u.Message)
		} else {
			steps = append(steps, u.Phase+"|"+u.Message)
		}
	})
	var result JourneyResult

	frames := []string{
		fmt.Sprintf(`{"id":"e1","type":"session.created","properties":{"session":%s}}`, sessionJSON("ses_root", "skene", "")),
		fmt.Sprintf(`{"id":"e2","type":"session.created","properties":{"session":%s}}`, sessionJSON("ses_code", "code", "ses_root")),
		`{"id":"e3","type":"part.created","properties":{"part":{"id":"p1","sessionId":"ses_code","messageId":"m1","type":"feature","feature":{"proposedId":"signup","name":"User signs up","description":"d","evidence":[]}},"delta":null}}`,
		`{"id":"e4","type":"part.created","properties":{"part":{"id":"p2","sessionId":"ses_code","messageId":"m1","type":"tool","tool":"read_file","callId":"c1","state":{"status":"completed","input":{},"output":"","title":null,"metadata":{},"started":null,"ended":null}},"delta":null}}`,
		fmt.Sprintf(`{"id":"e5","type":"session.idle","properties":{"session":%s}}`, sessionJSON("ses_code", "code", "ses_root")),
		`{"id":"e6","type":"part.created","properties":{"part":{"id":"p3","sessionId":"ses_root","messageId":"m2","type":"artifact","path":"/repo/skene/journey.yaml","title":"journey.yaml","summary":null},"delta":null}}`,
	}
	for _, frame := range frames {
		done, err := tracker.handle(envelope(t, frame), &result)
		if err != nil || done {
			t.Fatalf("run ended early on %s: done=%v err=%v", frame, done, err)
		}
	}

	idle := fmt.Sprintf(`{"id":"e7","type":"session.idle","properties":{"session":%s}}`, sessionJSON("ses_root", "skene", ""))
	done, err := tracker.handle(envelope(t, idle), &result)
	if err != nil || !done {
		t.Fatalf("expected clean finish, got done=%v err=%v", done, err)
	}

	if result.Features != 1 {
		t.Fatalf("expected 1 feature, got %d", result.Features)
	}
	if result.ArtifactPath != "/repo/skene/journey.yaml" {
		t.Fatalf("artifact path not captured: %q", result.ArtifactPath)
	}

	// Step-level lines persist in the progress log.
	joinedSteps := strings.Join(steps, "\n")
	for _, want := range []string{
		"▶ code agent started",
		"✓ code agent finished — 1 feature(s)",
		"journey.yaml written to /repo/skene/journey.yaml",
	} {
		if !strings.Contains(joinedSteps, want) {
			t.Fatalf("missing step line %q in:\n%s", want, joinedSteps)
		}
	}

	// Per-feature and per-tool lines are ticker detail, not steps.
	joinedDetails := strings.Join(details, "\n")
	for _, want := range []string{
		"[code] ✦ feature: User signs up",
		"[code] ✓ read_file",
	} {
		if !strings.Contains(joinedDetails, want) {
			t.Fatalf("missing detail line %q in:\n%s", want, joinedDetails)
		}
		if strings.Contains(joinedSteps, want) {
			t.Fatalf("detail line %q leaked into steps:\n%s", want, joinedSteps)
		}
	}
}

func TestRunTrackerSurfacesSessionError(t *testing.T) {
	tracker := newRunTracker("ses_root", nil)
	var result JourneyResult

	raw := fmt.Sprintf(`{"id":"e1","type":"session.error","properties":{"session":%s,"error":"no credentials"}}`,
		sessionJSON("ses_root", "skene", ""))
	done, err := tracker.handle(envelope(t, raw), &result)
	if !done || err == nil || err.Error() != "no credentials" {
		t.Fatalf("expected terminal error, got done=%v err=%v", done, err)
	}
}

func TestRunTrackerIgnoresOtherWorkspaceSessions(t *testing.T) {
	tracker := newRunTracker("ses_root", func(u Update) {
		t.Fatalf("unexpected update: %s %s", u.Phase, u.Message)
	})
	var result JourneyResult

	// A session tree rooted elsewhere in the same workspace must not leak
	// into this run's progress.
	frames := []string{
		fmt.Sprintf(`{"id":"e1","type":"session.created","properties":{"session":%s}}`, sessionJSON("ses_other", "skene", "")),
		fmt.Sprintf(`{"id":"e2","type":"session.idle","properties":{"session":%s}}`, sessionJSON("ses_other", "skene", "")),
		`{"id":"e3","type":"part.created","properties":{"part":{"id":"p1","sessionId":"ses_other","messageId":"m1","type":"feature","feature":{"proposedId":"x","name":"X","description":"d","evidence":[]}},"delta":null}}`,
	}
	for _, frame := range frames {
		done, err := tracker.handle(envelope(t, frame), &result)
		if done || err != nil {
			t.Fatalf("foreign session ended the run: done=%v err=%v", done, err)
		}
	}
	if result.Features != 0 {
		t.Fatalf("foreign feature counted: %d", result.Features)
	}
}
