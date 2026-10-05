"""Scheduler behaviour: priorities, coalescing, the ambient rotation."""

import time

import pytest

from box.display.dev import DevDisplay
from box.events import Event, Priority, SolidSpec, TextSpec
from box.render.engine import RenderEngine
from box.render.scenes import SolidScene
from box.scheduler import MIN_RESUME, Scheduler


@pytest.fixture
def scheduler():
    engine = RenderEngine(DevDisplay(8, 8), 8, 8, fps=60)
    return Scheduler(engine)


def ev(source="test", priority=Priority.NORMAL, text="hi", duration=None):
    return Event(
        source=source,
        priority=priority,
        duration=duration,
        scene=TextSpec(text=text),
    )


def test_ambient_shows_when_nothing_queued(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=5)
    scheduler.tick()
    assert scheduler.get_state().scene == "solid"
    assert scheduler.get_state().source == "box"


def test_normal_event_takes_the_panel_then_returns_to_ambient(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=99)
    scheduler.submit(ev(duration=0.05))
    assert scheduler.get_state().scene == "text"

    time.sleep(0.08)
    scheduler.tick()
    assert scheduler.get_state().scene == "solid", "must fall back to ambient"


def test_events_queue_in_order(scheduler):
    scheduler.submit(ev(source="a", text="first", duration=0.05))
    scheduler.submit(ev(source="b", text="second", duration=5))
    assert scheduler.queue_depth == 1
    assert scheduler.get_state().text == "first"

    time.sleep(0.08)
    scheduler.tick()
    assert scheduler.get_state().text == "second"
    assert scheduler.queue_depth == 0


def test_burst_from_one_source_is_coalesced(scheduler):
    """Ten pings from Discord must not buy ten slots of panel time."""
    scheduler.submit(ev(source="holding", duration=30))
    for i in range(10):
        scheduler.submit(ev(source="discord", text=f"msg {i}"))

    assert scheduler.queue_depth == 1, "only the newest from a source survives"
    assert scheduler._queue[0].event.scene.text == "msg 9"


def test_different_sources_all_queue(scheduler):
    scheduler.submit(ev(source="holding", duration=30))
    for name in ("discord", "github", "email"):
        scheduler.submit(ev(source=name))
    assert scheduler.queue_depth == 3


def test_alert_preempts_immediately(scheduler):
    scheduler.submit(ev(source="slow", text="background", duration=30))
    assert scheduler.get_state().text == "background"

    scheduler.submit(ev(source="fire", priority=Priority.ALERT, text="alarm"))
    assert scheduler.get_state().text == "alarm"
    assert scheduler.get_state().source == "fire"


def test_preempted_event_resumes_with_its_remaining_time(scheduler):
    scheduler.submit(ev(source="slow", text="background", duration=30))
    scheduler.submit(
        ev(source="fire", priority=Priority.ALERT, text="alarm", duration=0.05)
    )
    assert scheduler.queue_depth == 1, "interrupted event should be requeued"

    time.sleep(0.08)
    scheduler.tick()
    assert scheduler.get_state().text == "background"
    assert scheduler._current.duration < 30, "resumes with what was left, not a reset"


def test_alert_waits_for_an_alert_already_on_the_panel(scheduler):
    """Two pings at once must not shove each other off before either reads."""
    scheduler.submit(
        ev(source="discord", priority=Priority.ALERT, text="first", duration=5)
    )
    scheduler.submit(
        ev(source="slack", priority=Priority.ALERT, text="second", duration=5)
    )

    assert scheduler.get_state().text == "first", "the first alert keeps the panel"
    assert scheduler.queue_depth == 1


def test_a_waiting_alert_shows_before_queued_normals(scheduler):
    scheduler.submit(
        ev(source="a", priority=Priority.ALERT, text="alert-1", duration=0.05)
    )
    scheduler.submit(ev(source="b", text="ordinary", duration=5))
    scheduler.submit(
        ev(source="c", priority=Priority.ALERT, text="alert-2", duration=5)
    )

    time.sleep(0.08)
    scheduler.tick()
    assert scheduler.get_state().text == "alert-2", "alerts jump ahead of normals"


def test_alarm_interrupts_an_alert(scheduler):
    scheduler.submit(
        ev(source="discord", priority=Priority.ALERT, text="ping", duration=30)
    )
    scheduler.submit(
        ev(source="smoke", priority=Priority.ALARM, text="FIRE", duration=5)
    )

    assert scheduler.get_state().text == "FIRE"
    assert scheduler.get_state().priority == "alarm"
    assert scheduler.queue_depth == 1, "the interrupted alert is put back"


def test_the_alert_an_alarm_interrupted_resumes(scheduler):
    scheduler.submit(
        ev(source="discord", priority=Priority.ALERT, text="ping", duration=30)
    )
    time.sleep(0.05)
    scheduler.submit(
        ev(source="smoke", priority=Priority.ALARM, text="FIRE", duration=0.05)
    )

    time.sleep(0.08)
    scheduler.tick()
    state = scheduler.get_state()
    assert state.text == "ping"
    assert state.priority == "alert"


