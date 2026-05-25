"""Tests for SSE decoder and streaming infrastructure."""

from hermes._core._streaming import ServerSentEvent, _SSEDecoder


class TestSSEDecoder:
    """Unit tests for the raw SSE line decoder."""

    def _decode_lines(self, lines: list[str]) -> list[ServerSentEvent]:
        """Feed lines through decoder, collect dispatched events."""
        decoder = _SSEDecoder()
        events = []
        for line in lines:
            sse = decoder.decode(line)
            if sse is not None:
                events.append(sse)
        return events

    def test_basic_data_event(self) -> None:
        events = self._decode_lines(
            [
                'data: {"delta":"Hello"}',
                "",  # blank line triggers dispatch
            ]
        )
        assert len(events) == 1
        assert events[0].data == '{"delta":"Hello"}'
        assert events[0].json() == {"delta": "Hello"}

    def test_event_with_type(self) -> None:
        events = self._decode_lines(
            [
                "event: response.output_text.delta",
                'data: {"delta":"Hi"}',
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].event == "response.output_text.delta"
        assert events[0].data == '{"delta":"Hi"}'

    def test_multiple_events(self) -> None:
        events = self._decode_lines(
            [
                "event: response.created",
                "data: {}",
                "",
                "event: response.output_text.delta",
                'data: {"delta":"Hello"}',
                "",
                "event: response.completed",
                'data: {"usage":{"total_tokens":42}}',
                "",
            ]
        )
        assert len(events) == 3
        assert events[0].event == "response.created"
        assert events[1].event == "response.output_text.delta"
        assert events[2].event == "response.completed"

    def test_done_signal(self) -> None:
        events = self._decode_lines(
            [
                "data: [DONE]",
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].data == "[DONE]"

    def test_event_with_id(self) -> None:
        events = self._decode_lines(
            [
                "id: evt-001",
                "event: message.delta",
                'data: {"delta":"test"}',
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].id == "evt-001"

    def test_event_with_retry(self) -> None:
        events = self._decode_lines(
            [
                "retry: 5000",
                "event: message.delta",
                'data: {"delta":"x"}',
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].retry == 5000

    def test_colon_only_is_comment(self) -> None:
        """Lines starting with ':' are comments and ignored."""
        events = self._decode_lines(
            [
                ": this is a comment",
                "data: real",
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].data == "real"

    def test_empty_data(self) -> None:
        events = self._decode_lines(
            [
                "event: response.created",
                "data:",
                "",
            ]
        )
        assert len(events) == 1
        assert events[0].data == ""

    def test_no_dispatch_without_blank_line(self) -> None:
        """Events are only dispatched on blank line."""
        events = self._decode_lines(
            [
                "event: test",
                "data: partial",
                # no blank line — should NOT dispatch
            ]
        )
        assert len(events) == 0


class TestServerSentEvent:
    """ServerSentEvent data object."""

    def test_json_parsing(self) -> None:
        sse = ServerSentEvent(event="test", data='{"key": "value"}', id=None, retry=None)
        assert sse.json() == {"key": "value"}

    def test_default_values(self) -> None:
        sse = ServerSentEvent(event=None, data="test", id=None, retry=None)
        assert sse.event is None
        assert sse.id is None
        assert sse.retry is None
