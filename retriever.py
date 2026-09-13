import os
import re
import glob
import math

import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

CORPUS_DIR = os.environ.get("CORPUS_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "finance_rag_corpus"
)
MODEL = "text-embedding-3-small"
THRESHOLD = 0.4
client = OpenAI()
INDEX = None


def _load_chunks():
    chunks = []
    for path in glob.glob(os.path.join(CORPUS_DIR, "*.md")):
        _, fm, body = open(path, encoding="utf-8").read().split("---", 2)
        meta = yaml.safe_load(fm)
        for part in re.split(r"\n(?=## )", body):
            part = part.strip()
            if not part.startswith("## "):
                continue
            section = part.splitlines()[0].lstrip("# ").strip()
            chunks.append({
                "document_id": meta.get("document_id"),
                "title": meta.get("title"),
                "version": meta.get("version"),
                "status": meta.get("status"),
                "section": section,
                "text": f"{meta.get('title')}: {part}",
            })
    return chunks


def _embed(texts):
    return [d.embedding for d in client.embeddings.create(model=MODEL, input=texts).data]


def _ensure():
    global INDEX
    if INDEX is None:
        INDEX = _load_chunks()
        for c, e in zip(INDEX, _embed([c["text"] for c in INDEX])):
            c["embedding"] = e
    return INDEX


def _cos(a, b):
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return d / (na * nb) if na and nb else 0.0


def retrieve(query, k=4):
    q = _embed([query])[0]
    scored = sorted(((_cos(q, c["embedding"]), c) for c in _ensure()), reverse=True, key=lambda s: s[0])
    fields = ("document_id", "title", "version", "status", "section", "text")
    return [
        {f: c[f] for f in fields}
        | {"score": round(s, 3), "confidence": "high" if s >= THRESHOLD else "low"}
        for s, c in scored[:k]
    ]
