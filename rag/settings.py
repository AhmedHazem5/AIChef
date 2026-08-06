from pathlib import Path

import chromadb

from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore


# ==========================================================
# Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHROMA_DB_PATH = PROJECT_ROOT / "rag" / "chroma_db"


# ==========================================================
# Embedding model
# ==========================================================

embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
)


# ==========================================================
# ChromaDB
# ==========================================================

chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)

collection = chroma_client.get_or_create_collection(
    name="recipes"
)

vector_store = ChromaVectorStore(
    chroma_collection=collection,
)