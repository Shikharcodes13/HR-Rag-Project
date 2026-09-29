"""The RAG engine: embed -> retrieve -> answer strictly from the source PDF."""
from __future__ import annotations

import re
from pathlib import Path

import google.generativeai as genai

from .config import (
    CHAT_MODEL,
    COMPANY_NAME,
    EMBED_MODEL,
    GOOGLE_API_KEY,
    MIN_SCORE,
    TOP_K,
)
from .ingest import Chunk, load_chunks, parse_pdf, save_chunks
from .store import VectorStore

SYSTEM_PROMPT = f"""You are the HR Policy Assistant for {COMPANY_NAME}.
You answer employee questions using ONLY the policy extracts provided below.

Rules:
1. Base every fact strictly on the extracts. Never use outside knowledge or general
   Indian labour law that is not written in the extracts.
2. If the extracts do not contain the answer, say exactly: "I could not find this in the
   HR policy document." Then suggest the employee contact hr.helpdesk@xyztech.example.
3. Never guess numbers, dates, amounts or eligibility criteria. Quote them as written.
4. Cite the section you used inline, like [Section 5 - Leave Policy].
5. Be concise and direct. Lead with the answer, then the conditions that qualify it.
   Use short bullet points for lists, tables or multi-part entitlements.
6. Write in a warm, professional tone, addressing the employee as "you".
7. If the question is personal (e.g. "what is MY leave balance"), state the policy rule
   and tell them to check the HRMS / XYZ People Portal for their own figures.
"""


class RAGEngine:
    def __init__(self):
        self.chunks: list[Chunk] = []
        self.store = VectorStore()
        self._configured = False

    # ---------- setup ----------
    def _configure(self) -> None:
        if self._configured:
            return
        if not GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key "
                "from https://aistudio.google.com/apikey"
            )
        genai.configure(api_key=GOOGLE_API_KEY)
        self._configured = True

    @property
    def ready(self) -> bool:
        return bool(self.chunks) and self.store.ready

    def load(self) -> bool:
        """Load a previously built index from disk."""
        self.chunks = load_chunks()
        self.store = VectorStore.load()
        return self.ready

    # ---------- embeddings ----------
    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        self._configure()
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 100):  # API batch limit
            resp = genai.embed_content(
                model=EMBED_MODEL, content=texts[i : i + 100], task_type=task
            )
            vectors.extend(resp["embedding"])
        return vectors

    def ingest(self, pdf_path: Path) -> int:
        """Parse, embed and persist a policy PDF. Returns the chunk count."""
        chunks = parse_pdf(pdf_path)
        if not chunks:
            raise ValueError("No readable text found in that PDF.")
        vectors = self._embed([c.text for c in chunks], "retrieval_document")
        self.chunks = chunks
        self.store.build(vectors)
        save_chunks(chunks)
        self.store.save()
        return len(chunks)

    # ---------- query ----------
    def retrieve(self, question: str) -> list[dict]:
        qvec = self._embed([question], "retrieval_query")[0]
        hits = []
        for idx, score in self.store.search(qvec, TOP_K):
            c = self.chunks[idx]
            hits.append(
                {
                    "section": c.section,
                    "page": c.page,
                    "source": c.source,
                    "text": c.text,
                    "score": round(score, 4),
                }
            )
        return hits

    def answer(self, question: str) -> dict:
        if not self.ready:
            raise RuntimeError("No policy document has been indexed yet.")

        hits = self.retrieve(question)
        best = hits[0]["score"] if hits else 0.0

        # Off-topic guard: don't even call the model if nothing is remotely relevant.
        if best < MIN_SCORE:
            return {
                "answer": (
                    "I could not find this in the HR policy document. I can only answer "
                    "questions covered by the XYZ Technologies Employee Handbook — things "
                    "like leave, payroll, insurance, notice periods, travel claims or the "
                    "code of conduct.\n\nFor anything else, please write to "
                    "hr.helpdesk@xyztech.example (Ext. 1100)."
                ),
                "sources": [],
                "grounded": False,
            }

        context = "\n\n---\n\n".join(
            f"[{h['section']} | page {h['page']}]\n{h['text']}" for h in hits
        )
        prompt = (
            f"{SYSTEM_PROMPT}\n\n=== POLICY EXTRACTS ===\n{context}\n"
            f"=== END EXTRACTS ===\n\nEmployee question: {question}\n\nAnswer:"
        )

        self._configure()
        model = genai.GenerativeModel(CHAT_MODEL)
        text = (model.generate_content(prompt).text or "").strip()

        grounded = "could not find this in the hr policy" not in text.lower()
        return {
            "answer": text,
            "sources": [
                {k: h[k] for k in ("section", "page", "source", "score")}
                for h in hits
            ] if grounded else [],
            "grounded": grounded,
        }


engine = RAGEngine()
