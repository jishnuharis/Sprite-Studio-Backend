"""
Talks to Replicate using YOUR server's API token. The desktop app never
sees this token — it only ever talks to this backend.
"""
import io
import time
import requests
from PIL import Image

import config


def generate_image(prompt: str, negative_prompt: str = "", width: int = 512, height: int = 512) -> bytes:
    if not config.REPLICATE_API_TOKEN:
        raise RuntimeError("Server is missing REPLICATE_API_TOKEN — set it in the environment.")

    width = min(width, config.MAX_WIDTH)
    height = min(height, config.MAX_HEIGHT)

    headers = {
        "Authorization": f"Token {config.REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    url = f"https://api.replicate.com/v1/models/{config.REPLICATE_MODEL}/predictions"
    body = {
        "input": {
            "prompt": prompt,
            "go_fast": True,
            "megapixels": "1",
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "png",
        }
    }

    resp = requests.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Replicate error {resp.status_code}: {resp.text[:300]}")

    pred = resp.json()
    pred_id = pred.get("id")
    status = pred.get("status")
    data = pred

    # "Prefer: wait" usually returns the finished result immediately, but
    # poll as a fallback for slower cold starts.
    poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"
    for _ in range(60):
        if status == "succeeded":
            break
        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate generation {status}: {data.get('error')}")
        time.sleep(2)
        r = requests.get(poll_url, headers=headers, timeout=15)
        data = r.json()
        status = data.get("status")
    else:
        raise TimeoutError("Replicate generation timed out")

    output = data.get("output")
    img_url = output[0] if isinstance(output, list) else output
    img_resp = requests.get(img_url, timeout=30)

    # Re-encode through PIL so we always return a clean PNG regardless of
    # what the model handed back.
    img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
