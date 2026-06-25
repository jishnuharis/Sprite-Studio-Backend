"""
Calls Replicate's FLUX Schnell model using the server's own REPLICATE_API_TOKEN.
This token never leaves the server -- the desktop app never sees it.

Uses Replicate's plain REST API (not the `replicate` Python package) to keep
the server's dependency list small.
"""
import base64
import time

import requests

import config

_BASE = "https://api.replicate.com/v1"


class ReplicateError(Exception):
    pass


def _headers():
    if not config.REPLICATE_API_TOKEN:
        raise ReplicateError(
            "REPLICATE_API_TOKEN is not set on the server. "
            "Add it in your Railway service's environment variables."
        )
    return {
        "Authorization": f"Bearer {config.REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }


def generate_image_bytes(prompt: str, negative_prompt: str = "",
                          width: int = 512, height: int = 512) -> bytes:
    """Runs FLUX Schnell on Replicate and returns the resulting PNG image
    bytes. Raises ReplicateError on failure."""

    owner, name = config.REPLICATE_MODEL.split("/", 1)
    url = f"{_BASE}/models/{owner}/{name}/predictions"

    payload = {
        "input": {
            "prompt": prompt,
            "go_fast": True,
            "megapixels": "1",
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "png",
        }
    }
    if negative_prompt:
        payload["input"]["negative_prompt"] = negative_prompt

    try:
        resp = requests.post(
            url, json=payload, headers={**_headers(), "Prefer": "wait=30"}, timeout=60,
        )
    except requests.exceptions.RequestException as e:
        raise ReplicateError(f"Could not reach Replicate: {e}")

    if resp.status_code not in (200, 201):
        raise ReplicateError(f"Replicate request failed ({resp.status_code}): {resp.text[:300]}")

    prediction = resp.json()
    prediction = _poll_until_done(prediction)

    if prediction.get("status") != "succeeded":
        err = prediction.get("error") or "Generation failed with no error message"
        raise ReplicateError(str(err))

    output = prediction.get("output")
    image_url = _first_url(output)
    if not image_url:
        raise ReplicateError("Replicate returned no image output")

    img_resp = requests.get(image_url, timeout=60)
    if img_resp.status_code != 200:
        raise ReplicateError(f"Could not download generated image ({img_resp.status_code})")
    return img_resp.content


def _first_url(output):
    """Replicate's `output` field is sometimes a single URL string, sometimes
    a list of URLs, depending on the model."""
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        return output[0]
    return None


def _poll_until_done(prediction, timeout_s=120, interval_s=1.5):
    get_url = prediction.get("urls", {}).get("get")
    start = time.time()
    while prediction.get("status") not in ("succeeded", "failed", "canceled"):
        if not get_url or time.time() - start > timeout_s:
            raise ReplicateError("Timed out waiting for image generation")
        time.sleep(interval_s)
        resp = requests.get(get_url, headers=_headers(), timeout=30)
        if resp.status_code != 200:
            raise ReplicateError(f"Could not check generation status ({resp.status_code})")
        prediction = resp.json()
    return prediction


def generate_image_base64(prompt: str, negative_prompt: str = "",
                           width: int = 512, height: int = 512) -> str:
    img_bytes = generate_image_bytes(prompt, negative_prompt, width, height)
    return base64.b64encode(img_bytes).decode("ascii")
