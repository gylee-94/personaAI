import torch
import os, glob
import logging

from typing import List, Dict, Optional
from langchain_core.documents import Document
from langchain_community.document_compressors import FlashrankRerank
from langchain_huggingface import HuggingFacePipeline, ChatHuggingFace
from langchain_openai import ChatOpenAI
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool
from backend.tools.tavily import TavilySearch
from backend.tools.retrieval import DocumentRetrievalChain

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# def format_search_results(docs: List[Document]) -> List[Document]:
#     """
#     Format search results as markdown.

#     Args:
#         docs: List of documents to format

#     Returns:
#         Markdown formatted search results

#     """

#     if not docs:
#         return []

#     for i, doc in enumerate(docs, 1):
#         source = doc.metadata.get("source", "Unknown source")
#         page = doc.metadata.get("page", None)
#         page_info = f" (Page: {page+1})" if page is not None else ""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _normalize_openrouter_model_id(model_id: str) -> str:
    """OpenRouter expects vendor-prefixed model ids (e.g. ``google/gemini-3.5-flash``).

    Values that already contain a vendor prefix are returned unchanged; a bare
    Gemini name gets a ``google/`` prefix.
    """
    if "/" in model_id:
        return model_id
    if model_id.startswith("gemini"):
        return f"google/{model_id}"
    return model_id


def load_llm(model_name_or_path: str, temperature: float = 0.0) -> ChatOpenAI:
    """Load the chat LLM via OpenRouter (OpenAI-compatible API).

    OpenRouter exposes an OpenAI-compatible endpoint, so ``langchain_openai.ChatOpenAI``
    can call Gemini/Claude/GPT models through it. A local HuggingFace model (a
    filesystem path, or an org/repo/subpath with >=2 slashes) is still loaded
    directly, with CPU fallback on GPU OOM.
    """
    logger.info(f"Input model_name: {model_name_or_path}, Loading LLM...")
    enable_cpu_fallback = os.getenv("ENABLE_CPU_FALLBACK", "true").lower() in ["true", "1", "yes"]

    is_local_hf_model = os.path.isdir(model_name_or_path) or model_name_or_path.count("/") >= 2

    try:
        if is_local_hf_model:
            tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, skip_special_tokens=True)

            # Attempt GPU loading
            device = "cuda" if torch.cuda.is_available() else "cpu"
            try:
                if device == "cuda":
                    logger.info(f"Loading LLM on GPU: {model_name_or_path}")
                    # Clear GPU memory
                    torch.cuda.empty_cache()
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name_or_path,
                        trust_remote_code=True,
                        torch_dtype=torch.bfloat16,
                        device_map="auto"
                    )
                else:
                    raise RuntimeError("CUDA not available, using CPU")

            except (RuntimeError, torch.cuda.OutOfMemoryError) as gpu_error:
                if enable_cpu_fallback:
                    logger.warning(f"⚠️  GPU OOM or error: {gpu_error}")
                    logger.info("🔄 CPU fallback enabled - loading model on CPU...")

                    # Clear GPU memory
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

                    # Retry on CPU (use float32 - bfloat16 is slow on CPU)
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name_or_path,
                        trust_remote_code=True,
                        torch_dtype=torch.float32,
                        device_map="cpu"
                    )
                    device = "cpu"
                    logger.info("✅ LLM loading on CPU complete")
                else:
                    raise gpu_error

            pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=4096, device=device if device == "cpu" else None)

            hf = HuggingFacePipeline(pipeline=pipe)
            llm = ChatHuggingFace(llm=hf, verbose=True)

            return llm

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is not set")

        resolved_model = _normalize_openrouter_model_id(model_name_or_path)
        logger.info(f"Loading LLM via OpenRouter: {resolved_model}")

        return ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            max_tokens=None,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://personaai.local"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "PersonaAI RAG"),
            },
        )

    except Exception as e:
        raise ValueError(f"Unexpectedly failed to load LLM from {model_name_or_path}: {e}")


def get_reranker(model_name_or_path: str = "ms-marco-MultiBERT-L-12", top_n: int = 3, score_threshold: float = 0.7) -> FlashrankRerank:
    flash_model_list = ["ms-marco-MultiBERT-L-12", "ms-marco-MiniLM-L-12-v2", "rank-T5-flan", "rank_zephyr_7b_v1_full"]
    try:
        if model_name_or_path not in flash_model_list:
            raise ValueError(f"Invalid flash reranker model: {model_name_or_path}\nPlease choose from the following models: {flash_model_list}")

        else:
            return FlashrankRerank(model=model_name_or_path,
                                   top_n=top_n,
                                   score_threshold=score_threshold)

    except Exception as e:
        raise ValueError(f"Unexpectedly failed to load Reranker from {model_name_or_path}: {e}")

