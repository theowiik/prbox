from box.render.font import text_width
from box.sources.weather import BUCKET_SECONDS, MockWeather


def test_weather_shape(client):
    data = client.get("/api/sources/weather").json()
    for key in (
        "city",
        "temp",
        "feels_like",
        "condition",
        "humidity",
        "wind_kph",
        "display_text",
        "display_color",
    ):
        assert key in data


#: A timestamp aligned to the start of a bucket, so the whole bucket is ahead.
ALIGNED = 1_700_000_000.0 - (1_700_000_000.0 % BUCKET_SECONDS)


def test_weather_is_stable_within_a_bucket():
    weather = MockWeather("Stockholm")
    assert weather.get(ALIGNED) == weather.get(ALIGNED + BUCKET_SECONDS - 1)


def test_weather_changes_between_buckets():
    weather = MockWeather("Stockholm")
    samples = {
        weather.get(ALIGNED + i * BUCKET_SECONDS).display_text for i in range(20)
    }
    assert len(samples) > 1


def test_cities_differ():
    assert MockWeather("Stockholm").get(ALIGNED) != MockWeather("Oslo").get(ALIGNED)


def test_every_condition_renders_in_the_font():
    """Guards the original bug's neighbours: no weather string may need '?'."""
    weather = MockWeather("Stockholm")
    for i in range(500):
        text = weather.get(1_700_000_000.0 + i * BUCKET_SECONDS).display_text
        assert text_width(text) > 0
        for char in text:
            from box.render.font import _FONT

            assert char.upper() in _FONT, f"{char!r} in {text!r} has no glyph"


def test_push_weather_to_display(client):
    weather = client.get("/api/sources/weather").json()
    client.post(
        "/api/display/text",
        json={"text": weather["display_text"], "color": weather["display_color"]},
    )
    assert client.get("/api/display").json()["text"] == weather["display_text"]
