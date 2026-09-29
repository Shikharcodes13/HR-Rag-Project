# XYZ Technologies — HR Policy Assistant (RAG)

Nobody reads the 12-page HR handbook. This app lets any employee just ask —
and every answer is generated **strictly from the source PDF**, with the exact
section and page cited so it can be verified in seconds.

## How it works

```
policy.pdf ──▶ section-aware chunking ──▶ Gemini embeddings ──▶ NumPy vector index
                                                                        │
employee question ──▶ embed ──▶ cosine top-5 ──▶ grounded prompt ──▶ Gemini ──▶ answer + citations
```

Grounding safeguards:

- The system prompt forbids outside knowledge and requires inline `[Section X — Name]` citations.
- A **relevance floor** (`MIN_SCORE` in `app/config.py`) short-circuits off-topic questions
  before the model is ever called — they get a clean "not in the policy" reply plus the HR helpdesk contact.
- Headings are prefixed onto each chunk, so the embedding carries topical context
  and answers land on the right section.
- Personal questions ("what is *my* balance?") are answered with the rule, then redirected to the HRMS.

## Setup

The `.env`, the virtual environment and the index are **already set up** — you can skip
straight to step 4 and run it. The steps below are for rebuilding from scratch.

1. **Get a free Gemini API key** at <https://aistudio.google.com/apikey>,
   then put it in `.env` as `GOOGLE_API_KEY=...` (copy `.env.example` to start).

2. **Install dependencies:**

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. **Build the index** from the bundled policy PDF:

```bash
.venv\Scripts\python.exe build_index.py
```

4. **Run the app:**

```bash
run.bat
```

   Open <http://127.0.0.1:8000>.

## Using it

- Type any question, or click a topic in the left rail.
- Each answer shows a **Verified from PDF** badge and an expandable list of the
  source passages with page numbers and match scores.
- **Replace policy PDF** (bottom-left) uploads and re-indexes a new handbook at runtime —
  no restart needed. Swap in a different company's policy and it works the same.

## Project layout

| Path | Purpose |
|---|---|
| `app/config.py` | Models, chunk sizes, retrieval tuning knobs |
| `app/ingest.py` | PDF → section-aware, citable chunks |
| `app/store.py` | NumPy cosine-similarity vector store |
| `app/rag.py` | Embedding, retrieval, grounded prompting |
| `app/main.py` | FastAPI routes (`/api/ask`, `/api/upload`, `/api/status`) |
| `static/` | The UI (no build step, no framework) |
| `storage/` | Generated index — safe to delete and rebuild |

## Models

Set in `app/config.py`:

- `EMBED_MODEL = models/gemini-embedding-001`
- `CHAT_MODEL = gemini-2.5-flash`

If you see a `404 ... not found for API version v1beta`, your key has a different model
set available. List what yours supports:

```bash
.venv\Scripts\python.exe -c "import google.generativeai as g; from app.config import GOOGLE_API_KEY; g.configure(api_key=GOOGLE_API_KEY); [print(m.name) for m in g.list_models()]"
```

## Tuning

Edit `app/config.py`:

- `TOP_K` — passages sent to the model (raise for broad questions, lower for precision)
- `MIN_SCORE` — off-topic threshold, currently `0.64`. Calibrated by measuring real scores:
  on-topic questions scored **0.70–0.78**, off-topic ones **0.54–0.58**. Note that
  `gemini-embedding-001` never returns near-zero similarity, so this floor must sit
  high — re-measure if you switch embedding models.
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — re-run `build_index.py` after changing these
