"""Browser integration harness ONLY: real HTTP/storage/checks, explicit test executor.

Never imported by production entrypoints. It uses isolated temporary data supplied
by the frontend runner. No Hermes or model call occurs in this process.
"""

import time

import uvicorn
from test_execution import perform_release

from epoch_backend import hermes_bridge
from epoch_backend.app import create_app
from epoch_backend.config import Settings


def browser_executor(request, on_event, cancel_event):
    on_event({"type": "executor.message", "data": {"content": "Browser test executor started."}})
    # Give the browser time to connect to SSE, exercise navigation and cancel.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if cancel_event.wait(0.05):
            return {
                "success": False,
                "final_response": "Browser test executor cancelled.",
                "missing_evidence": ["Test executor: no actual Hermes/model invocation."],
            }
    return perform_release(request, on_event, cancel_event)


if __name__ == "__main__":
    hermes_bridge.detect_installation = lambda: {"available": True, "test_executor": True}
    hermes_bridge.execute = browser_executor
    config = Settings(enable_hermes=True)
    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="warning")
