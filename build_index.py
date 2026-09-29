"""One-time indexer: python build_index.py [path/to/policy.pdf]"""
import sys
from pathlib import Path

from app.config import DATA_DIR
from app.rag import engine

pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "XYZ_Technologies_HR_Policy.pdf"
if not pdf.exists():
    sys.exit(f"PDF not found: {pdf}")

print(f"Indexing {pdf.name} ...")
try:
    count = engine.ingest(pdf)
except RuntimeError as exc:
    sys.exit(f"\n{exc}")
print(f"Done. {count} chunks embedded and saved to storage/.")
