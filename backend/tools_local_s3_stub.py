"""Local S3-compatible endpoint used ONLY while real Cloudflare R2 keys are absent.

This is test infrastructure, not application code: the app always speaks the real S3
API through lib/storage.py, and pointing R2_ENDPOINT_URL at real Cloudflare R2 needs no
code change. It implements the subset of the S3 protocol boto3 uses — including
multipart upload — so the app's large-file path is exercised exactly as R2 would.
"""

import os
import re
import shutil
import uuid

from fastapi import FastAPI, Request, Response

app = FastAPI()
# Persistent location: /tmp is wiped when the pod restarts, which would orphan every
# stored object while the project rows survived. Kept inside /app so test uploads
# outlive restarts, exactly as real R2 objects would.
ROOT = os.environ.get("LOCAL_OBJECT_STORE_DIR", "/app/.local-object-store/data")
PARTS = os.environ.get("LOCAL_OBJECT_STORE_PARTS", "/app/.local-object-store/parts")
_ERR = '<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>{}</Code><Message>{}</Message></Error>'


def _path(bucket: str, key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9/._-]", "_", key)
    target = os.path.join(ROOT, bucket, *safe.split("/"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    return target


def _meta_path(target: str) -> str:
    return target + ".meta"


def _read_content_type(target: str) -> str:
    meta = _meta_path(target)
    if os.path.exists(meta):
        with open(meta) as handle:
            return handle.read().strip() or "application/octet-stream"
    return "application/octet-stream"


def _err(code: str, message: str, status: int) -> Response:
    return Response(_ERR.format(code, message), status_code=status, media_type="application/xml")


# --------------------------------------------------------------------------
# POST: multipart initiate (?uploads) and complete (?uploadId=...)
# --------------------------------------------------------------------------
@app.post("/{bucket}/{key:path}")
async def post_object(bucket: str, key: str, request: Request) -> Response:
    params = request.query_params

    if "uploads" in params:
        upload_id = uuid.uuid4().hex
        os.makedirs(os.path.join(PARTS, upload_id), exist_ok=True)
        with open(os.path.join(PARTS, upload_id, "ct"), "w") as handle:
            handle.write(request.headers.get("content-type", "application/octet-stream"))
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<InitiateMultipartUploadResult>"
            f"<Bucket>{bucket}</Bucket><Key>{key}</Key><UploadId>{upload_id}</UploadId>"
            "</InitiateMultipartUploadResult>"
        )
        return Response(body, status_code=200, media_type="application/xml")

    upload_id = params.get("uploadId")
    if upload_id:
        part_dir = os.path.join(PARTS, upload_id)
        if not os.path.isdir(part_dir):
            return _err("NoSuchUpload", "The specified upload does not exist.", 404)
        xml = (await request.body()).decode("utf-8", "replace")
        numbers = [int(n) for n in re.findall(r"<PartNumber>(\d+)</PartNumber>", xml)]
        if not numbers:
            numbers = sorted(
                int(name.split("-")[1])
                for name in os.listdir(part_dir)
                if name.startswith("part-")
            )
        target = _path(bucket, key)
        with open(target, "wb") as out:
            for number in sorted(numbers):
                chunk_path = os.path.join(part_dir, f"part-{number}")
                if not os.path.exists(chunk_path):
                    return _err("InvalidPart", f"part {number} missing", 400)
                with open(chunk_path, "rb") as chunk:
                    shutil.copyfileobj(chunk, out)
        ct_file = os.path.join(part_dir, "ct")
        content_type = "application/octet-stream"
        if os.path.exists(ct_file):
            with open(ct_file) as handle:
                content_type = handle.read().strip() or content_type
        with open(_meta_path(target), "w") as handle:
            handle.write(content_type)
        shutil.rmtree(part_dir, ignore_errors=True)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<CompleteMultipartUploadResult>"
            f"<Bucket>{bucket}</Bucket><Key>{key}</Key><ETag>&quot;stub-etag&quot;</ETag>"
            "</CompleteMultipartUploadResult>"
        )
        return Response(body, status_code=200, media_type="application/xml")

    return _err("InvalidRequest", "unsupported POST", 400)


# --------------------------------------------------------------------------
# PUT: whole object, or one multipart part
# --------------------------------------------------------------------------
@app.put("/{bucket}/{key:path}")
async def put_object(bucket: str, key: str, request: Request) -> Response:
    params = request.query_params
    upload_id = params.get("uploadId")
    part_number = params.get("partNumber")
    data = await request.body()

    if upload_id and part_number:
        part_dir = os.path.join(PARTS, upload_id)
        if not os.path.isdir(part_dir):
            return _err("NoSuchUpload", "The specified upload does not exist.", 404)
        with open(os.path.join(part_dir, f"part-{int(part_number)}"), "wb") as handle:
            handle.write(data)
        return Response(status_code=200, headers={"ETag": f'"part-{part_number}"'})

    target = _path(bucket, key)
    with open(target, "wb") as handle:
        handle.write(data)
    with open(_meta_path(target), "w") as handle:
        handle.write(request.headers.get("content-type", "application/octet-stream"))
    return Response(status_code=200, headers={"ETag": '"stub-etag"'})


@app.head("/{bucket}/{key:path}")
async def head_object(bucket: str, key: str) -> Response:
    target = _path(bucket, key)
    if not os.path.exists(target):
        return Response(status_code=404, media_type="application/xml")
    return Response(
        status_code=200,
        headers={
            "content-length": str(os.path.getsize(target)),
            "content-type": _read_content_type(target),
            "etag": '"stub-etag"',
            "accept-ranges": "bytes",
        },
    )


@app.get("/{bucket}/{key:path}")
async def get_object(bucket: str, key: str, request: Request) -> Response:
    target = _path(bucket, key)
    if not os.path.exists(target):
        return _err("NoSuchKey", "The specified key does not exist.", 404)

    size = os.path.getsize(target)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", request.headers.get("range", "").strip())
    start, end, status = 0, size - 1, 200
    headers = {"accept-ranges": "bytes", "etag": '"stub-etag"'}
    if match and match.group(1):
        start = int(match.group(1))
        end = size - 1 if not match.group(2) else min(int(match.group(2)), size - 1)
        status = 206
        headers["content-range"] = f"bytes {start}-{end}/{size}"
    elif match and match.group(2):
        start = max(0, size - int(match.group(2)))
        status = 206
        headers["content-range"] = f"bytes {start}-{end}/{size}"

    with open(target, "rb") as handle:
        handle.seek(start)
        payload = handle.read(end - start + 1)
    headers["content-length"] = str(len(payload))
    return Response(content=payload, status_code=status, media_type=_read_content_type(target), headers=headers)


@app.delete("/{bucket}/{key:path}")
async def delete_object(bucket: str, key: str, request: Request) -> Response:
    upload_id = request.query_params.get("uploadId")
    if upload_id:  # AbortMultipartUpload
        shutil.rmtree(os.path.join(PARTS, upload_id), ignore_errors=True)
        return Response(status_code=204)
    target = _path(bucket, key)
    for path in (target, _meta_path(target)):
        if os.path.exists(path):
            os.unlink(path)
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="warning")
