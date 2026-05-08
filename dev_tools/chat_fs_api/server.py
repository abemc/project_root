from pathlib import Path
import os
import subprocess
import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


APP = FastAPI(title="Chat FS API")
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# workspace root: use current working directory (start server from workspace root)
WORKSPACE_ROOT = Path.cwd().resolve()


def safe_path(rel_path: str) -> Path:
    p = (WORKSPACE_ROOT / rel_path).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT)):
        raise HTTPException(status_code=400, detail="Path is outside workspace")
    return p


@APP.get("/api/list")
def list_dir(path: str = Query(".")):
    p = safe_path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Not found")
    if p.is_file():
        raise HTTPException(status_code=400, detail="Path is a file")

    entries = []
    for child in sorted(p.iterdir(), key=lambda x: x.name):
        try:
            stat = child.stat()
            entries.append({
                "name": child.name,
                "path": str(child.relative_to(WORKSPACE_ROOT)),
                "is_dir": child.is_dir(),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            })
        except Exception:
            continue
    return {"root": str(WORKSPACE_ROOT), "entries": entries}


@APP.get("/api/read")
def read_file(path: str = Query(...)):
    p = safe_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    size = p.stat().st_size
    if size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large to read (>2MB)")
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File appears binary")
    return {"path": str(p.relative_to(WORKSPACE_ROOT)), "text": text}


class PatchRequest(BaseModel):
    patch: str
    branch: str | None = None


@APP.post("/api/patch/check")
def patch_check(req: PatchRequest):
    if not req.patch:
        raise HTTPException(status_code=400, detail="Empty patch")
    proc = subprocess.run([
        "git",
        "apply",
        "--check",
        "--whitespace=nowarn",
        "-",
    ], input=req.patch.encode(), cwd=str(WORKSPACE_ROOT), capture_output=True)
    ok = proc.returncode == 0
    return {"ok": ok, "stdout": proc.stdout.decode(errors="ignore"), "stderr": proc.stderr.decode(errors="ignore")}


@APP.post("/api/patch/apply")
def patch_apply(req: PatchRequest):
    if not req.patch:
        raise HTTPException(status_code=400, detail="Empty patch")

    ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    branch = req.branch or f"chat-patch-{ts}"

    # create new branch
    proc = subprocess.run(["git", "checkout", "-b", branch], cwd=str(WORKSPACE_ROOT), capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {proc.stderr.decode()}")

    # apply patch
    proc = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], input=req.patch.encode(), cwd=str(WORKSPACE_ROOT), capture_output=True)
    if proc.returncode != 0:
        # try to clean up by switching back to main branch
        subprocess.run(["git", "checkout", "-"], cwd=str(WORKSPACE_ROOT))
        raise HTTPException(status_code=500, detail=f"git apply failed: {proc.stderr.decode()}" )

    # add and commit
    proc = subprocess.run(["git", "add", "-A"], cwd=str(WORKSPACE_ROOT), capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git add failed: {proc.stderr.decode()}")
    proc = subprocess.run(["git", "commit", "-m", "Apply patch via chat tool"], cwd=str(WORKSPACE_ROOT), capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git commit failed: {proc.stderr.decode()}")

    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(WORKSPACE_ROOT), capture_output=True)
    commit = proc.stdout.decode().strip()
    return {"branch": branch, "commit": commit}


@APP.get("/api/health")
def health():
    return {"status": "ok", "workspace": str(WORKSPACE_ROOT)}
