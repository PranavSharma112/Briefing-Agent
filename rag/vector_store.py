"""Persistent vector store for transcript/text chunks, keyed by doc_id."""
import chromadb


class VectorStore:
    def __init__(self, collection_name: str = "briefings"):
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(collection_name)

    def add_documents(self, doc_id: str, chunks: list[str]) -> None:
        try:
            self.collection.add(
                ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
                documents=chunks,
                metadatas=[{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))],
            )
        except Exception as e:
            print(f"[vector_store] failed to add documents for {doc_id}: {e}")

    def query(self, doc_id: str, query_text: str, n_results: int = 3) -> list[str]:
        try:
            result = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={"doc_id": doc_id},
            )
            return result.get("documents", [[]])[0]
        except Exception as e:
            print(f"[vector_store] query failed for {doc_id}: {e}")
            return []
