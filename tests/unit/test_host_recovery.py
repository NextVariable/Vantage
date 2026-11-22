"""Default STDIO host: recoverable timeout isolation on a real pipe.

These tests drive the actual ``os.pipe`` transport, not a fake stream, so a
late reply is really sitting in the kernel buffer when the next request is
dispatched.
"""
import io
import json
import os
from threading import Thread
from time import monotonic, sleep

from sourceglint.deadline import deadline_scope
from sourceglint.host_stdio import PROTOCOL_VERSION, StdioHostModel
from sourceglint.intelligence.model import ModelStatus


SCHEMA = {
    "type": "object",
    "required": ["marker"],
    "properties": {"marker": {"type": "string"}},
}


class RecordingOutput(io.StringIO):
    """Capture requests as they are written to the host."""

    def __init__(self):
        super().__init__()
        self.requests = []

    def write(self, text):
        written = super().write(text)
        for line in text.splitlines():
            if line.strip():
                self.requests.append(json.loads(line))
        return written


class HostPipe:
    """A real pipe for host -> engine frames plus the engine's request log."""

    def __init__(self):
        read_fd, self._write_fd = os.pipe()
        self.reader = os.fdopen(read_fd, "r", encoding="utf-8", newline="")
        self.output = RecordingOutput()
        self.model = StdioHostModel(input_stream=self.reader, output_stream=self.output)

    def send(self, frame):
        os.write(self._write_fd, (json.dumps(frame) + "\n").encode("utf-8"))

    def call(self, *, task, deadline_seconds=None, payload=None):
        """Run one model call on a worker thread and return its response."""
        box = {}

        def run():
            with deadline_scope(
                None if deadline_seconds is None else monotonic() + deadline_seconds
            ):
                box["response"] = self.model.complete_structured(
                    task=task,
                    payload=payload or {},
                    response_schema=SCHEMA,
                )

        thread = Thread(target=run, daemon=True)
        thread.start()
        return thread, box

    def wait_for_write(self, count, timeout=2.0):
        limit = monotonic() + timeout
        while len(self.output.requests) < count and monotonic() < limit:
            sleep(0.005)
        assert len(self.output.requests) >= count, "engine did not write its request"
        return self.output.requests[count - 1]

    def close(self):
        try:
            os.close(self._write_fd)
        except OSError:
            pass
        self.reader.close()


def reply(task, marker, request_id=None):
    frame = {
        "type": "model_response",
        "task": task,
        "payload": {"marker": marker},
    }
    if request_id is not None:
        frame["request_id"] = request_id
    return frame


