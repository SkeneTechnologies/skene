package api

// Hand-written reader for the server's GET /event stream. The generated
// client covers the request/response types; SSE framing is the one part of
// the contract oapi-codegen cannot express, so it lives here.
//
// Wire format (see docs/design/backend-server.md §"SSE framing"): frames are
// `data: <event JSON>\n\n` only — no `event:` or `id:` lines. Event JSON is
// `{id, type, properties}`.

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

// EventEnvelope is one decoded SSE frame: the event's envelope fields plus
// the raw JSON for typed decoding via Decode.
type EventEnvelope struct {
	ID   string
	Type string
	Raw  []byte
}

// Decode unmarshals the envelope into the concrete generated event struct
// (*SessionCreated, *PartUpdated, ...). Unknown event types return (nil, nil)
// so clients stay forward-compatible with new server events.
func (e EventEnvelope) Decode() (interface{}, error) {
	var target interface{}
	switch e.Type {
	case "server.connected":
		target = &ServerConnected{}
	case "server.heartbeat":
		target = &ServerHeartbeat{}
	case "session.created":
		target = &SessionCreated{}
	case "session.updated":
		target = &SessionUpdated{}
	case "session.idle":
		target = &SessionIdle{}
	case "session.error":
		target = &SessionError{}
	case "message.created":
		target = &MessageCreated{}
	case "message.updated":
		target = &MessageUpdated{}
	case "part.created":
		target = &PartCreated{}
	case "part.updated":
		target = &PartUpdated{}
	default:
		return nil, nil
	}
	if err := json.Unmarshal(e.Raw, target); err != nil {
		return nil, fmt.Errorf("decode %s event: %w", e.Type, err)
	}
	return target, nil
}

// maxEventSize bounds a single SSE frame; completed tool outputs can be
// large, but anything past this indicates a broken stream.
const maxEventSize = 16 * 1024 * 1024

// ReadEvents reads SSE frames from r and calls handle for each event until
// r is exhausted or handle returns false. It returns nil on clean EOF and on
// handle-requested stops; the caller ends the stream by closing the response
// body (e.g. via context cancellation), which surfaces here as an error that
// is also reported as nil when the frame boundary was clean.
func ReadEvents(r io.Reader, handle func(EventEnvelope) bool) error {
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 64*1024), maxEventSize)

	var data strings.Builder
	dispatch := func() bool {
		if data.Len() == 0 {
			return true
		}
		payload := []byte(data.String())
		data.Reset()
		var envelope struct {
			ID   string `json:"id"`
			Type string `json:"type"`
		}
		if err := json.Unmarshal(payload, &envelope); err != nil {
			// Not an event we understand; skip the frame.
			return true
		}
		return handle(EventEnvelope{ID: envelope.ID, Type: envelope.Type, Raw: payload})
	}

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			if !dispatch() {
				return nil
			}
			continue
		}
		if rest, ok := bytes.CutPrefix(line, []byte("data:")); ok {
			if data.Len() > 0 {
				data.WriteByte('\n')
			}
			data.Write(bytes.TrimPrefix(rest, []byte(" ")))
		}
		// Other SSE field lines (event:, id:, retry:, comments) are not
		// produced by the server; ignore them if they ever appear.
	}
	if err := scanner.Err(); err != nil {
		if data.Len() == 0 {
			// Stream torn down between frames (normal shutdown path when
			// the caller closes the body).
			return nil
		}
		return err
	}
	dispatch()
	return nil
}
