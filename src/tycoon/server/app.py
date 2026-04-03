from fastapi import FastAPI, Response
from tycoon import __version__

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Welcome to Tycoon", "version": __version__}

@app.get("/check-updates")
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
            return {"update_available": True, "current_version": str(current_version), "latest_version": str(latest_version)}
        else:
            return {"update_available": False, "current_version": str(current_version), "latest_version": str(latest_version)}
    except requests.RequestException as e:
        return {"error": f"Failed to check for updates: {e}"}
    except KeyError as e:
        return {"error": f"Unexpected response format: missing key {e}"}