def test_correlated_host_recovers_after_a_timeout_and_dispatches_the_fact():
    host = HostPipe()
    try:
        # 1. A successful call teaches the bridge that this host echoes ids.
        thread, box = host.call(task="clustering")
        request = host.wait_for_write(1)
        assert request["protocol"] == PROTOCOL_VERSION
        assert request["request_id"]
        host.send(reply("clustering", "clusters", request["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS

        # 2. Contradiction times out; its late reply stays in the pipe.
        contradiction_thread, contradiction_box = host.call(
            task="contradiction", deadline_seconds=0.05
        )
        contradiction_request = host.wait_for_write(2)
        contradiction_thread.join(2)
        timed_out = contradiction_box["response"]
        assert timed_out.status is ModelStatus.TIMEOUT
        host.send(reply("contradiction", "late", contradiction_request["request_id"]))

        # 3. FACT is dispatched with its own id and gets the matching reply.
        fact_thread, fact_box = host.call(task="fact_synthesis")
        fact_request = host.wait_for_write(3)
        assert fact_request["request_id"] != contradiction_request["request_id"]
        host.send(reply("fact_synthesis", "facts", fact_request["request_id"]))
        fact_thread.join(2)

        fact = fact_box["response"]
        assert fact.status is ModelStatus.SUCCESS
        assert fact.payload == {"marker": "facts"}
        assert len(host.output.requests) == 3
    finally:
        host.close()


def test_legacy_host_still_fails_closed_after_a_timeout():
    host = HostPipe()
    try:
        thread, box = host.call(task="contradiction", deadline_seconds=0.05)
        host.wait_for_write(1)
        thread.join(2)
        assert box["response"].status is ModelStatus.TIMEOUT

        second, second_box = host.call(task="fact_synthesis")
        second.join(2)
        assert second_box["response"].status is ModelStatus.TIMEOUT
        # Fail-closed: the legacy stream is not reused for a new request.
        assert len(host.output.requests) == 1
    finally:
        host.close()


def test_declared_v2_host_recovers_even_on_the_first_timeout():
    os.environ["SOURCEGLINT_HOST_PROTOCOL"] = "v2"
    host = HostPipe()
    try:
        first, first_box = host.call(task="contradiction", deadline_seconds=0.05)
        first_request = host.wait_for_write(1)
        first.join(2)
        assert first_box["response"].status is ModelStatus.TIMEOUT
        host.send(reply("contradiction", "late", first_request["request_id"]))

        fact, fact_box = host.call(task="fact_synthesis")
        fact_request = host.wait_for_write(2)
        host.send(reply("fact_synthesis", "facts", fact_request["request_id"]))
        fact.join(2)
        assert fact_box["response"].status is ModelStatus.SUCCESS
        assert fact_box["response"].payload == {"marker": "facts"}
    finally:
        host.close()
        os.environ.pop("SOURCEGLINT_HOST_PROTOCOL", None)


def test_correlated_host_rejects_a_reply_without_id_after_negotiation():
    host = HostPipe()
    try:
        thread, box = host.call(task="clustering")
        request = host.wait_for_write(1)
        host.send(reply("clustering", "clusters", request["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS

        thread, box = host.call(task="fact_synthesis")
        host.wait_for_write(2)
        host.send(reply("fact_synthesis", "facts"))  # no request id
        thread.join(2)
        assert box["response"].status is ModelStatus.INVALID_OUTPUT
        assert "request_id" in (box["response"].error or "")
    finally:
        host.close()


def test_correlated_host_skips_duplicate_and_cross_request_frames():
    host = HostPipe()
    try:
        thread, box = host.call(task="clustering")
        first = host.wait_for_write(1)
        host.send(reply("clustering", "clusters", first["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS

        # A duplicate of the completed request and a frame for an unknown
        # request arrive before the FACT reply.
        host.send(reply("clustering", "clusters", first["request_id"]))
        host.send(reply("contradiction", "stale", "contradiction-unknown"))

        thread, box = host.call(task="fact_synthesis")
        fact_request = host.wait_for_write(2)
        host.send(reply("fact_synthesis", "facts", fact_request["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS
        assert box["response"].payload == {"marker": "facts"}
    finally:
        host.close()


def test_correlated_wrong_task_is_rejected_not_accepted():
    host = HostPipe()
    try:
        thread, box = host.call(task="clustering")
        request = host.wait_for_write(1)
        host.send(reply("clustering", "clusters", request["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS

        thread, box = host.call(task="fact_synthesis")
        fact_request = host.wait_for_write(2)
        # The id matches, the task does not: this must never be accepted.
        host.send(reply("contradiction", "wrong", fact_request["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.INVALID_OUTPUT
        assert "task" in (box["response"].error or "")
    finally:
        host.close()


def test_late_reply_arriving_together_with_the_next_reply_is_skipped_by_id():
    """Regression: bytes must never be consumed by an abandoned reader.

    The late contradiction frame and the FACT reply are written back to back,
    so a single ``os.read`` sees both. The FACT call must skip the first by
    request id and still receive its own payload.
    """
    host = HostPipe()
    try:
        thread, box = host.call(task="clustering")
        first = host.wait_for_write(1)
        host.send(reply("clustering", "clusters", first["request_id"]))
        thread.join(2)
        assert box["response"].status is ModelStatus.SUCCESS

        contradiction_thread, contradiction_box = host.call(
            task="contradiction", deadline_seconds=0.05
        )
        stale = host.wait_for_write(2)
        contradiction_thread.join(2)
        assert contradiction_box["response"].status is ModelStatus.TIMEOUT

        fact_thread, fact_box = host.call(task="fact_synthesis")
        fact_request = host.wait_for_write(3)
        burst = (json.dumps(reply("contradiction", "late", stale["request_id"])) + "\n"
                 + json.dumps(reply("fact_synthesis", "facts", fact_request["request_id"])) + "\n")
        os.write(host._write_fd, burst.encode("utf-8"))
        fact_thread.join(2)
        assert fact_box["response"].status is ModelStatus.SUCCESS
        assert fact_box["response"].payload == {"marker": "facts"}
    finally:
        host.close()
