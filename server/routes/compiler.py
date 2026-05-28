import os
import json
import subprocess
import tempfile
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

ARDUINO_CLI = os.getenv("ARDUINO_CLI_PATH", "arduino-cli")


def _find_cli():
    path = shutil.which(ARDUINO_CLI)
    if not path:
        raise HTTPException(
            status_code=503,
            detail=f"arduino-cli not found. Set ARDUINO_CLI_PATH in .env or install from https://arduino.github.io/arduino-cli/",
        )
    return path


class CompileRequest(BaseModel):
    code: str
    fqbn: str = "arduino:avr:uno"


class UploadRequest(BaseModel):
    code: str
    fqbn: str = "arduino:avr:uno"
    port: str


def _write_sketch(tmpdir: str, code: str) -> str:
    sketch_dir = os.path.join(tmpdir, "sketch")
    os.makedirs(sketch_dir)
    with open(os.path.join(sketch_dir, "sketch.ino"), "w") as f:
        f.write(code)
    return sketch_dir


@router.get("/api/ports")
async def list_ports():
    cli = _find_cli()
    result = subprocess.run(
        [cli, "board", "list", "--format", "json"],
        capture_output=True, text=True, timeout=10,
    )
    try:
        data = json.loads(result.stdout)
        ports = [
            {"port": item["port"]["address"]}
            for item in (data.get("detected_ports") or [])
        ]
    except Exception:
        ports = []
    return {"ports": ports}


@router.post("/api/compile")
async def compile_sketch(body: CompileRequest):
    cli = _find_cli()
    tmpdir = tempfile.mkdtemp()
    try:
        sketch_dir = _write_sketch(tmpdir, body.code)
        result = subprocess.run(
            [cli, "compile", "--fqbn", body.fqbn, sketch_dir],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/api/upload")
async def upload_sketch(body: UploadRequest):
    cli = _find_cli()
    tmpdir = tempfile.mkdtemp()
    try:
        sketch_dir = _write_sketch(tmpdir, body.code)
        compile_run = subprocess.run(
            [cli, "compile", "--fqbn", body.fqbn, sketch_dir],
            capture_output=True, text=True, timeout=60,
        )
        if compile_run.returncode != 0:
            return {"success": False, "stdout": compile_run.stdout, "stderr": compile_run.stderr}
        upload_run = subprocess.run(
            [cli, "upload", "-p", body.port, "--fqbn", body.fqbn, sketch_dir],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "success": upload_run.returncode == 0,
            "stdout": upload_run.stdout,
            "stderr": upload_run.stderr,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
