"""
File storage via Vercel Blob.

Vercel's serverless Python functions have a read-only filesystem (except
/tmp, which is wiped between invocations and not shared across them), so a
file saved during the /api/upload request would already be gone by the
time the separate /api/transcribe request runs. Vercel Blob is Vercel's
own object storage and is the natural fit here: cheap, simple REST API,
no separate account needed beyond your existing Vercel project.

Set BLOB_READ_WRITE_TOKEN in your environment - Vercel adds this
automatically once you create a Blob store and connect it to your project
(Storage tab in the Vercel dashboard).

Docs: https://vercel.com/docs/storage/vercel-blob/using-blob-sdk
(This module talks to the same REST API directly via `requests`, since
Vercel's official SDK is JavaScript-first; there's no official Python SDK.)
"""
import os
import uuid

import requests

BLOB_API_BASE = "https://blob.vercel-storage.com"


def _token():
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError(
            "BLOB_READ_WRITE_TOKEN is not set. In the Vercel dashboard, go to "
            "Storage -> Create Database -> Blob, connect it to this project, "
            "and the token will be added to your environment automatically "
            "(redeploy after connecting it)."
        )
    return token


def upload_bytes(data, filename, content_type="application/octet-stream"):
    """
    Uploads raw bytes to Vercel Blob and returns the public URL.
    A random prefix is added to the stored pathname so concurrent uploads
    never collide, even if two people upload a file with the same name.
    """
    pathname = f"{uuid.uuid4().hex}-{filename}"
    try:
        response = requests.put(
            f"{BLOB_API_BASE}/{pathname}",
            data=data,
            headers={
                "Authorization": f"Bearer {_token()}",
                "x-content-type": content_type,
                "x-api-version": "7",
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Upload to Vercel Blob failed (network error): {exc}") from exc

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Upload to Vercel Blob failed ({response.status_code}): {response.text[:300]}")

    body = response.json()
    return body.get("url")


def download_bytes(url):
    """Fetches a previously-uploaded blob's raw bytes back, given its URL."""
    try:
        response = requests.get(url, timeout=25)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Couldn't download audio from storage: {exc}") from exc
    if response.status_code != 200:
        raise RuntimeError(f"Couldn't download audio from storage (HTTP {response.status_code}).")
    return response.content


def delete_blob(url):
    """Best-effort cleanup - failures here should never break the request that calls it."""
    try:
        requests.delete(
            BLOB_API_BASE,
            params={"url": url},
            headers={"Authorization": f"Bearer {_token()}", "x-api-version": "7"},
            timeout=20,
        )
    except (requests.exceptions.RequestException, RuntimeError):
        pass
