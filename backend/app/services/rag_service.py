import re
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

_embedder = None
_client = None

COLLECTION_NAME = "document_chunks"
QDRANT_PATH = "qdrant_data"

CHUNK_WORDS = 200
OVERLAP_WORDS = 40
TOP_K = 3

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _get_embedder() -> SentenceTransformer:
    global _embedder

    if _embedder is None:
        _embedder = SentenceTransformer("BAAI/bge-m3")
        # BGE-M3 supports sequences up to 8192 tokens, and sentence-transformers
        # defaults max_seq_length to the model's max — so every short chunk was
        # being padded/processed as if it were 8192 tokens on CPU (~30x wasted
        # compute). Our chunks are ~200-240 words (~300 tokens), so 512 gives
        # comfortable headroom while cutting encode time drastically.
        _embedder.max_seq_length = 512

    return _embedder


def _get_client() -> QdrantClient:
    global _client

    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)

        if not _client.collection_exists(COLLECTION_NAME):
            dim = _get_embedder().get_embedding_dimension()
            _client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )

    return _client


def _chunk_text(text: str, chunk_words: int = CHUNK_WORDS, overlap_words: int = OVERLAP_WORDS) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]

    chunks = []
    current_words: list[str] = []

    for sentence in sentences:
        current_words.extend(sentence.split())

        if len(current_words) >= chunk_words:
            chunks.append(" ".join(current_words))
            current_words = current_words[-overlap_words:]

    # Only append the trailing remainder if it has genuinely new content
    # beyond the carried-over overlap (or it's the only chunk there is) —
    # otherwise it would just duplicate the tail of the last chunk.
    if current_words and (not chunks or len(current_words) > overlap_words):
        chunks.append(" ".join(current_words))

    return chunks or ([text] if text.strip() else [])


def index_document(document_id: str, text: str) -> None:
    chunks = _chunk_text(text)

    if not chunks:
        return

    embedder = _get_embedder()
    client = _get_client()

    vectors = embedder.encode(chunks, normalize_embeddings=True)

    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector.tolist(),
            payload={"document_id": document_id, "chunk_index": i, "text": chunk},
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)


def retrieve_relevant_chunks(document_id: str, question: str, top_k: int = TOP_K) -> str:
    embedder = _get_embedder()
    client = _get_client()

    query_vector = embedder.encode(question, normalize_embeddings=True).tolist()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id))]
        ),
        limit=top_k,
    ).points

    if not results:
        return ""

    ordered = sorted(results, key=lambda r: r.payload["chunk_index"])

    return "\n\n".join(r.payload["text"] for r in ordered)
