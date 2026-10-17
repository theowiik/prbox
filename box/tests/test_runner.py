"""SourceRunner: on-box sources poll off the event loop and survive failures."""

import asyncio
import threading
import time

import pytest

from box import visuals
from box.display.emulator import EmulatorDisplay
from box.events import Event, Priority, TextSpec, VisualSpec
from box.render.engine import RenderEngine
from box.scheduler import Scheduler
from box.sources.runner import SourceRunner


@pytest.fixture
def scheduler():
    return Scheduler(RenderEngine(EmulatorDisplay(8, 8), 8, 8, fps=60))


class Recording:
    name = "rec"
    interval = 60.0

    def __init__(self):
        self.thread = None

    def poll(self):
        self.thread = threading.current_thread()
        return Event(
            source=self.name, priority=Priority.AMBIENT, scene=TextSpec(text="x")
        )


class Broken:
    name = "broken"
    interval = 60.0

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


class Slow:
    """A feed whose server takes its time."""

    name = "slow"
    interval = 60.0

    def poll(self):
        time.sleep(0.5)


@pytest.mark.anyio
async def test_a_slow_source_does_not_hold_up_the_others(scheduler):
    runner = SourceRunner(scheduler, [Slow(), Recording()])
    await runner.start()
    try:
        await asyncio.sleep(0.1)
        assert scheduler.get_state().source == "rec", "rec waited behind slow"
    finally:
        await runner.stop()


class PintPourer:
    name = "pints"
    interval = 60.0

    def poll(self):
        return Event(source=self.name, scene=VisualSpec(name="beer"))


@pytest.mark.anyio
async def test_a_visual_is_rendered_off_the_loop(scheduler, monkeypatch):
    """Seconds of rendering on a Pi must happen on the worker, not the loop."""
    threads = []
    render = visuals.VISUALS["beer"].render

    def spy(w, h):
        threads.append(threading.current_thread())
        return render(w, h)

    visuals.frames.cache_clear()
    monkeypatch.setitem(visuals.VISUALS, "beer", visuals.Visual(spy, 20.0, loop=False))
    await SourceRunner(scheduler, [PintPourer()]).poll_once()
    visuals.frames.cache_clear()
    assert threads and threads[0] is not threading.current_thread()
    assert scheduler.get_state().scene == "frames"
