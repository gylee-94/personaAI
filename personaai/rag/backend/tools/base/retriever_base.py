from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_huggingface import HuggingFaceEmbeddings

import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RetrievalChain(ABC):
    """
    Abstract base class for RAG search implementations.

    This class provides a template for different document retrieval chains,
    allowing for customization of document loading, splitting, vectorization,
    and various search methods.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize a RetrievalChain with configuration parameters.

        Args:
            **kwargs: Keyword arguments including:
                source_uris: Paths to source documents
                k: Number of results to return (default: 5)
                embedding_model: Model name for embeddings (default: OpenAI "text-embedding-3-small")
                persist_directory: Directory to persist vector store
        """
        self.source_uris = kwargs.get("source_uris", [])
        self.k = kwargs.get("k", 5)
        self.embedding_model = kwargs.get("embedding_model", "text-embedding-3-small")
        self.persist_directory = kwargs.get("persist_directory", None)
        self.embeddings = None
        self.vectorstore = None
        self.retrievers = None
        self.splited = None

    @abstractmethod
    def load_documents(self, source_uris: List[str]) -> List[Document]:
        """
        Load documents from source URIs.

        Args:
            source_uris: List of file paths or URIs to load documents from

        Returns:
            List of loaded documents
        """
        pass

    @abstractmethod
    def create_text_splitter(self) -> Any:
        """
        Create a text splitter appropriate for the document type.

        Returns:
            A text splitter instance
        """
        pass

    @abstractmethod
    def create_vectorstore(self) -> Any:
        """
        Load or initialize the vector store.
        This might load an existing store or return a new/empty instance.
        """
        pass

    def split_documents(self, docs: List[Document], text_splitter: Any) -> List[Document]:
        """
        Split documents into chunks using the provided text splitter.

        Args:
            docs: Documents to split
            text_splitter: Text splitter instance

        Returns:
            Splited document chunks
        """

        return text_splitter.split_documents(docs)

    def create_embedding(self) -> HuggingFaceEmbeddings:
        """
        Create an embedding model instance.

        Returns:
            An embeddings model instance
        """
        # Add model_kwargs to trust remote code
        model_kwargs = {'trust_remote_code': True}
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model,
            model_kwargs=model_kwargs # Pass the argument here
        )

    def create_semantic_retriever(self, vectorstore: Any) -> BaseRetriever:
        """
        Create a semantic search retriever from the vector store.
        """
        # Ensure vectorstore is valid before using
        if not vectorstore:
             raise ValueError("Cannot create semantic retriever from an invalid vector store.")

        return vectorstore.as_retriever(search_kwargs={"k": self.k})

    def create_retrievers(self) -> Dict[str, Optional[BaseRetriever]]:
        """
        Create retriever instances using the initialized/updated self.vectorstore.
        Only creates the semantic retriever for now.

        Returns:
            Dictionary containing the semantic retriever (or None for others).
        """
        if not hasattr(self, 'vectorstore') or self.vectorstore is None:
            logger.error("Vector store is not initialized before creating retrievers.")

            raise ValueError("Vector store is not initialized before creating retrievers.")

        try:
            semantic_retriever = self.create_semantic_retriever(self.vectorstore)
            logger.info("Semantic retriever created successfully.")

            return {
                "semantic": semantic_retriever,
                "keyword": None,
                "hybrid": None,
            }

        except Exception as e:
            logger.error(f"Failed to create semantic retriever: {e}", exc_info=True)

            raise ValueError("Failed to create semantic retriever.") from e

    def initialize(self) -> "RetrievalChain":
        """
        Initialize the retrieval chain: load/init vector store, identify and
        process only new documents, add them to the store, and create retrievers.

        Returns:
            The initialized and potentially updated retrieval chain instance.
        """
        logger.info("Initializing retrieval chain for incremental updates...")
        self.embeddings = self.create_embedding() # Needed for Chroma interaction

        # 1. Load or initialize vector store
        try:
            self.vectorstore = self.create_vectorstore()

            if not self.vectorstore:
                # This should ideally not happen if create_vectorstore raises errors properly
                raise ValueError("create_vectorstore returned an invalid object.")

            logger.debug("Vector store loaded or initialized successfully.")

        except Exception as e:
            logger.error(f"Fatal error during vector store initialization: {e}", exc_info=True)

            raise ValueError("Could not initialize vector store. Cannot continue.") from e

        # 2. Get existing sources from the vector store
        existing_sources = set()

        try:
            # Use get() which is standard Chroma API. Handle potential emptiness.
            existing_data = self.vectorstore.get(include=["metadatas"])
            # Check if the response structure is as expected
            if existing_data and isinstance(existing_data.get('metadatas'), list):
                for metadata in existing_data['metadatas']:
                    # Ensure metadata is a dict and has 'source'
                    if isinstance(metadata, dict) and 'source' in metadata:
                        existing_sources.add(metadata['source'])
                logger.debug(f"Found {len(existing_sources)} unique existing sources in the vector store.")

            else:
                logger.debug("No existing metadata found or unexpected format. Assuming store is empty or sources are not stored.")

        except Exception as e:
            # Catch potential errors during .get() e.g., DB connection issues after init
            logger.warning(f"Could not retrieve existing sources from vector store: {e}. Proceeding as if empty.", exc_info=True)

        # 3. Find new source URIs to process
        # self.source_uris comes from graph.py (glob results)
        if not isinstance(self.source_uris, list):
             logger.warning(f"source_uris is not a list ({type(self.source_uris)}). Skipping incremental check.")
             new_source_uris = []

        else:
             current_uris_set = set(self.source_uris)
             new_source_uris = list(current_uris_set - existing_sources)

        if not new_source_uris:
            logger.debug("No new PDF files found to index.")
            self.splited = [] # No new docs were split
            logger.debug("No new documents to index.")

        else:
            logger.debug(f"Found {len(new_source_uris)} new PDF files to index: {new_source_uris}")

            # 4. Load and split only new documents
            docs = self.load_documents(new_source_uris)
            if not docs:
                logger.warning(f"Failed to load any documents from the new source URIs: {new_source_uris}")
                self.splited = []

            else:
                text_splitter = self.create_text_splitter()
                self.splited = self.split_documents(docs, text_splitter)
                logger.debug(f"Loaded and split {len(docs)} new documents into {len(self.splited)} chunks.")

                # 5. Add new documents to the vector store
                if self.splited:
                    try:

                        logger.debug(f"Adding {len(self.splited)} new chunks to the vector store...")
                        self.vectorstore.add_documents(documents=self.splited)
                        logger.debug(f"Successfully added new chunks to the vector store.")
                        # Persist changes explicitly if needed (Chroma usually handles this)
                        # self.vectorstore.persist()

                    except Exception as e:
                        logger.error(f"Failed to add new documents to vector store: {e}", exc_info=True)

                        raise ValueError("Failed to add new documents to vector store.") from e

        # 6. Create retrievers using the potentially updated vector store
        # self.splited is set based on whether new docs were processed
        self.retrievers = self.create_retrievers() # Now uses self.vectorstore

        if not self.retrievers or self.retrievers.get("semantic") is None:
            logger.error("Failed to create semantic retriever after initialization/update.")
            # Raise error as the main retriever is unusable
            raise ValueError("Semantic retriever could not be created.")

        logger.debug("Retriever initialization and update complete.")
        return self

    def search_semantic(self, query: str, k: Optional[int] = None) -> List[Document]:
        """
        Perform semantic search on the loaded documents.

        Args:
            query: Search query
            k: Number of results to return, overrides self.k

        Returns:
            Relevant documents

        Raises:
            ValueError: If the retrieval chain is not initialized
        """

        if not hasattr(self, 'retrievers') or self.retrievers is None:
            raise ValueError("Initialization required. Call initialize() method first.")

        k = k or self.k
        retriever = self.retrievers["semantic"]
        retriever.search_kwargs["k"] = k

        return retriever.get_relevant_documents(query)

    def search_keyword(self, query: str, k: Optional[int] = None) -> List[Document]:
        """
        Perform keyword-based search on the loaded documents.

        Args:
            query: Search query
            k: Number of results to return (Note: BM25Retriever may not support dynamic k)

        Returns:
            Relevant documents

        Raises:
            ValueError: If the retrieval chain is not initialized
        """

        if not hasattr(self, 'retrievers') or self.retrievers is None:
            raise ValueError("Initialization required. Call initialize() method first.")

        return self.retrievers["keyword"].get_relevant_documents(query)

    def search_hybrid(self, query: str, k: Optional[int] = None) -> List[Document]:
        """
        Perform hybrid search (keyword + semantic) on the loaded documents.

        Args:
            query: Search query
            k: Number of results to return (Note: EnsembleRetriever may not support dynamic k)

        Returns:
            Relevant documents

        Raises:
            ValueError: If the retrieval chain is not initialized
        """

        if not hasattr(self, 'retrievers') or self.retrievers is None:
            raise ValueError("Initialization required. Call initialize() method first.")

        return self.retrievers["hybrid"].get_relevant_documents(query)

    def search(self, query: str, k: Optional[int] = None) -> List[Document]:
        """
        Default search method that uses semantic search.

        Args:
            query: Search query
            k: Number of results to return, overrides self.k

        Returns:
            Relevant documents
        """

        return self.search_semantic(query, k)
