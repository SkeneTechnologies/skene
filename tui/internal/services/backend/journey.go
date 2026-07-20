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
	// as the active phase). Message is a per-agent/per-tool log line.
	Phase   string
	Message string
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
	update := func(phase, message string) {
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

	update(phaseStarting, "Requesting journey analysis...")
	sessionID, err := s.startAnalysis(ctx, directory)
	if err != nil {
		return JourneyResult{Err: err}
	}
	update(phaseStarting, "Session "+sessionID)

	result := JourneyResult{SessionID: sessionID}
	run := newRunTracker(sessionID, update)

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
// session and its subagent children.
type runTracker struct {
	rootID string
	// agents maps session id -> agent name, seeded with the root and grown
	// from session.created events for its children.
	agents map[string]string
	update func(phase, message string)
}

func newRunTracker(rootID string, update func(phase, message string)) *runTracker {
	return &runTracker{
		rootID: rootID,
		agents: map[string]string{},
		update: update,
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
			t.update(phaseAnalyzing, fmt.Sprintf("▶ %s agent started", session.Agent))
		}
	case *api.SessionIdle:
		if event.Properties.Session.Id == t.rootID {
			t.update(phaseFinalizing, "Analysis complete")
			return true, nil
		}
	case *api.SessionError:
		if event.Properties.Session.Id == t.rootID {
			return true, errors.New(event.Properties.Error)
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
			t.update("", fmt.Sprintf("%s ✦ feature: %s", t.tag(feature.SessionId), feature.Feature.Name))
		}
	case "artifact":
		if artifact, err := part.AsArtifactPart(); err == nil && artifact.SessionId == t.rootID {
			// The feature map lands first; only the journey artifact is
			// the run's deliverable.
			if artifact.Title != nil && *artifact.Title == "features.yaml" {
				t.update(phaseFinalizing, "feature map written to "+artifact.Path)
			} else {
				result.ArtifactPath = artifact.Path
				t.update(phaseFinalizing, "journey.yaml written to "+artifact.Path)
			}
		}
	case "text":
		if text, err := part.AsTextPart(); err == nil && text.SessionId == t.rootID {
			if line := firstLine(text.Text); line != "" {
				t.update("", t.tag(text.SessionId)+" "+line)
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
	switch st := state.(type) {
	case api.ToolStateRunning:
		title := tool.Tool
		if st.Title != nil && *st.Title != "" {
			title = *st.Title
		}
		if tool.Tool == "synthesize_journey" {
			t.update(phaseFinalizing, fmt.Sprintf("%s ⚙ %s", tag, title))
		} else {
			t.update("", fmt.Sprintf("%s ⚙ %s", tag, title))
		}
	case api.ToolStateCompleted:
		t.update("", fmt.Sprintf("%s ✓ %s", tag, tool.Tool))
	case api.ToolStateError:
		message := ""
		if st.Error != nil {
			message = *st.Error
		}
		t.update("", fmt.Sprintf("%s ✗ %s: %s", tag, tool.Tool, firstLine(message)))
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
