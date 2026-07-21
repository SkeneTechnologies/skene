package backend

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"skene/internal/api"
)

// Update is one structured progress notification from a journey run.
type Update struct {
	// Phase, when non-empty, names the coarse step the run is in (rendered
	// as the active phase). Message is a progress line.
	Phase   string
	Message string
	// Detail marks high-frequency activity (individual tool calls, single
	// feature emissions) meant for a transient ticker. Step-level lines —
	// agents starting/finishing, artifacts written, errors — keep it false
	// and should stay visible for the whole run.
	Detail bool
}

// JourneyResult is the outcome of a journey analysis run.
type JourneyResult struct {
	SessionID    string
	ArtifactPath string // absolute path of the produced journey.yaml
	Features     int
	Err          error
}

const (
	phaseStarting   = "Starting analysis"
	phaseAnalyzing  = "Analyzing codebase & schema"
	phaseFinalizing = "Assembling journey"
)

// RunJourney starts the canned journey analysis for directory and follows
// the event stream until the run finishes. Cancelling ctx aborts the run
// server-side (the abort fans out to the whole child-session tree).
func (s *Server) RunJourney(ctx context.Context, directory string, onUpdate func(Update)) JourneyResult {
	step := func(phase, message string) {
		if onUpdate != nil {
			onUpdate(Update{Phase: phase, Message: message})
		}
	}

	// Subscribe before starting the run so no events are missed.
	events, closeEvents, err := s.openEvents(ctx, directory)
	if err != nil {
		return JourneyResult{Err: fmt.Errorf("event stream: %w", err)}
	}
	defer closeEvents()

	step(phaseStarting, "Requesting journey analysis...")
	sessionID, err := s.startAnalysis(ctx, directory)
	if err != nil {
		return JourneyResult{Err: err}
	}
	step(phaseStarting, "Session "+sessionID)

	result := JourneyResult{SessionID: sessionID}
	run := newRunTracker(sessionID, onUpdate)

	for {
		select {
		case <-ctx.Done():
			s.abort(sessionID)
			result.Err = ctx.Err()
			return result
		case envelope, ok := <-events:
			if !ok {
				result.Err = errors.New("event stream closed before the run finished")
				return result
			}
			done, err := run.handle(envelope, &result)
			if err != nil {
				result.Err = err
				return result
			}
			if done {
				return result
			}
		}
	}
}

// JourneyJSON fetches the workspace's parsed journey.yaml (GET /journey).
// A 404 (no run yet) returns (nil, nil).
func (s *Server) JourneyJSON(ctx context.Context, directory string) (map[string]interface{}, error) {
	resp, err := s.client.GetJourneyJourneyGet(ctx, &api.GetJourneyJourneyGetParams{
		XSkeneDirectory: &directory,
	})
	if err != nil {
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode == http.StatusNotFound {
		return nil, nil
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GET /journey: %s", readAPIError(resp))
	}
	var journey map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&journey); err != nil {
		return nil, fmt.Errorf("GET /journey: %w", err)
	}
	return journey, nil
}

func (s *Server) startAnalysis(ctx context.Context, directory string) (string, error) {
	resp, err := s.client.AnalyseJourneyAnalysePost(ctx,
		&api.AnalyseJourneyAnalysePostParams{XSkeneDirectory: &directory},
		api.JourneyAnalyseRequest{},
	)
	if err != nil {
		return "", fmt.Errorf("start analysis: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusAccepted {
		return "", fmt.Errorf("start analysis: %s", readAPIError(resp))
	}
	var accepted api.JourneyAnalyseAccepted
	if err := json.NewDecoder(resp.Body).Decode(&accepted); err != nil {
		return "", fmt.Errorf("start analysis: %w", err)
	}
	return accepted.SessionId, nil
}

// openEvents starts the SSE subscription and pumps envelopes onto a channel.
// The returned closer tears down the HTTP stream (which ends the pump).
func (s *Server) openEvents(ctx context.Context, directory string) (<-chan api.EventEnvelope, func(), error) {
	resp, err := s.client.EventsEventGet(ctx, &api.EventsEventGetParams{
		XSkeneDirectory: &directory,
	})
	if err != nil {
		return nil, nil, err
	}
	if resp.StatusCode != http.StatusOK {
		body := readAPIError(resp)
		_ = resp.Body.Close()
		return nil, nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, body)
	}

	events := make(chan api.EventEnvelope, 64)
	go func() {
		defer close(events)
		_ = api.ReadEvents(resp.Body, func(e api.EventEnvelope) bool {
			select {
			case events <- e:
				return true
			case <-ctx.Done():
				return false
			}
		})
	}()
	return events, func() { _ = resp.Body.Close() }, nil
}

// abort cancels the running session tree; best-effort with its own deadline
// because the caller's context is already cancelled.
func (s *Server) abort(sessionID string) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	resp, err := s.client.AbortSessionSessionIdAbortPost(ctx, sessionID, &api.AbortSessionSessionIdAbortPostParams{})
	if err == nil {
		_ = resp.Body.Close()
	}
}

// runTracker folds the event stream into progress updates for one root
// session and its subagent children. Step-level updates (agents starting/
// finishing, artifacts, errors) persist in the progress log; per-tool and
// per-feature activity is flagged Detail for the transient ticker.
type runTracker struct {
	rootID string
	// agents maps session id -> agent name, seeded with the root and grown
	// from session.created events for its children.
	agents map[string]string
	// features counts emitted features per session, for the finish line.
	features map[string]int
	notify   func(Update)
}

func newRunTracker(rootID string, notify func(Update)) *runTracker {
	return &runTracker{
		rootID:   rootID,
		agents:   map[string]string{},
		features: map[string]int{},
		notify:   notify,
	}
}

