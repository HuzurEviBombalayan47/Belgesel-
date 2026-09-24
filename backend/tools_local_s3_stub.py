"""Test-only S3-compatible stub for verifying the R2 storage code path locally.
NOT part of the app — the shipped storage layer is Cloudflare R2; this stub simply
speaks the same S3 protocol so boto3 can be exercised end-to-end without keys.

Run: python /tmp/s3stub.py  (serves on :9000, files under /tmp/s3stub-data)
"""

import os
import re

from fastapi import FastAPI, Request, Response

app = FastAPI()
ROOT = "/tmp/s3stub-data"
_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>{}</Code><Message>{}</Message></Error>'


def _path(bucket: str, key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9/._-]", "_", key)
    target = os.path.join(ROOT, bucket, *safe.split("/"))
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    return target


def _error(code: str, message: str, status: int) -> Response:
    return Response(_XML.format(code, message), status_code=status, media_type="application/xml")


@app.api_route("/{bucket}/{key:path}", methods=["PUT", "POST"])
async def put_object(bucket: str, key: str, request: Request) -> Response:
    if not key or key.endswith("/"):
        return Response(status_code=200, media_type="application/xml")  # multipart initiation etc.
    data = await request.body()
    target = _path(bucket, key)
    with open(target, "wb") as handle:
        handle.write(data)
    with open(target + ".meta", "w") as handle:  # remember the content-type for HEAD/GET
        handle.write(request.headers.get("content-type", "application/octet-stream"))
    return Response(status_code=200, headers={"ETag": '"stub-etag"'})


@app.api_route("/{bucket}/{key:path}", methods=["HEAD"])
async def head_object(bucket: str, key: str) -> Response:
    target = _path(bucket, key)
    if not os.path.exists(target):
        return Response(status_code=404, media_type="application/xml")
    content_type = "application/octet-stream"
    if os.path.exists(target + ".meta"):
        with open(target + ".meta") as handle:
            content_type = handle.read().strip() or content_type
    return Response(
        status_code=200,
        headers={"content-length": str(os.path.getsize(target)), "content-type": content_type, "etag": '"stub-etag"'},
    )


@app.api_route("/{bucket}/{key:path}", methods=["GET"])
async def get_object(bucket: str, key: str, request: Request) -> Response:
    target = _path(bucket, key)
    if not os.path.exists(target):
        return _error("NoSuchKey", "The specified key does not exist.", 404)

    size = os.path.getsize(target)
    range_header = request.headers.get("range", "")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
    start, end = 0, size - 1
    status = 200
    headers = {"accept-ranges": "bytes", "etag": '"stub-etag"'}
    if match and match.group(1):
        start = int(match.group(1))
        end = size - 1 if not match.group(2) else min(int(match.group(2)), size - 1)
        status = 206
        headers["content-range"] = f"bytes {start}-{end}/{size}"
    elif match and match.group(2):
        start = size - int(match.group(2))
        status = 206
        headers["content-range"] = f"bytes {start}-{end}/{size}"

    with open(target, "rb") as handle:
        handle.seek(start)
        payload = handle.read(end - start + 1)
    headers["content-length"] = str(len(payload))
    return Response(content=payload, status_code=status, media_type="application/octet-stream", headers=headers)


@app.api_route("/{bucket}/{key:path}", methods=["DELETE"])
async def delete_object(bucket: str, key: str) -> Response:
    target = _path(bucket, key)
    if os.path.exists(target):
        os.unlink(target)
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="warning")
