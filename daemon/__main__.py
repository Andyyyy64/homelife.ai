"""Entry point for `python -m life`."""

from dotenv import load_dotenv
load_dotenv()

from daemon.cli import cli

if __name__ == "__main__":
    cli()