func (t *runTracker) step(phase, message string) {
	if t.notify != nil {
		t.notify(Update{Phase: phase, Message: message})
	}
}

func (t *runTracker) detail(message string) {
	if t.notify != nil {
		t.notify(Update{Message: message, Detail: true})
	}
}

// handle processes one event; done reports that the root session finished.
func (t *runTracker) handle(envelope api.EventEnvelope, result *JourneyResult) (bool, error) {
	decoded, err := envelope.Decode()
	if err != nil || decoded == nil {
		return false, nil // tolerate unknown/undecodable events
	}

	switch event := decoded.(type) {
	case *api.SessionCreated:
		session := event.Properties.Session
		if session.Id == t.rootID {
			t.agents[session.Id] = session.Agent
		} else if session.ParentId != nil && t.tracks(*session.ParentId) {
			t.agents[session.Id] = session.Agent
			t.step(phaseAnalyzing, fmt.Sprintf("▶ %s agent started", session.Agent))
		}
	case *api.SessionIdle:
		session := event.Properties.Session
		if session.Id == t.rootID {
			t.step(phaseFinalizing, "Analysis complete")
			return true, nil
		}
		if t.tracks(session.Id) && session.Id != t.rootID {
			t.step("", fmt.Sprintf("✓ %s agent finished — %d feature(s)", session.Agent, t.features[session.Id]))
		}
	case *api.SessionError:
		session := event.Properties.Session
		if session.Id == t.rootID {
			return true, errors.New(event.Properties.Error)
		}
		if t.tracks(session.Id) {
			// A failed subagent doesn't end the run — the main agent
			// decides how to continue with the sources it has.
			t.step("", fmt.Sprintf("✗ %s agent failed: %s", session.Agent, firstLine(event.Properties.Error)))
		}
	case *api.PartCreated:
		t.handlePart(event.Properties.Part, result)
	case *api.PartUpdated:
		t.handlePart(event.Properties.Part, result)
	}
	return false, nil
}

func (t *runTracker) tracks(sessionID string) bool {
	_, ok := t.agents[sessionID]
	return ok
}

func (t *runTracker) handlePart(part api.PartProps_Part, result *JourneyResult) {
	kind, err := part.Discriminator()
	if err != nil {
		return
	}
	switch kind {
	case "tool":
		if tool, err := part.AsToolPart(); err == nil && t.tracks(tool.SessionId) {
			t.handleToolPart(tool)
		}
	case "feature":
		if feature, err := part.AsFeaturePart(); err == nil && t.tracks(feature.SessionId) {
			result.Features++
			t.features[feature.SessionId]++
			t.detail(fmt.Sprintf("%s ✦ feature: %s", t.tag(feature.SessionId), feature.Feature.Name))
		}
	case "artifact":
		if artifact, err := part.AsArtifactPart(); err == nil && artifact.SessionId == t.rootID {
			// The feature map lands first; only the journey artifact is
			// the run's deliverable.
			if artifact.Title != nil && *artifact.Title == "features.yaml" {
				t.step(phaseFinalizing, "feature map written to "+artifact.Path)
			} else {
				result.ArtifactPath = artifact.Path
				t.step(phaseFinalizing, "journey.yaml written to "+artifact.Path)
			}
		}
	case "text":
		if text, err := part.AsTextPart(); err == nil && text.SessionId == t.rootID {
			if line := firstLine(text.Text); line != "" {
				t.step("", t.tag(text.SessionId)+" "+line)
			}
		}
	}
}

func (t *runTracker) handleToolPart(tool api.ToolPart) {
	tag := t.tag(tool.SessionId)
	state, err := tool.State.ValueByDiscriminator()
	if err != nil {
		return
	}
	// The pipeline tool is a step of the run itself; everything else
	// (list_directory, read_file, ...) is per-call activity for the ticker.
	important := tool.Tool == "synthesize_journey"
	switch st := state.(type) {
	case api.ToolStateRunning:
		title := tool.Tool
		if st.Title != nil && *st.Title != "" {
			title = *st.Title
		}
		if important {
			t.step(phaseFinalizing, fmt.Sprintf("%s ⚙ %s", tag, title))
		} else {
			t.detail(fmt.Sprintf("%s ⚙ %s", tag, title))
		}
	case api.ToolStateCompleted:
		if important {
			t.step("", fmt.Sprintf("%s ✓ %s", tag, tool.Tool))
		} else {
			t.detail(fmt.Sprintf("%s ✓ %s", tag, tool.Tool))
		}
	case api.ToolStateError:
		message := ""
		if st.Error != nil {
			message = *st.Error
		}
		line := fmt.Sprintf("%s ✗ %s: %s", tag, tool.Tool, firstLine(message))
		// Root-session tool failures (a task that died, synthesis errors)
		// are step-level; a failed read inside a subagent is ticker noise.
		if important || tool.SessionId == t.rootID {
			t.step("", line)
		} else {
			t.detail(line)
		}
	}
}

func (t *runTracker) tag(sessionID string) string {
	if agent, ok := t.agents[sessionID]; ok {
		return "[" + agent + "]"
	}
	return "[?]"
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	const max = 160
	if len(s) > max {
		s = s[:max] + "…"
	}
	return s
}

// readAPIError extracts FastAPI's {"detail": ...} message from an error
// response, falling back to the raw body.
func readAPIError(resp *http.Response) string {
	body, err := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
	if err != nil || len(body) == 0 {
		return fmt.Sprintf("HTTP %d", resp.StatusCode)
	}
	var detail struct {
		Detail string `json:"detail"`
	}
	if json.Unmarshal(body, &detail) == nil && detail.Detail != "" {
		return detail.Detail
	}
	return strings.TrimSpace(string(body))
}