def test_an_alarm_interrupts_another_alarm(scheduler):
    """'Always instant' has no exception for other alarms."""
    scheduler.submit(
        ev(source="clock", priority=Priority.ALARM, text="WAKE", duration=30)
    )
    scheduler.submit(
        ev(source="smoke", priority=Priority.ALARM, text="FIRE", duration=30)
    )
    assert scheduler.get_state().text == "FIRE"


def test_an_interrupted_event_resumes_ahead_of_waiting_alerts(scheduler):
    """It was halfway through being read, so it gets its remaining time first."""
    scheduler.submit(
        ev(source="discord", priority=Priority.ALERT, text="ping", duration=30)
    )
    scheduler.submit(
        ev(source="slack", priority=Priority.ALERT, text="waiting", duration=5)
    )
    scheduler.submit(
        ev(source="smoke", priority=Priority.ALARM, text="FIRE", duration=0.05)
    )

    time.sleep(0.08)
    scheduler.tick()
    assert scheduler.get_state().text == "ping"


def test_ambient_never_wins_the_panel_from_an_alert(scheduler):
    scheduler.submit(
        ev(source="discord", priority=Priority.ALERT, text="ping", duration=30)
    )
    scheduler.submit(ev(source="weather", priority=Priority.AMBIENT, text="12C"))
    assert scheduler.get_state().text == "ping"


def test_nearly_finished_event_is_not_resumed(scheduler):
    scheduler.submit(ev(source="slow", duration=MIN_RESUME / 2))
    scheduler.submit(ev(source="fire", priority=Priority.ALERT))
    assert scheduler.queue_depth == 0, "a sliver of an event is not worth resuming"


def test_ambient_sources_share_a_rotation(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=0.05)
    scheduler.submit(
        Event(source="weather", priority=Priority.AMBIENT, scene=TextSpec(text="5C"))
    )
    assert set(scheduler.get_state().ambient) == {"box", "weather"}


def test_ambient_rotation_advances(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=0.04)
    scheduler.submit(
        Event(
            source="weather",
            priority=Priority.AMBIENT,
            duration=0.04,
            scene=TextSpec(text="5C"),
        )
    )
    seen = set()
    for _ in range(40):
        scheduler.tick()
        seen.add(scheduler.get_state().source)
        time.sleep(0.01)
    assert seen == {"box", "weather"}, "rotation must cycle every card"


def test_ambient_refresh_replaces_in_place(scheduler):
    """A source polling on a timer updates its card, never adds another."""
    for temp in ("5C", "6C", "7C"):
        scheduler.submit(
            Event(
                source="weather", priority=Priority.AMBIENT, scene=TextSpec(text=temp)
            )
        )
    assert scheduler.get_state().ambient == ["weather"]


def test_ambient_never_interrupts_a_normal_event(scheduler):
    scheduler.submit(ev(source="msg", text="important", duration=30))
    scheduler.submit(
        Event(source="weather", priority=Priority.AMBIENT, scene=TextSpec(text="5C"))
    )
    assert scheduler.get_state().text == "important"


def test_focus_jumps_the_rotation(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=99)
    scheduler.submit(
        Event(source="weather", priority=Priority.AMBIENT, scene=TextSpec(text="5C")),
        focus=False,
    )
    assert scheduler.get_state().source == "box", "a timer refresh must not hijack"

    scheduler.submit(
        Event(source="weather", priority=Priority.AMBIENT, scene=TextSpec(text="6C")),
        focus=True,
    )
    assert scheduler.get_state().source == "weather"


def test_clear_drops_the_queue(scheduler):
    scheduler.set_ambient_scene("box", SolidScene((20, 40, 80)), dwell=99)
    scheduler.submit(ev(source="a", duration=30))
    scheduler.submit(ev(source="b", duration=30))
    scheduler.clear()
    assert scheduler.queue_depth == 0
    assert scheduler.get_state().scene == "solid"


def test_explicit_colour_is_reported_not_the_fallback(scheduler):
    scheduler.submit(
        Event(source="discord", scene=TextSpec(text="hi", color="#ABCDEF"))
    )
    assert scheduler.get_state().color == "#ABCDEF"


def test_source_styling_applies_when_no_colour_given(scheduler):
    from box.events import SOURCE_COLORS

    scheduler.submit(Event(source="discord", scene=TextSpec(text="hi")))
    assert scheduler.get_state().color == SOURCE_COLORS["discord"]


def test_solid_colour_is_reported(scheduler):
    scheduler.submit(Event(source="x", scene=SolidSpec(color="#123456")))
    assert scheduler.get_state().color == "#123456"


def test_scene_kinds_all_build(scheduler):
    for spec in (TextSpec(text="a"), SolidSpec(color="#fff")):
        scheduler.submit(Event(source="x", scene=spec, duration=30))
        scheduler.clear()
