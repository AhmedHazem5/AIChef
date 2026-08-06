from pathlib import Path

from llama_index.core import Settings
from llama_index.core import SimpleDirectoryReader
from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex

from rag.settings import embed_model
from rag.settings import vector_store


# ==========================================================
# Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RECIPES_DIRECTORY = PROJECT_ROOT / "data" / "recipes"


# ==========================================================
# LlamaIndex settings
# ==========================================================

Settings.embed_model = embed_model


def load_recipe_documents():
    """
    Load every PDF inside every cuisine folder.
    Empty folders are skipped automatically.
    """

    documents = []

    if not RECIPES_DIRECTORY.exists():
        print("Recipes directory does not exist.")
        return documents

    for cuisine_folder in RECIPES_DIRECTORY.iterdir():

        if not cuisine_folder.is_dir():
            continue

        # Search recursively for PDFs
        pdf_files = list(cuisine_folder.rglob("*.pdf"))

        if not pdf_files:
            print(f"Skipping {cuisine_folder.name} (no PDFs found)")
            continue

        print(
            f"Loading {len(pdf_files)} PDF(s) from {cuisine_folder.name}..."
        )

        reader = SimpleDirectoryReader(
            input_files=[str(pdf) for pdf in pdf_files]
        )

        cuisine_documents = reader.load_data()

        for document in cuisine_documents:
            document.metadata["cuisine"] = cuisine_folder.name

        documents.extend(cuisine_documents)

    return documents


def build_index():
    """
    Build the ChromaDB vector index from all recipe PDFs.
    """

    documents = load_recipe_documents()

    print(f"\nLoaded {len(documents)} document(s).")

    if not documents:
        print("No recipe PDFs found.")
        print("Add PDFs inside data/recipes/<Cuisine>/")
        return

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
    )

    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
    )

    print("\nRecipe index built successfully.")


if __name__ == "__main__":
    build_index()