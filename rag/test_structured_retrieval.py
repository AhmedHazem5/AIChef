from pathlib import Path

import chromadb

from llama_index.core import (
    Settings,
    StorageContext,
    VectorStoreIndex,
)

from llama_index.embeddings.ollama import (
    OllamaEmbedding,
)

from llama_index.vector_stores.chroma import (
    ChromaVectorStore,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

CHROMA_DB_PATH = (
    PROJECT_ROOT
    / "rag"
    / "structured_chroma_db"
)


# ============================================================
# Embedding model
# ============================================================

embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
)

Settings.embed_model = embed_model


# ============================================================
# Open existing Chroma collection
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)

collection = chroma_client.get_collection(
    name="structured_recipes"
)

vector_store = ChromaVectorStore(
    chroma_collection=collection
)

storage_context = StorageContext.from_defaults(
    vector_store=vector_store
)

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    storage_context=storage_context,
    embed_model=embed_model,
)


# ============================================================
# Retriever
# ============================================================

retriever = index.as_retriever(
    similarity_top_k=5
)


# ============================================================
# Test
# ============================================================

def test_query(
    query: str,
):

    print(
        "\n========================================"
    )

    print(
        f"QUERY: {query}"
    )

    print(
        "========================================"
    )

    results = retriever.retrieve(
        query
    )

    if not results:

        print(
            "No recipes found."
        )

        return

    for rank, result in enumerate(
        results,
        start=1,
    ):

        node = result.node

        metadata = (
            node.metadata
            or {}
        )

        print(
            f"\n#{rank}"
        )

        print(
            f"Score: "
            f"{result.score}"
        )

        print(
            f"ID: "
            f"{metadata.get('recipe_id')}"
        )

        print(
            f"Title: "
            f"{metadata.get('title')}"
        )

        print(
            f"Cuisine: "
            f"{metadata.get('cuisine')}"
        )

        print(
            f"Country: "
            f"{metadata.get('country')}"
        )

        print(
            f"Category: "
            f"{metadata.get('category')}"
        )

        print(
            f"Calories: "
            f"{metadata.get('calories')}"
        )

        print(
            f"Protein: "
            f"{metadata.get('protein_g')} g"
        )


def main():

    print(
        f"Stored vectors: "
        f"{collection.count()}"
    )

    test_queries = [
        "healthy chicken recipe",
        "Egyptian recipe",
        "Japanese beef recipe",
        "Italian pasta recipe",
        "high protein chicken recipe",
        "shrimp recipe",
    ]

    for query in test_queries:

        test_query(
            query
        )


if __name__ == "__main__":
    main()