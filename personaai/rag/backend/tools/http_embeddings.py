"""
HTTP-based embedding class
HuggingFaceEmbeddings-compatible class via vLLM OpenAI-compatible API
"""
import httpx
import logging
import asyncio
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import time


logger = logging.getLogger(__name__)


class HTTPEmbeddings:
    """
    Class that generates embeddings via vLLM OpenAI-compatible API (/v1/embeddings)
    Provides the same interface as HuggingFaceEmbeddings
    """

    def __init__(
        self,
        service_url: str = "http://localhost:8003",
        model_name: str = "Qwen/Qwen3-Embedding-8B",
        timeout: float = 100.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ):
        self.service_url = service_url.rstrip('/')
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # API endpoint configuration
        self.embed_url = f"{self.service_url}/v1/embeddings"
        self.health_url = f"{self.service_url}/health"

        # HTTP client configuration
        self.client_config = {
            "timeout": httpx.Timeout(timeout),
            "limits": httpx.Limits(max_connections=10, max_keepalive_connections=5)
        }

        # Thread pool (for synchronous methods)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="http_embed")

        logger.info(f"HTTP embedding client initialized: {service_url}")

    def _make_request(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request (with retries)"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(**self.client_config) as client:
                    response = client.post(url, json=data)
                    response.raise_for_status()
                    return response.json()

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Timeout (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_exception = e
                    logger.warning(f"Server error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                else:
                    logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                    raise

            except Exception as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            if attempt < self.max_retries:
                time.sleep(self.retry_delay * (2 ** attempt))

        raise RuntimeError(f"HTTP request failed (after {self.max_retries + 1} attempts): {last_exception}")

    async def _make_request_async(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute asynchronous HTTP request (with retries)"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(**self.client_config) as client:
                    response = await client.post(url, json=data)
                    response.raise_for_status()
                    return response.json()

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Timeout (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_exception = e
                    logger.warning(f"Server error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                else:
                    logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                    raise

            except Exception as e:
                last_exception = e
                logger.warning(f"Async request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))

        raise RuntimeError(f"Async HTTP request failed (after {self.max_retries + 1} attempts): {last_exception}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Convert documents to embeddings (HuggingFaceEmbeddings compatible)"""
        if not texts:
            return []

        try:
            start_time = time.time()

            data = {"model": self.model_name, "input": texts}
            response = self._make_request(self.embed_url, data)
            sorted_data = sorted(response["data"], key=lambda x: x["index"])
            embeddings = [item["embedding"] for item in sorted_data]

            processing_time = time.time() - start_time
            logger.debug(f"Embedding generation complete: {len(texts)} documents, {processing_time:.3f}s")
            return embeddings

        except Exception as e:
            logger.error(f"Document embedding failed: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """Convert a single query to an embedding (HuggingFaceEmbeddings compatible)"""
        try:
            start_time = time.time()

            data = {"model": self.model_name, "input": text}
            response = self._make_request(self.embed_url, data)
            embedding = response["data"][0]["embedding"]

            processing_time = time.time() - start_time
            logger.debug(f"Query embedding complete: {processing_time:.3f}s")
            return embedding

        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous document embedding"""
        if not texts:
            return []

        try:
            start_time = time.time()

            data = {"model": self.model_name, "input": texts}
            response = await self._make_request_async(self.embed_url, data)
            sorted_data = sorted(response["data"], key=lambda x: x["index"])
            embeddings = [item["embedding"] for item in sorted_data]

            processing_time = time.time() - start_time
            logger.debug(f"Async embedding generation complete: {len(texts)} documents, {processing_time:.3f}s")
            return embeddings

        except Exception as e:
            logger.error(f"Async document embedding failed: {e}")
            raise

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous single query embedding"""
        try:
            start_time = time.time()

            data = {"model": self.model_name, "input": text}
            response = await self._make_request_async(self.embed_url, data)
            embedding = response["data"][0]["embedding"]

            processing_time = time.time() - start_time
            logger.debug(f"Async query embedding complete: {processing_time:.3f}s")
            return embedding

        except Exception as e:
            logger.error(f"Async query embedding failed: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Service health check"""
        try:
            with httpx.Client(**self.client_config) as client:
                response = client.get(self.health_url)
                response.raise_for_status()
                # vLLM /health endpoint returns an empty 200
                return {"status": "healthy"}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    def is_service_available(self) -> bool:
        """Check service availability"""
        try:
            health_info = self.health_check()
            return health_info.get("status") == "healthy"
        except:
            return False

    def __del__(self):
        """Destructor - clean up thread pool"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)


class HTTPHuggingFaceEmbeddings(HTTPEmbeddings):
    """
    HTTP embedding class fully compatible with HuggingFaceEmbeddings
    Can be used as a drop-in replacement for existing code
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-8B",
        service_url: str = "http://localhost:8003",
        model_kwargs: Optional[Dict] = None,
        encode_kwargs: Optional[Dict] = None,
        **kwargs
    ):
        super().__init__(
            service_url=service_url,
            model_name=model_name,
            **kwargs,
        )

        # Store for compatibility
        self.model_kwargs = model_kwargs or {}
        self.encode_kwargs = encode_kwargs or {}

        logger.info(f"HTTP HuggingFace-compatible embedding initialized: {model_name} -> {service_url}")


def create_http_embeddings(service_url: str = "http://localhost:8003") -> HTTPHuggingFaceEmbeddings:
    """Create an HTTP embedding instance"""
    return HTTPHuggingFaceEmbeddings(service_url=service_url)


def test_http_embeddings(service_url: str = "http://localhost:8003"):
    """Test HTTP embeddings"""
    embeddings = create_http_embeddings(service_url)

    # Health check
    print("Health check:", embeddings.is_service_available())

    # Single query test
    query_embedding = embeddings.embed_query("test query")
    print(f"Query embedding dimension: {len(query_embedding)}")

    # Document embedding test
    docs = ["document 1", "document 2"]
    doc_embeddings = embeddings.embed_documents(docs)
    print(f"Document embeddings: {len(doc_embeddings)}, dimension: {len(doc_embeddings[0])}")


if __name__ == "__main__":
    test_http_embeddings()
