"""Central configuration for the XYZ Technologies HR Assistant."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
STATIC_DIR = BASE_DIR / "static"
STORAGE_DIR.mkdir(exist_ok=True)

INDEX_PATH = STORAGE_DIR / "index.npz"
CHUNKS_PATH = STORAGE_DIR / "chunks.json"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

EMBED_MODEL = "models/gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"

# Retrieval tuning
CHUNK_SIZE = 1100          # characters per chunk
CHUNK_OVERLAP = 180
TOP_K = 5                  # chunks sent to the model
MIN_SCORE = 0.64          # calibrated: on-topic scored >=0.70, off-topic <=0.58

COMPANY_NAME = "XYZ Technologies Pvt. Ltd."
