"""FastAPI app serving the XYZ Technologies HR Policy Assistant."""
from __future__ import annotations

import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DATA_DIR, STATIC_DIR
from .rag import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.load()  # pick up an existing index if one was built earlier
    yield


app = FastAPI(title="XYZ Technologies HR Assistant", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@app.get("/api/status")
def status():
    return {
        "ready": engine.ready,
        "chunks": len(engine.chunks),
        "document": engine.chunks[0].source if engine.chunks else None,
    }


@app.post("/api/ask")
def ask(req: AskRequest):
    if not engine.ready:
        raise HTTPException(409, "No HR policy document has been indexed yet.")
    try:
        return engine.answer(req.question.strip())
    except Exception as exc:  # surface a readable message instead of a bare 500
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")
    dest = DATA_DIR / file.filename
    DATA_DIR.mkdir(exist_ok=True)
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        count = engine.ingest(dest)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"document": file.filename, "chunks": count}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
