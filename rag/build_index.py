from pathlib import Path

from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)

from llama_index.core.node_parser import SentenceSplitter

from rag.settings import (
    collection,
    embed_model,
    vector_store,
)


# ==========================================================
# Configuration
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RECIPES_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "recipes"
)

# Keep chunks reasonably large so we do not create
# tens of thousands of embeddings.
CHUNK_SIZE = 1800

CHUNK_OVERLAP = 100

# We expect roughly 5,300 chunks with italian3 included.
MAX_ALLOWED_CHUNKS = 6000


# These two PDFs are too large for development indexing.
EXCLUDED_FILES = {
    "italian2.pdf",
    "The Great Italian Cookbook.pdf",
}


# ==========================================================
# LlamaIndex configuration
# ==========================================================

Settings.embed_model = embed_model

splitter = SentenceSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


# ==========================================================
# Load recipe PDFs
# ==========================================================

def load_recipe_documents():
    documents = []

    if not RECIPES_DIRECTORY.exists():
        print("Recipes directory does not exist:")
        print(RECIPES_DIRECTORY)

        return documents

    for cuisine_folder in sorted(
        RECIPES_DIRECTORY.iterdir()
    ):
        if not cuisine_folder.is_dir():
            continue

        pdf_files = sorted(
            cuisine_folder.rglob("*.pdf")
        )

        if not pdf_files:
            print(
                f"Skipping {cuisine_folder.name} "
                "(no PDFs found)"
            )
            continue

        print(
            f"\n{cuisine_folder.name}: "
            f"{len(pdf_files)} PDF(s)"
        )

        for pdf_file in pdf_files:

            # ------------------------------------------
            # Skip only the two huge Italian books.
            # italian3.pdf is still included.
            # ------------------------------------------

            if pdf_file.name in EXCLUDED_FILES:
                print(
                    f"  Skipping: {pdf_file.name} "
                    "(disabled for development)"
                )
                continue

            print(
                f"  Reading: {pdf_file.name}"
            )

            try:
                reader = SimpleDirectoryReader(
                    input_files=[
                        str(pdf_file)
                    ]
                )

                pdf_documents = (
                    reader.load_data()
                )

            except Exception as error:
                print(
                    f"  ERROR reading "
                    f"{pdf_file.name}: {error}"
                )
                continue

            for document in pdf_documents:

                document.metadata[
                    "cuisine"
                ] = cuisine_folder.name

                document.metadata[
                    "source_file"
                ] = pdf_file.name

            documents.extend(
                pdf_documents
            )

            characters = sum(
                len(document.text or "")
                for document in pdf_documents
            )

            print(
                f"    Documents: "
                f"{len(pdf_documents)}"
            )

            print(
                f"    Characters extracted: "
                f"{characters:,}"
            )

    return documents


# ==========================================================
# Create chunks BEFORE embedding
# ==========================================================

def create_nodes(
    documents,
):
    print(
        "\nPreparing chunks..."
    )

    nodes = (
        splitter
        .get_nodes_from_documents(
            documents
        )
    )

    return nodes


# ==========================================================
# Print preflight statistics
# ==========================================================

def print_chunk_statistics(
    nodes,
):
    print(
        "\n=============================="
    )

    print(
        "INDEX PREFLIGHT"
    )

    print(
        "=============================="
    )

    print(
        f"Chunk size: {CHUNK_SIZE}"
    )

    print(
        f"Chunk overlap: "
        f"{CHUNK_OVERLAP}"
    )

    print(
        f"TOTAL CHUNKS: "
        f"{len(nodes):,}"
    )

    print(
        f"TOTAL EMBEDDINGS REQUIRED: "
        f"{len(nodes):,}"
    )

    counts = {}

    for node in nodes:

        source = node.metadata.get(
            "source_file",
            "Unknown"
        )

        counts[source] = (
            counts.get(source, 0)
            + 1
        )

    print(
        "\nChunks by PDF:"
    )

    for source, count in sorted(
        counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(
            f"  {source}: "
            f"{count:,}"
        )

    print(
        "==============================\n"
    )


# ==========================================================
# Clear old Chroma index
# ==========================================================

def clear_existing_index():
    """
    Only clear the previous index after the new build passes
    the preflight safety check.
    """

    current_count = (
        collection.count()
    )

    if current_count == 0:
        print(
            "Existing recipe index is empty."
        )
        return

    print(
        f"Removing "
        f"{current_count:,} "
        "old recipe chunks..."
    )

    data = collection.get()

    ids = data.get(
        "ids",
        []
    )

    if ids:
        collection.delete(
            ids=ids
        )

    print(
        "Old index cleared."
    )


# ==========================================================
# Build index
# ==========================================================

def build_index():

    print(
        "Loading recipe documents..."
    )

    documents = (
        load_recipe_documents()
    )

    print(
        f"\nLoaded "
        f"{len(documents)} "
        "document(s)."
    )

    if not documents:
        print(
            "No recipe documents found."
        )
        return

    # ------------------------------------------
    # No embeddings yet.
    # ------------------------------------------

    nodes = create_nodes(
        documents
    )

    print_chunk_statistics(
        nodes
    )

    # ------------------------------------------
    # Safety check
    # ------------------------------------------

    if len(nodes) > MAX_ALLOWED_CHUNKS:

        print(
            "BUILD STOPPED."
        )

        print(
            f"The index would require "
            f"{len(nodes):,} embeddings."
        )

        print(
            f"The current safety limit is "
            f"{MAX_ALLOWED_CHUNKS:,}."
        )

        print(
            "\nNothing was embedded and "
            "the existing Chroma database "
            "was not deleted."
        )

        return

    # ------------------------------------------
    # Safe to proceed.
    # ------------------------------------------

    clear_existing_index()

    storage_context = (
        StorageContext.from_defaults(
            vector_store=vector_store
        )
    )

    print(
        "\nCreating embeddings..."
    )

    print(
        f"Exactly {len(nodes):,} "
        "embeddings will be generated."
    )

    print(
        "This is the slow part."
    )

    VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )

    final_count = (
        collection.count()
    )

    print(
        "\nRecipe index built successfully."
    )

    print(
        f"Stored vectors in ChromaDB: "
        f"{final_count:,}"
    )


if __name__ == "__main__":
    build_index()