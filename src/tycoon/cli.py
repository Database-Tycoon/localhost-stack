import click
from tycoon import __version__

@click.group()
def cli():
    pass

@cli.command()
def check_updates():
    """Check for updates to the tycoon package."""
    import requests
    from packaging.version import parse as parse_version

    try:
        response = requests.get("https://pypi.org/pypi/tycoon/json")
        response.raise_for_status()
        latest_version = parse_version(response.json()["info"]["version"])
        current_version = parse_version(__version__)
        
        if latest_version > current_version:
            print(f"Update available: {latest_version} (you have {current_version})")
        else:
            print(f"No updates available. You have version {current_version}")
    except requests.RequestException as e:
        print(f"Failed to check for updates: {e}")
    except KeyError as e:
        print(f"Unexpected response format: missing key {e}")