def get_search_tool(return_stats: bool = False, index: bool = True):
    """
    Initialize Retriever and Web search tool.

    If return_stats=True, returns a (retrievers_dict, stats_dict) tuple.
    stats_dict holds the actual indexing throughput (number of requested files, number of created/added chunks, number of failed batches).

    If index=False, only the retriever is built without (re-)embedding any documents.
    Use this for verification/result-checking after indexing is already done, to avoid
    re-embedding files that workers have already processed (duplicate points in Qdrant).
    """
    # --- Initialize Local PDF Retriever (Qdrant based) ---
    logger.info("Initializing local data retriever (Qdrant based) for PDF and XML files...")

    data_dir = os.getenv("DATA_DIR")
    source_uris = []

    if data_dir and os.path.isdir(data_dir):
        # pdf files
        pdf_pattern = os.path.join(data_dir, '*.pdf')
        pdf_files = glob.glob(pdf_pattern)

        if pdf_files:
            logger.info(f"Found {len(pdf_files)} PDF files in {data_dir}.")
            source_uris.extend(pdf_files)

        # xml files
        xml_pattern = os.path.join(data_dir, '*.xml')
        xml_files = glob.glob(xml_pattern)

        if xml_files:
            logger.info(f"Found {len(xml_files)} XML files in {data_dir}.")
            source_uris.extend(xml_files)

        # markdown files
        markdown_pattern = os.path.join(data_dir, '*.md')
        markdown_files = glob.glob(markdown_pattern)

        if markdown_files:
            logger.info(f"Found {len(markdown_files)} Markdown files in {data_dir}.")
            source_uris.extend(markdown_files)

        if not source_uris:
            logger.warning(f"No PDF or XML or Markdown files found in directory: {data_dir}")

    else:
        logger.warning(f"DATA_DIR environment variable is not set or is not a valid directory. No local files will be loaded.")

    # Qdrant vector store configuration (Qdrant stores data on its own in ./storage)
    embedding_model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    try:
        # initialize() loads an existing DB, or processes documents and creates a DB if needed.
        # Note: initialization can take time when there are many documents.
        # In actual production, it is recommended to separate DB creation/updates into a separate process.
        chain = DocumentRetrievalChain(
            source_uris=source_uris, # Pass the modified URI list
            persist_directory=None, # Qdrant uses its own storage
            embedding_model=embedding_model_name # Pass embedding model name
            # k=5 # Default k is 5 in the base class
        ).initialize(index=index)

        # --- Check if initialization was successful ---
        if not chain.retrievers or not isinstance(chain.retrievers, dict):
            logger.error("Data retriever initialization failed. The 'retrievers' attribute is missing or invalid.")
            raise ValueError("Failed to initialize data retrievers. Check logs for details.")

        # Create SemanticRetriever instance (now safe to access)
        retrievers = chain.retrievers
        logger.info(f"Local semantic retriever initialized using Qdrant with {len(source_uris)} potential sources.")

    except Exception as e:
        logger.error(f"Failed to initialize local data retriever: {e}", exc_info=True)
        # semantic_retriever = None # Set to None on initialization failure to prevent errors
        raise e # Or raise the error here to abort execution

    # Initialize Tavily web search tool
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if tavily_api_key:
        tavily_tool = TavilySearch(api_key=tavily_api_key)
    else:
        logger.warning("TAVILY_API_KEY not found. Web search will not be available.")
        raise ValueError("TAVILY_API_KEY not found. Web search will not be available.")

    retrievers_dict: Dict[str, Optional[BaseRetriever | BaseTool]] = {
        **retrievers,
        "web": tavily_tool
    }

    # Build the final retriever dictionary (uses Semantic only)
    if return_stats:
        stats = {
            "requested_files": getattr(chain, "requested_file_count", len(source_uris)),
            "total_chunks": getattr(chain, "total_chunk_count", 0),
            "indexed_chunks": getattr(chain, "indexed_chunk_count", 0),
            "failed_batches": getattr(chain, "failed_batch_count", 0),
        }
        return retrievers_dict, stats

    return retrievers_dict

from typing import List, Dict, Any, Optional
from backend.agent.state import AgentState, SearchResult

