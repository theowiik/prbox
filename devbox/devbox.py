
import click
import requests

# Define the base URL for your API
API_BASE_URL = "http://localhost:6000"

SAMPLE_AUDIO = "sample.mp3"


@click.group()
def cli():
    """Simple CLI for controlling devices via API."""


@cli.command()
def beep():
    """Send a beep request."""
    send_request("beep")


@cli.command()
def light():
    """Send a light request."""
    send_request("light")


@cli.command()
def play():
    """Upload an audio file to play."""
    files = {"audio": (SAMPLE_AUDIO, open(SAMPLE_AUDIO, "rb"), "audio/mpeg")}

    response = requests.post(f"{API_BASE_URL}/play", files=files)
    click.echo(f"Response from play: {response.status_code} - {response.text}")


@cli.command()
def speak():
    """Send a speak request with a message."""
    message = click.prompt("Enter your message", type=str)
    send_request("speak", data={"message": message})


def send_request(endpoint, data=None):
    """Helper function to send API requests."""
    url = f"{API_BASE_URL}/{endpoint}"
    response = requests.post(url, data=data)
    click.echo(f"Response from {endpoint}: {response.status_code} - {response.text}")


if __name__ == "__main__":
    cli()
