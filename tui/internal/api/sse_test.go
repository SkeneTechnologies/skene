package api

import (
	"strings"
	"testing"
)

func TestReadEventsParsesFrames(t *testing.T) {
	stream := "data: {\"id\":\"evt_1\",\"type\":\"server.connected\",\"properties\":{}}\n\n" +
		"data: {\"id\":\"evt_2\",\"type\":\"server.heartbeat\",\"properties\":{}}\n\n"

	var got []EventEnvelope
	err := ReadEvents(strings.NewReader(stream), func(e EventEnvelope) bool {
		got = append(got, e)
		return true
	})
	if err != nil {
		t.Fatalf("ReadEvents: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 events, got %d", len(got))
	}
	if got[0].Type != "server.connected" || got[0].ID != "evt_1" {
		t.Fatalf("unexpected first event: %+v", got[0])
	}
	if got[1].Type != "server.heartbeat" {
		t.Fatalf("unexpected second event: %+v", got[1])
	}
}

func TestReadEventsStopsWhenHandlerReturnsFalse(t *testing.T) {
	stream := "data: {\"id\":\"evt_1\",\"type\":\"server.connected\",\"properties\":{}}\n\n" +
		"data: {\"id\":\"evt_2\",\"type\":\"server.heartbeat\",\"properties\":{}}\n\n"

	var count int
	err := ReadEvents(strings.NewReader(stream), func(EventEnvelope) bool {
		count++
		return false
	})
	if err != nil {
		t.Fatalf("ReadEvents: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected handler to run once, ran %d times", count)
	}
}

func TestReadEventsDispatchesFinalFrameWithoutTrailingBlank(t *testing.T) {
	stream := "data: {\"id\":\"evt_1\",\"type\":\"session.idle\",\"properties\":{\"session\":{\"id\":\"ses_1\",\"projectId\":\"prj_1\",\"agent\":\"skene\",\"created\":1,\"updated\":1}}}"

	var got []EventEnvelope
	if err := ReadEvents(strings.NewReader(stream), func(e EventEnvelope) bool {
		got = append(got, e)
		return true
	}); err != nil {
		t.Fatalf("ReadEvents: %v", err)
	}
	if len(got) != 1 || got[0].Type != "session.idle" {
		t.Fatalf("expected trailing frame to dispatch, got %+v", got)
	}
}

func TestDecodeSessionEvent(t *testing.T) {
	envelope := EventEnvelope{
		Type: "session.error",
		Raw: []byte(`{"id":"evt_1","type":"session.error","properties":{` +
			`"session":{"id":"ses_1","projectId":"prj_1","agent":"skene","created":1,"updated":2},` +
			`"error":"boom"}}`),
	}
	decoded, err := envelope.Decode()
	if err != nil {
		t.Fatalf("Decode: %v", err)
	}
	event, ok := decoded.(*SessionError)
	if !ok {
		t.Fatalf("expected *SessionError, got %T", decoded)
	}
	if event.Properties.Error != "boom" || event.Properties.Session.Id != "ses_1" {
		t.Fatalf("unexpected event contents: %+v", event.Properties)
	}
}

func TestDecodeUnknownTypeIsNil(t *testing.T) {
	decoded, err := EventEnvelope{Type: "session.hibernated", Raw: []byte(`{}`)}.Decode()
	if err != nil || decoded != nil {
		t.Fatalf("unknown types should be (nil, nil); got (%v, %v)", decoded, err)
	}
}

func TestDecodePermissionAsked(t *testing.T) {
	envelope := EventEnvelope{
		Type: "permission.asked",
		Raw: []byte(`{"id":"evt_5","type":"permission.asked","properties":{"request":{` +
			`"id":"prm_1","sessionId":"ses_1","tool":"write_db","title":"Write to users?",` +
			`"metadata":{},"status":"pending","created":1,"answered":null}}}`),
	}
	decoded, err := envelope.Decode()
	if err != nil {
		t.Fatalf("Decode: %v", err)
	}
	event, ok := decoded.(*PermissionAsked)
	if !ok {
		t.Fatalf("expected *PermissionAsked, got %T", decoded)
	}
	request := event.Properties.Request
	if request.Id != "prm_1" || request.Tool != "write_db" {
		t.Fatalf("unexpected request contents: %+v", request)
	}
	if request.Status == nil || *request.Status != PermissionRequestStatusPending {
		t.Fatalf("expected pending status, got %v", request.Status)
	}
}

func TestDecodePartCreatedMilestone(t *testing.T) {
	envelope := EventEnvelope{
		Type: "part.created",
		Raw: []byte(`{"id":"evt_9","type":"part.created","properties":{"part":{` +
			`"id":"prt_1","sessionId":"ses_2","messageId":"msg_1","type":"milestone",` +
			`"milestone":{"proposedId":"signup","name":"User signs up","description":"d",` +
			`"evidence":[],"trackedEvent":null,"stageId":null}},"delta":null}}`),
	}
	decoded, err := envelope.Decode()
	if err != nil {
		t.Fatalf("Decode: %v", err)
	}
	event := decoded.(*PartCreated)
	kind, err := event.Properties.Part.Discriminator()
	if err != nil || kind != "milestone" {
		t.Fatalf("expected milestone part, got %q (%v)", kind, err)
	}
	milestone, err := event.Properties.Part.AsMilestonePart()
	if err != nil {
		t.Fatalf("AsMilestonePart: %v", err)
	}
	if milestone.Milestone.Name != "User signs up" || milestone.SessionId != "ses_2" {
		t.Fatalf("unexpected milestone: %+v", milestone)
	}
}
