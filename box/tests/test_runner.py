"""SourceRunner: on-box sources poll off the event loop and survive failures."""

import threading

import pytest

from box.display.dev import DevDisplay
from box.events import Event, Priority, TextSpec
from box.render.engine import RenderEngine
from box.scheduler import Scheduler
from box.sources.runner import SourceRunner


@pytest.fixture
def scheduler():
    return Scheduler(RenderEngine(DevDisplay(8, 8), 8, 8, fps=60))


class Recording:
    name = "rec"

    def __init__(self):
        self.thread = None

    def poll(self):
        self.thread = threading.current_thread()
        return Event(
            source=self.name, priority=Priority.AMBIENT, scene=TextSpec(text="x")
        )


class Broken:
    name = "broken"

    def poll(self):
        raise RuntimeError("api down")


@pytest.mark.anyio
async def test_poll_runs_off_the_event_loop(scheduler):
    """A blocking HTTP call in poll() must not freeze the render loop."""
    source = Recording()
    await SourceRunner(scheduler, [source]).poll_once()
    assert source.thread is not threading.current_thread()
    assert scheduler.get_state().source == "rec"


@pytest.mark.anyio
async def test_one_broken_source_does_not_stop_the_rest(scheduler):
    await SourceRunner(scheduler, [Broken(), Recording()]).poll_once()
    assert scheduler.get_state().ambient == ["rec"]