# --- Helper Functions ---
def format_search_results(
    results: List[SearchResult],
    used_doc_indices: Optional[List[int]] = None,
    not_used_doc_indices: Optional[List[int]] = None,
    new_doc_start_index: int = 0
) -> str:
    """Format search results (a list of SearchResult) into a string for the LLM context.

    Args:
        results: List of search results
        used_doc_indices: List of document indices used in the previous answer
        not_used_doc_indices: List of document indices not used in the previous answer
        new_doc_start_index: Index at which newly retrieved documents start (0 means all are new documents)

    Returns:
        A formatted string including document status tags
    """
    formatted = []
    doc_counter = 1

    # Function to determine the document status tag
    def get_status_tag(idx: int) -> str:
        if new_doc_start_index > 0 and idx >= new_doc_start_index:
            return "[NEW]"
        elif used_doc_indices and idx in used_doc_indices:
            return "[USED]"
        elif not_used_doc_indices and idx in not_used_doc_indices:
            return "[NOT USED]"
        return ""

    # Generate document status summary (only from Loop 2 onwards)
    if new_doc_start_index > 0 or used_doc_indices or not_used_doc_indices:
        summary_parts = ["=== Document Status Summary ==="]
        if used_doc_indices:
            summary_parts.append(f"- Previously Used: {used_doc_indices}")
        if not_used_doc_indices:
            summary_parts.append(f"- Previously Not Used: {not_used_doc_indices}")
        if new_doc_start_index > 0:
            # Calculate the range of new document indices
            total_docs = sum(len(r.documents) for r in results if r.documents)
            new_indices = list(range(new_doc_start_index, total_docs + 1))
            if new_indices:
                summary_parts.append(f"- Newly Retrieved: {new_indices}")
        summary_parts.append("")
        summary_parts.append("=== Documents ===")
        summary_parts.append("")
        formatted.append("\n".join(summary_parts))

    for i, result in enumerate(results):
        if not result.documents:
            continue

        for doc in result.documents:
            base_source_info = doc.metadata.get("source", f'doc_{doc_counter}')
            chunk_id = doc.metadata.get("chunk_id")
            page_content = doc.page_content.replace('\n', ' ').strip()

            # Generate the final source info string
            if chunk_id:
                final_source_info = f"{base_source_info} (Chunk: {chunk_id})"
            else:
                final_source_info = base_source_info

            # Add the document status tag
            status_tag = get_status_tag(doc_counter)
            if status_tag:
                formatted.append(f"---Document {doc_counter} (Source: {final_source_info}) {status_tag}---\n{page_content}")
            else:
                formatted.append(f"---Document {doc_counter} (Source: {final_source_info})---\n{page_content}")

            doc_counter += 1

    return "\n\n".join(formatted)

def deduplicate_search_results(results: List[SearchResult]) -> List[SearchResult]:
    """Keep documents within a SearchResult list unique by (source, chunk_id).
    Prevents chunks with the same (source, chunk_id) from appearing multiple times,
    avoiding duplicate processing during the loop and improving memory efficiency.
    """
    seen_chunk_keys = set()
    deduplicated_results = []
    logger.debug(f"--- Processing documents across {len(results)} SearchResult objects, ensuring unique (source, chunk_id) ---")
    total_docs_before = sum(len(r.documents) for r in results if r.documents)

    for result in results:
        unique_docs_in_result = []
        if not result.documents: # SearchResults with no documents are not included in the result
            continue

        for doc in result.documents:
            # --- Modification start ---
            source = doc.metadata.get("source")
            chunk_id = doc.metadata.get("chunk_id",0)

            # When source exists
            if source is not None:
                chunk_key = (source, chunk_id)

                # When this (source, chunk_id) key is seen for the first time
                if chunk_key not in seen_chunk_keys:
                    seen_chunk_keys.add(chunk_key) # Add the key to the set
                    unique_docs_in_result.append(doc)
            else:
                # When source or chunk_id is missing, do not include it.
                logger.warning(f"Document missing 'source' or 'chunk_id' in metadata, keeping it: {doc.metadata}")
                continue

        # If this SearchResult has documents with unique (source, chunk_id), add it to the result
        if unique_docs_in_result:
             deduplicated_results.append(SearchResult(
                 question=result.question,
                 documents=unique_docs_in_result
             ))
        # This log rarely occurs since it is based on (source, chunk_id)
        # else:
        #      logger.debug(f"SearchResult for question '{result.question}' removed as all its documents had duplicate (source, chunk_id).")

    total_docs_after = sum(len(r.documents) for r in deduplicated_results)
    # Log message update
    logger.debug(f"--- Processed {total_docs_before} documents, resulting in {total_docs_after} documents with unique (source, chunk_id) pairs across {len(deduplicated_results)} SearchResults ---")
    return deduplicated_results

def merge_and_deduplicate_context(existing_context: Optional[List[SearchResult]], new_results: List[SearchResult]) -> List[SearchResult]:
    """Merge the existing context with new search results and return a SearchResult list with duplicate documents removed."""
    combined_results = (existing_context or []) + new_results
    # Pass the combined list to the deduplication function
    return deduplicate_search_results(combined_results)


def initialize_visits_and_loop(state: AgentState) -> Dict[str, Any]:
    """Helper to initialize node_visits and loop_count in the state."""
    return {
        "node_visits": 0,
        "loop_count": 0
    }

def update_status_and_visit(state: AgentState, status: str) -> Dict[str, Any]:
    """Helper to create a dictionary containing status and incremented node_visits updates."""
    current_visits = state.get("node_visits", 0)
    loop_count = state.get("loop_count", 0)
    logger.debug("----------------------------------------------------------")
    logger.debug(f"--- Status: {status} | Node Visits: {current_visits + 1} | Loop Count: {loop_count} ---")
    logger.debug("----------------------------------------------------------")
    return {"node_visits": current_visits + 1, "status": status}
