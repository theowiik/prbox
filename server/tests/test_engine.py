import asyncio

import pytest

from prbox.controller import DisplayController
from prbox.display.dev import DevDisplay
from prbox.render.engine import RenderEngine, _gamma_lut
from prbox.render.scenes import SolidScene


def make_engine(fps: int = 120) -> tuple[RenderEngine, DevDisplay]:
    display = DevDisplay(8, 4)
    return RenderEngine(display, 8, 4, fps=fps), display


def test_gamma_lut_endpoints():
    lut = _gamma_lut(1.0, 2.2)
    assert lut[0] == 0 and lut[255] == 255
    assert lut[128] < 128, "gamma must darken midtones"


def test_gamma_lut_scales_with_brightness():
    assert _gamma_lut(0.5, 2.2)[255] == 128
    assert max(_gamma_lut(0.0, 2.2)) == 0


def test_brightness_validated():
    engine, _ = make_engine()
    with pytest.raises(ValueError):
        engine.set_brightness(1.5)


@pytest.mark.anyio
async def test_engine_pushes_frames():
    engine, display = make_engine(fps=100)
    engine.set_scene(SolidScene((255, 255, 255)), fade=False)
    await engine.start()
    try:
        await asyncio.sleep(0.1)
        assert any(display.latest_frame()), "engine should have pushed a lit frame"
    finally:
        await engine.stop()


@pytest.mark.anyio
async def test_subscriber_receives_frames_and_unsubscribes():
    engine, _ = make_engine(fps=100)
    await engine.start()
    try:
        queue = engine.subscribe()
        frame = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert len(frame) == 8 * 4 * 3
    finally:
        engine.unsubscribe(queue)
        await engine.stop()
    assert queue not in engine._subscribers


@pytest.mark.anyio
async def test_slow_subscriber_does_not_stall_the_loop():
    engine, display = make_engine(fps=200)
    engine.set_scene(SolidScene((255, 0, 0)), fade=False)
    queue = engine.subscribe()  # Never drained.
    await engine.start()
    try:
        await asyncio.sleep(0.15)
        assert engine._frame_index > 5, "loop must keep running past a full queue"
        assert queue.qsize() <= 1
    finally:
        engine.unsubscribe(queue)
        await engine.stop()


@pytest.mark.anyio
async def test_display_errors_do_not_kill_the_loop():
    class Broken(DevDisplay):
        def push_frame(self, buf):
            raise RuntimeError("hardware fell over")

    engine = RenderEngine(Broken(8, 4), 8, 4, fps=200)
    await engine.start()
    try:
        await asyncio.sleep(0.1)
        assert engine._frame_index > 3
    finally:
        await engine.stop()


def test_controller_reports_scene_and_state():
    engine, _ = make_engine()
    controller = DisplayController(engine)

    assert controller.get_state().scene == "blank"

    controller.show_text("hi", "#ff0000")
    state = controller.get_state()
    assert (state.scene, state.text, state.color) == ("text", "hi", "#FF0000")

    controller.show_rainbow()
    assert controller.get_state().scene == "rainbow"
    assert controller.get_state().text == ""

    controller.set_brightness(0.25)
    assert controller.get_state().brightness == 0.25


def test_controller_rejects_bad_colour():
    engine, _ = make_engine()
    with pytest.raises(ValueError):
        DisplayController(engine).show_text("hi", "not-a-colour")
