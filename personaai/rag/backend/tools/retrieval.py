import os
import asyncio
import torch
import time
import multiprocessing as mp
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional, Any, Dict
from dotenv import load_dotenv

from langchain_community.document_loaders import PDFPlumberLoader, UnstructuredXMLLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_huggingface import HuggingFaceEmbeddings

from backend.tools.base.retriever_base import RetrievalChain
from backend.tools.http_embeddings import HTTPHuggingFaceEmbeddings
from tqdm import tqdm

import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress excessive logging from UnstructuredXMLLoader
logging.getLogger("unstructured").setLevel(logging.WARNING)
logging.getLogger("unstructured.partition").setLevel(logging.WARNING)
logging.getLogger("unstructured.cleaners").setLevel(logging.WARNING)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

class DocumentRetrievalChain(RetrievalChain):
    """Loads PDF/XML/Markdown documents, splits them, creates embeddings with Qwen3-Embedding-8B,
    stores them in Qdrant vector database, and provides retrieval functionalities.
    """
    def __init__(self, source_uris: List[str], persist_directory: Optional[str] = None, embedding_model: str = "text-embedding-3-small", chunk_size: int = 1000, chunk_overlap: int = 200, k: int = 5, **kwargs) -> None:
        super().__init__(**kwargs) # Pass remaining kwargs to base class

        # Per-worker file batch processing - check the list from a temp file (priority) or environment variable
        worker_batch_file = os.getenv("WORKER_FILE_BATCH_FILE", "")
        worker_batch = os.getenv("WORKER_FILE_BATCH", "")
        worker_files = None

        if worker_batch_file and os.path.exists(worker_batch_file):
            # Load file list line by line from the temp file (safe even if paths contain commas)
            with open(worker_batch_file, "r", encoding="utf-8") as bf:
                worker_files = [line.strip() for line in bf if line.strip()]
        elif worker_batch:
            # Backward compatibility: comma-separated environment variable
            worker_files = [f.strip() for f in worker_batch.split(",") if f.strip()]

        if worker_files is not None:
            # Set only the files this worker will process
            self.source_uris = worker_files

            # Always print for duplicate-processing prevention checks (regardless of logging level)
            worker_id = os.getenv("WORKER_ID", "0")
            gpu_id = os.getenv("GPU_ID", "0")
            print(f"📁 Worker {worker_id} (GPU {gpu_id}): confirmed batch of {len(worker_files):,} files")
            print(f"   First file: {worker_files[0] if worker_files else 'None'}")
            print(f"   Last file: {worker_files[-1] if worker_files else 'None'}")
        else:
            self.source_uris = source_uris
            print(f"⚠️  WORKER_FILE_BATCH environment variable not set - processing all files (risk of duplicates!)")

        self.persist_directory = persist_directory or "./vector_db" # Default directory
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.k = k
        self.retrievers: Dict[str, BaseRetriever] = {} # Initialize retrievers

    def _create_embedding_function(self, model_name_or_path: str) -> HuggingFaceEmbeddings | HTTPHuggingFaceEmbeddings:
        """Creates the embedding function with HTTP service option for Qwen3-Embedding-8B.
        Automatically supports CPU fallback when GPU OOM occurs.
        """
        enable_cpu_fallback = os.getenv("ENABLE_CPU_FALLBACK", "true").lower() in ["true", "1", "yes"]
        logger.info(f"Creating embedding function with model: {model_name_or_path}")

        try:
            # Check whether to use the HTTP embedding service
            use_http_service = os.getenv("EMBEDDING_SERVICE_ENABLED", "false").lower() in ["true", "1", "yes"]
            service_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

            if use_http_service and model_name_or_path == "Qwen/Qwen3-Embedding-8B":
                logger.info(f"🌐 Attempting to use HTTP embedding service: {service_url}")

                try:
                    # Create HTTP embedding service and run health check
                    http_embeddings = HTTPHuggingFaceEmbeddings(
                        model_name=model_name_or_path,
                        service_url=service_url,
                        timeout=60.0,
                        max_retries=3
                    )

                    # Check service availability
                    if http_embeddings.is_service_available():
                        logger.info("✅ HTTP embedding service connection successful!")
                        return http_embeddings
                    else:
                        logger.warning("⚠️  HTTP embedding service health check failed")

                except Exception as http_e:
                    logger.warning(f"⚠️  HTTP embedding service connection failed: {http_e}")

                # Fall back to local model if the HTTP service fails
                logger.info("📍 Falling back to local model...")

            if model_name_or_path == "Qwen/Qwen3-Embedding-8B":
                # Qwen3-Embedding-8B local processing (GPU optimization with CPU fallback)
                logger.info("Setting up Qwen3-Embedding-8B with local GPU acceleration...")
                self._setup_gpu_optimization()

                # Must use the HF_HOME/hub path (HuggingFace Hub cache structure)
                hf_home = os.getenv('HF_HOME')
                hf_cache_folder = os.path.join(hf_home, 'hub') if hf_home else None

                # Attempt GPU loading
                if torch.cuda.is_available():
                    gpu_device = f"cuda:{os.getenv('GPU_ID', '0')}"
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    logger.info(f"GPU memory cleared for embedding model loading")

                    model_kwargs = {
                        'device': gpu_device,
                        'trust_remote_code': True,
                    }

                    encode_kwargs = {
                        'batch_size': int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
                        'normalize_embeddings': True
                    }

                    try:
                        return HuggingFaceEmbeddings(
                            model_name=model_name_or_path,
                            cache_folder=hf_cache_folder,
                            model_kwargs=model_kwargs,
                            encode_kwargs=encode_kwargs
                        )
                    except (RuntimeError, torch.cuda.OutOfMemoryError) as gpu_error:
                        if enable_cpu_fallback:
                            logger.warning(f"⚠️  GPU OOM for embedding model: {gpu_error}")
                            logger.info("🔄 CPU fallback enabled - loading embedding model on CPU...")
                            torch.cuda.empty_cache()
                        else:
                            raise gpu_error

                # On CPU fallback or when CUDA is unavailable
                logger.info("📍 Loading embedding model on CPU...")
                model_kwargs = {
                    'device': 'cpu',
                    'trust_remote_code': True,
                }
                encode_kwargs = {
                    'batch_size': max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")) // 4),  # Reduce batch size on CPU
                    'normalize_embeddings': True
                }
                embeddings = HuggingFaceEmbeddings(
                    model_name=model_name_or_path,
                    cache_folder=hf_cache_folder,
                    model_kwargs=model_kwargs,
                    encode_kwargs=encode_kwargs
                )
                logger.info("✅ Embedding model loaded on CPU")
                return embeddings

            else:
                # Existing HuggingFace models (GPU with CPU fallback)
                hf_home = os.getenv('HF_HOME')
                hf_cache_folder = os.path.join(hf_home, 'hub') if hf_home else None

                if torch.cuda.is_available():
                    gpu_device = f"cuda:{os.getenv('GPU_ID', '0')}"
                    model_kwargs = {
                        'device': gpu_device,
                        'trust_remote_code': True
                    }

                    try:
                        return HuggingFaceEmbeddings(
                            model_name=model_name_or_path,
                            cache_folder=hf_cache_folder,
                            model_kwargs=model_kwargs,
                        )
                    except (RuntimeError, torch.cuda.OutOfMemoryError) as gpu_error:
                        if enable_cpu_fallback:
                            logger.warning(f"⚠️  GPU OOM for embedding model: {gpu_error}")
                            logger.info("🔄 CPU fallback enabled - loading embedding model on CPU...")
                            torch.cuda.empty_cache()
                        else:
                            raise gpu_error

                # On CPU fallback or when CUDA is unavailable
                logger.info("📍 Loading embedding model on CPU...")
                model_kwargs = {
                    'device': 'cpu',
                    'trust_remote_code': True
                }
                embeddings = HuggingFaceEmbeddings(
                    model_name=model_name_or_path,
                    cache_folder=hf_cache_folder,
                    model_kwargs=model_kwargs,
                )
                logger.info("✅ Embedding model loaded on CPU")
                return embeddings

        except Exception as e:
            raise ValueError(f"Failed to create embedding function: {e}")

    def _get_gpu_memory_info(self, gpu_id):
        """Retrieves memory info for a specific GPU and computes 80% of available memory"""
        import subprocess
        try:
            result = subprocess.run([
                'nvidia-smi', '--query-gpu=index,memory.total,memory.used,memory.free',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, check=True)

            for line in result.stdout.strip().split('\n'):
                idx, total, used, free = map(int, line.split(', '))
                if idx == gpu_id:
                    # Compute 80% of available memory in MB and convert to a PyTorch fraction
                    available_80_percent = free * 0.8
                    fraction = available_80_percent / total
                    return {
                        'total_mb': total,
                        'used_mb': used,
                        'free_mb': free,
                        'usable_mb': available_80_percent,
                        'fraction': min(fraction, 0.9)  # Cap at 90% maximum
                    }
        except Exception as e:
            logger.warning(f"Could not retrieve memory info for GPU {gpu_id}: {e}")
        return None

    def _setup_gpu_optimization(self):
        """Multi-GPU optimization setup - dynamically allocates 80% of available memory"""
        if torch.cuda.is_available():
            # Check whether this is a worker process - if so, skip GPU optimization (already done in main)
            is_worker = os.getenv("IS_WORKER") == "true"
            if is_worker:
                logger.info("Worker process - GPU optimization already done in main, skipping")
                return

            # Only the main process proceeds with GPU optimization
            num_gpus = torch.cuda.device_count()
            logger.info(f"🎮 {num_gpus} GPU(s) detected")

            # Determine the GPU ID for the current process (environment variable or default)
            process_gpu_id = int(os.getenv("GPU_ID", "0"))
            if process_gpu_id >= num_gpus:
                process_gpu_id = 0

            # Configure the designated GPU
            torch.cuda.set_device(process_gpu_id)
            torch.cuda.empty_cache()

            # Dynamic GPU memory allocation (main process only)
            memory_info = self._get_gpu_memory_info(process_gpu_id)
            if memory_info:
                torch.cuda.set_per_process_memory_fraction(memory_info['fraction'], device=process_gpu_id)
                logger.info(f"GPU {process_gpu_id}: allocated 80% ({memory_info['usable_mb']:,.0f}MB) of {memory_info['free_mb']:,}MB available memory")
                logger.info(f"GPU {process_gpu_id}: memory fraction = {memory_info['fraction']:.3f}")
            else:
                # Use a safe default if info cannot be retrieved
                torch.cuda.set_per_process_memory_fraction(0.6, device=process_gpu_id)
                logger.warning(f"GPU {process_gpu_id}: memory info unavailable - using default 60%")

            # H200 optimization settings
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

            # Set environment variables
            if os.getenv("PYTORCH_CUDA_ALLOC_CONF") is None:
                os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"

            logger.info(f"GPU optimization complete (process GPU {process_gpu_id}): {torch.cuda.get_device_name(process_gpu_id)}")
            logger.info(f"GPU memory: {torch.cuda.get_device_properties(process_gpu_id).total_memory / 1024**3:.1f}GB")

            # Print info for all GPUs
            for i in range(num_gpus):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                logger.info(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f}GB)")
        else:
            logger.warning("CUDA is not available. Running on CPU.")

    def _extract_academic_metadata(self, soup, file_path: str) -> dict:
        """Extracts academic metadata from PMC or PubMed XML"""
        metadata = {
            "source": file_path,
            "loader": "direct_xml_parsing_with_metadata"
        }

        try:
            # Determine XML format (content first, filename secondary) - independent of directory structure
            import os
            filename = os.path.basename(file_path)

            # First pass: content-based detection (most reliable method)
            is_pubmed_by_content = (
                soup.find('PubmedArticle') is not None or
                soup.find('PubmedArticleSet') is not None or
                soup.find('PMID') is not None
            )

            is_pmc_by_content = (
                soup.find('pmc-articleset') is not None or
                soup.find('article-meta') is not None or
                soup.find('article-id', {'pub-id-type': 'pmcid'}) is not None
            )

            # Re-check with ElementTree if BeautifulSoup failed
            if not is_pubmed_by_content and not is_pmc_by_content:
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    # Check PubMed structure with ElementTree
                    if (root.find('.//PMID') is not None or
                        root.find('.//PubmedArticle') is not None or
                        root.find('.//PubmedArticleSet') is not None):
                        is_pubmed_by_content = True

                    # Check PMC structure with ElementTree
                    elif (root.find('.//article-meta') is not None or
                          root.find('.//{http://dtd.nlm.nih.gov/2.0/xsd/archivearticle}article-meta') is not None or
                          root.find('.//article-id[@pub-id-type="pmcid"]') is not None):
                        is_pmc_by_content = True

                except Exception as et_error:
                    logger.debug(f"ElementTree fallback failed for {file_path}: {et_error}")
                    pass

            # Second pass: filename pattern-based detection (secondary)
            is_pubmed_by_filename = (
                filename.startswith(('10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20')) and
                not filename.startswith('PMC')  # Distinguish from PMC ID
            )

            is_pmc_by_filename = filename.startswith('PMC')

            # Final determination (content first, filename secondary)
            if is_pmc_by_content or (is_pmc_by_filename and not is_pubmed_by_content):
                is_pubmed = False
            elif is_pubmed_by_content or (is_pubmed_by_filename and not is_pmc_by_content):
                is_pubmed = True
            else:
                # Default when uncertain: PMC (allows extracting more fields)
                is_pubmed = False

            if is_pubmed:
                metadata = self._extract_pubmed_metadata(soup, file_path, metadata)
            else:
                metadata = self._extract_pmc_metadata(soup, file_path, metadata)

        except Exception as e:
            logger.debug(f"Error extracting metadata from {file_path}: {e}")

        return metadata

    def _extract_pmc_metadata(self, soup, file_path: str, metadata: dict) -> dict:
        """Extracts academic metadata from PMC XML"""
        try:
            metadata["xml_format"] = "PMC"

            # Extract title
            title_elem = soup.find('article-title')
            if title_elem:
                metadata["title"] = title_elem.get_text(strip=True)

            # Extract DOI
            doi_elem = soup.find('article-id', {'pub-id-type': 'doi'})
            if doi_elem:
                metadata["doi"] = doi_elem.get_text(strip=True)

            # Extract PMC ID
            pmc_elem = soup.find('article-id', {'pub-id-type': 'pmcid'})
            if pmc_elem:
                metadata["pmc_id"] = pmc_elem.get_text(strip=True)

            # Extract PMID
            pmid_elem = soup.find('article-id', {'pub-id-type': 'pmid'})
            if pmid_elem:
                metadata["pmid"] = pmid_elem.get_text(strip=True)

            # Extract authors
            authors = []
            contrib_elems = soup.find_all('contrib', {'contrib-type': 'author'})
            for contrib in contrib_elems:
                name_elem = contrib.find('name')
                if name_elem:
                    surname = name_elem.find('surname')
                    given_names = name_elem.find('given-names')
                    if surname and given_names:
                        author_name = f"{given_names.get_text(strip=True)} {surname.get_text(strip=True)}"
                        authors.append(author_name)

            if authors:
                metadata["authors"] = "; ".join(authors)
                metadata["first_author"] = authors[0]

            # Extract journal name
            journal_elem = soup.find('journal-title')
            if journal_elem:
                metadata["journal"] = journal_elem.get_text(strip=True)

            # Extract publication date
            pub_date_elem = soup.find('pub-date', {'pub-type': 'epub'}) or soup.find('pub-date')
            if pub_date_elem:
                year_elem = pub_date_elem.find('year')
                month_elem = pub_date_elem.find('month')
                day_elem = pub_date_elem.find('day')

                year = year_elem.get_text(strip=True) if year_elem else ""
                month = month_elem.get_text(strip=True).zfill(2) if month_elem else "01"
                day = day_elem.get_text(strip=True).zfill(2) if day_elem else "01"

                if year:
                    metadata["publication_date"] = f"{year}-{month}-{day}"
                    metadata["publication_year"] = year

            # Extract keywords
            keywords = []
            kwd_elems = soup.find_all('kwd')
            for kwd in kwd_elems:
                keyword = kwd.get_text(strip=True)
                if keyword:
                    keywords.append(keyword)

            if keywords:
                metadata["keywords"] = "; ".join(keywords)

            # Extract abstract
            abstract_elem = soup.find('abstract')
            if abstract_elem:
                abstract_text = abstract_elem.get_text(separator=' ', strip=True)
                if len(abstract_text) > 50:  # Only abstracts of meaningful length
                    metadata["abstract"] = abstract_text[:500] + "..." if len(abstract_text) > 500 else abstract_text

            # Extract PMC ID from filename
            import os
            filename = os.path.basename(file_path)
            if filename.startswith("PMC") and not metadata.get("pmc_id"):
                pmc_from_filename = filename.split("_")[0]
                metadata["pmc_id"] = pmc_from_filename

        except Exception as e:
            logger.debug(f"Error extracting PMC metadata from {file_path}: {e}")

        return metadata

    def _extract_pubmed_metadata(self, soup, file_path: str, metadata: dict) -> dict:
        """Extracts academic metadata from PubMed XML (uses ElementTree)"""
        try:
            import xml.etree.ElementTree as ET

            metadata["xml_format"] = "PubMed"

            # Re-parse with ElementTree (more stable)
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract title
            title_elem = root.find('.//ArticleTitle')
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()

            # Extract PMID
            pmid_elem = root.find('.//PMID')
            if pmid_elem is not None and pmid_elem.text:
                metadata["pmid"] = pmid_elem.text.strip()

            # Extract DOI
            doi_elem = root.find('.//ArticleId[@IdType="doi"]')
            if doi_elem is not None and doi_elem.text:
                metadata["doi"] = doi_elem.text.strip()

            # Extract authors
            authors = []
            author_elems = root.findall('.//Author[@ValidYN="Y"]')
            for author in author_elems:
                last_name_elem = author.find('LastName')
                first_name_elem = author.find('ForeName')
                if (last_name_elem is not None and last_name_elem.text and
                    first_name_elem is not None and first_name_elem.text):
                    author_name = f"{first_name_elem.text.strip()} {last_name_elem.text.strip()}"
                    authors.append(author_name)

            if authors:
                metadata["authors"] = "; ".join(authors)
                metadata["first_author"] = authors[0]

            # Extract journal name
            journal_elem = root.find('.//Journal/Title')
            if journal_elem is not None and journal_elem.text:
                metadata["journal"] = journal_elem.text.strip()

            # Extract publication date
            pub_date_elem = root.find('.//PubDate')
            if pub_date_elem is not None:
                year_elem = pub_date_elem.find('Year')
                month_elem = pub_date_elem.find('Month')
                day_elem = pub_date_elem.find('Day')

                year = year_elem.text.strip() if year_elem is not None and year_elem.text else ""
                month = month_elem.text.strip() if month_elem is not None and month_elem.text else ""
                day = day_elem.text.strip() if day_elem is not None and day_elem.text else ""

                if year:
                    # Convert month name to a number
                    month_names = {
                        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                    }
                    month_num = month_names.get(month, month)
                    if month_num.isdigit():
                        month_num = month_num.zfill(2)
                    else:
                        month_num = "01"

                    day_num = day.zfill(2) if day.isdigit() else "01"
                    metadata["publication_date"] = f"{year}-{month_num}-{day_num}"
                    metadata["publication_year"] = year

            # Extract abstract
            abstract_elem = root.find('.//AbstractText')
            if abstract_elem is not None and abstract_elem.text:
                abstract_text = abstract_elem.text.strip()
                if len(abstract_text) > 50:
                    metadata["abstract"] = abstract_text[:500] + "..." if len(abstract_text) > 500 else abstract_text

            # Extract MeSH keywords
            mesh_keywords = []
            mesh_elems = root.findall('.//DescriptorName')
            for mesh in mesh_elems[:10]:  # First 10 only
                if mesh.text:
                    keyword = mesh.text.strip()
                    if keyword:
                        mesh_keywords.append(keyword)

            if mesh_keywords:
                metadata["mesh_keywords"] = "; ".join(mesh_keywords)

            # Extract PMID from filename
            import os
            filename = os.path.basename(file_path)
            if filename[0].isdigit() and not metadata.get("pmid"):
                pmid_from_filename = filename.split("_")[0]
                metadata["pmid"] = pmid_from_filename

        except Exception as e:
            logger.debug(f"Error extracting PubMed metadata from {file_path}: {e}")

        return metadata

    def _load_xml_directly(self, file_path: str) -> List[Document]:
        """Directly parses an XML file to extract text along with academic metadata."""
        try:
            # Use BeautifulSoup (more lenient parsing)
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # XML parsing (use the lxml parser, fall back to html.parser on failure)
            try:
                soup = BeautifulSoup(content, 'xml')
            except:
                soup = BeautifulSoup(content, 'html.parser')

            # Extract academic metadata
            metadata = self._extract_academic_metadata(soup, file_path)

            # Extract all text (remove tags, preserve all content)
            extracted_text = soup.get_text(separator=' ', strip=True)

            # Add text length info
            metadata["original_length"] = len(extracted_text)

            # Create a Document if the text is not empty
            if extracted_text and len(extracted_text.strip()) > 10:
                return [Document(
                    page_content=extracted_text,
                    metadata=metadata
                )]
            else:
                logger.debug(f"Empty content after XML parsing: {file_path}")
                return []

        except Exception as e:
            logger.error(f"Direct XML parsing failed for {file_path}: {e}")
            # fallback to UnstructuredXMLLoader
            try:
                loader = UnstructuredXMLLoader(file_path, strategy="fast")
                docs = loader.load()
                # Add basic metadata even on fallback
                if docs:
                    for doc in docs:
                        doc.metadata.update({
                            "source": file_path,
                            "loader": "unstructured_xml_fallback"
                        })
                return docs
            except:
                return []

    def _load_and_split_docs_multiprocessing(self, uris_to_process: List[str], embedding_model: HuggingFaceEmbeddings) -> List[Document]:
        """Loads and splits large-scale documents using multiprocessing (single-threaded in worker processes)."""
        total_files = len(uris_to_process)

        # Check whether this is a worker process - if so, do not use multiprocessing (daemon processes cannot spawn children)
        is_worker = os.getenv("IS_WORKER") == "true"

        if is_worker:
            logger.info(f"🔧 Worker process: processing {total_files:,} documents single-threaded")
            # In worker processes, process single-threaded (multiprocessing prohibited)
            all_documents = []
            failed_files = []

            for i, uri in enumerate(uris_to_process):
                max_retries = 3
                retry_count = 0

                while retry_count < max_retries:
                    try:
                        # Process a single file as a batch (using the static method)
                        docs = DocumentRetrievalChain._process_file_batch([uri], self.chunk_size, self.chunk_overlap)
                        all_documents.extend(docs)
                        break  # End the retry loop on success

                    except Exception as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"⚠️  File processing failed (retry {retry_count}/{max_retries}) {uri}: {e}")
                            time.sleep(1)  # Wait 1 second before retrying
                        else:
                            logger.error(f"❌ File processing finally failed {uri}: {e}")
                            failed_files.append(uri)

                if (i + 1) % 1000 == 0:
                    logger.info(f"📄 Worker progress: {i+1}/{total_files} files processed (failed: {len(failed_files)})")

            if failed_files:
                logger.error(f"❌ {len(failed_files)} files failed to process in worker process:")
                for failed_file in failed_files:
                    logger.error(f"   - {failed_file}")
                # Raise an exception if any files failed (for accurate document processing)
                raise RuntimeError(f"{len(failed_files)} files failed to process in worker process. Aborted for accurate indexing.")

            logger.info(f"✅ Worker process complete: {len(all_documents):,} documents processed")
            return all_documents

        # Use multiprocessing in the main process
        if total_files > 50000:
            logger.info(f"🚀 Starting processing of {total_files:,} documents with multiprocessing")
        else:
            logger.info(f"Processing {total_files:,} documents with multiprocessing")

        # Determine number of workers based on CPU core count (increased to max 12)
        num_workers = min(mp.cpu_count(), 12)
        logger.info(f"🔧 Available CPU cores: {mp.cpu_count()}, workers to use: {num_workers}")

        # Divide files into batches (small batches prioritizing stability)
        batch_size = max(200, min(800, total_files // (num_workers * 50)))  # Limit to 200-800 range
        file_batches = [uris_to_process[i:i + batch_size] for i in range(0, total_files, batch_size)]

        logger.info(f"📦 Split into {len(file_batches)} batches (~{batch_size} files per batch)")

        all_documents = []
        failed_batches = []

        # Parallel processing with ProcessPoolExecutor (main process only)
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Process each batch in a separate process
            future_to_batch = {
                executor.submit(self._process_file_batch, batch, self.chunk_size, self.chunk_overlap): i
                for i, batch in enumerate(file_batches)
            }

            # Progress display
            completed_batches = 0
            total_batches = len(file_batches)

            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                max_retries = 2
                retry_count = 0

                while retry_count <= max_retries:
                    try:
                        batch_documents = future.result(timeout=300)  # 5-minute timeout
                        all_documents.extend(batch_documents)
                        completed_batches += 1

                        logger.info(f"✅ Batch {batch_idx + 1}/{total_batches} complete "
                                   f"(cumulative documents: {len(all_documents):,})")
                        break

                    except Exception as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning(f"⚠️  Batch {batch_idx + 1} failed (retry {retry_count}/{max_retries}): {e}")
                            # Retry the batch
                            batch = file_batches[batch_idx]
                            future = executor.submit(self._process_file_batch, batch, self.chunk_size, self.chunk_overlap)
                        else:
                            logger.error(f"❌ Batch {batch_idx + 1} finally failed: {e}")
                            failed_batches.append((batch_idx, file_batches[batch_idx]))

        if failed_batches:
            failed_files_count = sum(len(batch[1]) for batch in failed_batches)
            logger.error(f"❌ {len(failed_batches)} batches ({failed_files_count} files) failed to process")
            for batch_idx, batch_files in failed_batches:
                logger.error(f"   Batch {batch_idx + 1}: {len(batch_files)} files")
            raise RuntimeError(f"{len(failed_batches)} batches failed to process. Aborted for accurate indexing.")

        logger.info(f"🎉 Multiprocessing complete: {len(all_documents):,} documents processed in total")
        return all_documents

    def _load_and_split_docs(self, uris_to_process: List[str], embedding_model: HuggingFaceEmbeddings) -> List[Document]:
        """Loads documents from URIs and splits them into chunks (optimized for large datasets)."""
        documents = []
        total_files = len(uris_to_process)

        if total_files > 50000:
            logger.info(f"🚀 Loading {total_files:,} documents (large-scale processing)")
        else:
            logger.info(f"Loading {total_files:,} documents.")

        # Display tqdm progress with a unique position per worker process
        worker_id = os.getenv("WORKER_ID", "0")
        gpu_id = os.getenv("GPU_ID", "0")

        # Optimize progress display for large-scale data (separate line per worker)
        position_offset = int(worker_id) + 20  # Start at 20 to avoid overlapping with the indexing tqdm
        progress_bar = tqdm(uris_to_process,
                           desc=f"📄 GPU {gpu_id} Worker {worker_id} Loading",
                           unit="files",
                           unit_scale=True, position=position_offset, leave=False,
                           ncols=120, bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} files [{elapsed}<{remaining}, {rate_fmt}]")

        failed_documents = []

        for uri in progress_bar:
            try:
                file_extension = os.path.splitext(uri)[1].lower()
                if file_extension == ".pdf":
                    loader = PDFPlumberLoader(uri)
                elif file_extension == ".xml":
                    # Preserve 100% of text via direct XML parsing
                    doc = self._load_xml_directly(uri)
                    if doc:
                        for page_doc in doc:
                            page_doc.metadata["source"] = uri
                        documents.extend(doc)
                    continue  # Skip the generic loader
                elif file_extension == ".md":
                    loader = UnstructuredMarkdownLoader(uri)
                else:
                    logger.warning(f"Unsupported file type: {file_extension} for uri {uri}. Skipping.")
                    continue # Skip unsupported file types.

                doc = loader.load()
                if doc:
                    # Add source metadata to each document chunk later
                    # We add it here to the initial documents loaded
                    for page_doc in doc:
                        page_doc.metadata["source"] = uri # Store the original file URI
                        page_doc.page_content = page_doc.page_content.replace("\n", " ")

                        # Add basic academic metadata to PDF/MD files
                        if file_extension == ".pdf":
                            page_doc.metadata["document_type"] = "PDF Document"
                            # Attempt to extract info from the PDF filename
                            filename = os.path.basename(uri)
                            if "_" in filename:
                                # Analyze filename pattern (e.g., PMC123_Title_Keywords.pdf)
                                parts = filename.replace(".pdf", "").split("_")
                                if parts[0].startswith("PMC"):
                                    page_doc.metadata["pmc_id"] = parts[0]
                                if len(parts) > 1:
                                    page_doc.metadata["title"] = " ".join(parts[1:]).replace("_", " ")

                        elif file_extension == ".md":
                            page_doc.metadata["document_type"] = "Markdown Document"
                            # Attempt to extract title from the markdown file
                            content_lines = page_doc.page_content.split('\n')[:5]  # Check only the first 5 lines
                            for line in content_lines:
                                if line.strip().startswith('#'):
                                    title_text = line.strip().lstrip('#').strip()
                                    if len(title_text) > 5:
                                        page_doc.metadata["title"] = title_text
                                        break
                    documents.extend(doc)

                    # Memory management for large-scale processing - garbage collect every 10,000 documents
                    if len(documents) % 10000 == 0 and len(documents) > 0:
                        logger.debug(f"Memory management: Processed {len(documents)} documents so far")
                        import gc
                        gc.collect()  # Run garbage collection
                else:
                    logger.warning(f"No documents loaded from {uri}")
            except Exception as e:
                logger.error(f"❌ Document load finally failed {uri}: {e}")
                failed_documents.append(uri)

        # Check for failed documents
        if failed_documents:
            logger.error(f"❌ {len(failed_documents)} documents failed to load:")
            for failed_doc in failed_documents[:10]:  # Log only the first 10
                logger.error(f"   - {failed_doc}")
            if len(failed_documents) > 10:
                logger.error(f"   ... and {len(failed_documents) - 10} more")
            raise RuntimeError(f"{len(failed_documents)} documents failed to load. Aborted for accurate indexing.")

        if not documents:
            logger.warning("No documents were loaded successfully.")
            return []

        # text_splitter = SemanticChunker(embedding_model) # - too many API requests can get the API requests rejected
        text_splitter = RecursiveCharacterTextSplitter(chunk_size = self.chunk_size, chunk_overlap = self.chunk_overlap)
        split_docs_raw = text_splitter.split_documents(documents)
        logger.info(f"Split {len(documents)} documents into {len(split_docs_raw)} raw chunks.")

        final_split_docs = []
        chunks_per_source: Dict[str, int] = {} # Chunk counter per source

        for chunk_doc in split_docs_raw:
            source = chunk_doc.metadata.get("source")
            if source:
                # Compute and update the chunk number for that source
                chunk_index = chunks_per_source.get(source, 0)
                chunks_per_source[source] = chunk_index + 1

                # Add chunk_id to metadata
                chunk_doc.metadata["chunk_id"] = f"chunk_{chunk_index:03d}" # e.g., chunk_000, chunk_001
                final_split_docs.append(chunk_doc)
            else:
                logger.warning("Chunk document missing 'source' metadata, skipping.")
                # Add logic here to handle chunks without a source if needed

        logger.info(f"Added unique chunk IDs to {len(final_split_docs)} chunks.")

        # Log sample metadata (only the first few)
        if final_split_docs and logger.isEnabledFor(logging.INFO):
            sample_doc = final_split_docs[0]
            sample_metadata = {k: v for k, v in sample_doc.metadata.items() if k != "source"}
            logger.info(f"📋 Sample metadata extracted: {list(sample_metadata.keys())}")
            if sample_metadata.get("title"):
                logger.debug(f"   📖 Title: {sample_metadata['title'][:100]}...")
            if sample_metadata.get("authors"):
                logger.debug(f"   👥 Authors: {sample_metadata['authors'][:100]}...")
            if sample_metadata.get("doi"):
                logger.debug(f"   🔗 DOI: {sample_metadata['doi']}")

        return final_split_docs # Return the list of chunks with unique IDs added

    @staticmethod
    def _extract_academic_metadata_static(soup, file_path: str) -> dict:
        """Static method: extracts academic metadata from PMC or PubMed XML (for multiprocessing)"""
        metadata = {
            "source": file_path,
            "loader": "direct_xml_parsing_with_metadata"
        }

        try:
            # Determine XML format (content first, filename secondary) - independent of directory structure
            import os
            filename = os.path.basename(file_path)

            # First pass: content-based detection (most reliable method)
            is_pubmed_by_content = (
                soup.find('PubmedArticle') is not None or
                soup.find('PubmedArticleSet') is not None or
                soup.find('PMID') is not None
            )

            is_pmc_by_content = (
                soup.find('pmc-articleset') is not None or
                soup.find('article-meta') is not None or
                soup.find('article-id', {'pub-id-type': 'pmcid'}) is not None
            )

            # Re-check with ElementTree if BeautifulSoup failed
            if not is_pubmed_by_content and not is_pmc_by_content:
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    # Check PubMed structure with ElementTree
                    if (root.find('.//PMID') is not None or
                        root.find('.//PubmedArticle') is not None or
                        root.find('.//PubmedArticleSet') is not None):
                        is_pubmed_by_content = True

                    # Check PMC structure with ElementTree
                    elif (root.find('.//article-meta') is not None or
                          root.find('.//{http://dtd.nlm.nih.gov/2.0/xsd/archivearticle}article-meta') is not None or
                          root.find('.//article-id[@pub-id-type="pmcid"]') is not None):
                        is_pmc_by_content = True

                except Exception as et_error:
                    logger.debug(f"ElementTree fallback failed for {file_path}: {et_error}")
                    pass

            # Second pass: filename pattern-based detection (secondary)
            is_pubmed_by_filename = (
                filename.startswith(('10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20')) and
                not filename.startswith('PMC')  # Distinguish from PMC ID
            )

            is_pmc_by_filename = filename.startswith('PMC')

            # Final determination (content first, filename secondary)
            if is_pmc_by_content or (is_pmc_by_filename and not is_pubmed_by_content):
                is_pubmed = False
            elif is_pubmed_by_content or (is_pubmed_by_filename and not is_pmc_by_content):
                is_pubmed = True
            else:
                # Default when uncertain: PMC (allows extracting more fields)
                is_pubmed = False

            if is_pubmed:
                # ElementTree parsing for PubMed XML (simplified version for multiprocessing)
                import xml.etree.ElementTree as ET
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    metadata["xml_format"] = "PubMed"

                    # Extract title
                    title_elem = root.find('.//ArticleTitle')
                    if title_elem is not None and title_elem.text:
                        metadata["title"] = title_elem.text.strip()

                    # Extract PMID
                    pmid_elem = root.find('.//PMID')
                    if pmid_elem is not None and pmid_elem.text:
                        metadata["pmid"] = pmid_elem.text.strip()

                    # Extract DOI
                    doi_elem = root.find('.//ArticleId[@IdType="doi"]')
                    if doi_elem is not None and doi_elem.text:
                        metadata["doi"] = doi_elem.text.strip()

                    # Extract authors (first 5 only - for performance)
                    authors = []
                    author_elems = root.findall('.//Author[@ValidYN="Y"]')[:5]
                    for author in author_elems:
                        last_name_elem = author.find('LastName')
                        first_name_elem = author.find('ForeName')
                        if (last_name_elem is not None and last_name_elem.text and
                            first_name_elem is not None and first_name_elem.text):
                            author_name = f"{first_name_elem.text.strip()} {last_name_elem.text.strip()}"
                            authors.append(author_name)

                    if authors:
                        metadata["authors"] = "; ".join(authors)
                        metadata["first_author"] = authors[0]

                    # Extract journal name
                    journal_elem = root.find('.//Journal/Title')
                    if journal_elem is not None and journal_elem.text:
                        metadata["journal"] = journal_elem.text.strip()

                    # Extract publication year (simplified)
                    pub_date_elem = root.find('.//PubDate/Year')
                    if pub_date_elem is not None and pub_date_elem.text:
                        metadata["publication_year"] = pub_date_elem.text.strip()

                    # Extract MeSH keywords (first 3 only)
                    mesh_keywords = []
                    mesh_elems = root.findall('.//DescriptorName')[:3]
                    for mesh in mesh_elems:
                        if mesh.text:
                            keyword = mesh.text.strip()
                            if keyword:
                                mesh_keywords.append(keyword)

                    if mesh_keywords:
                        metadata["mesh_keywords"] = "; ".join(mesh_keywords)

                    # Extract PMID from filename
                    import os
                    filename = os.path.basename(file_path)
                    if filename[0].isdigit() and not metadata.get("pmid"):
                        pmid_from_filename = filename.split("_")[0]
                        metadata["pmid"] = pmid_from_filename

                except:
                    # Set default value if ElementTree parsing fails
                    metadata["xml_format"] = "PubMed"

            else:
                # PMC format processing
                metadata["xml_format"] = "PMC"

                # Extract title
                title_elem = soup.find('article-title')
                if title_elem:
                    metadata["title"] = title_elem.get_text(strip=True)

                # Extract DOI
                doi_elem = soup.find('article-id', {'pub-id-type': 'doi'})
                if doi_elem:
                    metadata["doi"] = doi_elem.get_text(strip=True)

                # Extract PMC ID
                pmc_elem = soup.find('article-id', {'pub-id-type': 'pmcid'})
                if pmc_elem:
                    metadata["pmc_id"] = pmc_elem.get_text(strip=True)

                # Extract PMID
                pmid_elem = soup.find('article-id', {'pub-id-type': 'pmid'})
                if pmid_elem:
                    metadata["pmid"] = pmid_elem.get_text(strip=True)

                # Extract authors (simple version - for performance)
                authors = []
                contrib_elems = soup.find_all('contrib', {'contrib-type': 'author'})[:10]
                for contrib in contrib_elems:
                    name_elem = contrib.find('name')
                    if name_elem:
                        surname = name_elem.find('surname')
                        given_names = name_elem.find('given-names')
                        if surname and given_names:
                            author_name = f"{given_names.get_text(strip=True)} {surname.get_text(strip=True)}"
                            authors.append(author_name)

                if authors:
                    metadata["authors"] = "; ".join(authors)
                    metadata["first_author"] = authors[0]

                # Extract journal name
                journal_elem = soup.find('journal-title')
                if journal_elem:
                    metadata["journal"] = journal_elem.get_text(strip=True)

                # Extract publication year (simple version)
                pub_date_elem = soup.find('pub-date', {'pub-type': 'epub'}) or soup.find('pub-date')
                if pub_date_elem:
                    year_elem = pub_date_elem.find('year')
                    if year_elem:
                        metadata["publication_year"] = year_elem.get_text(strip=True)

                # Extract keywords (first 5 only)
                keywords = []
                kwd_elems = soup.find_all('kwd')[:5]
                for kwd in kwd_elems:
                    keyword = kwd.get_text(strip=True)
                    if keyword:
                        keywords.append(keyword)

                if keywords:
                    metadata["keywords"] = "; ".join(keywords)

                # Extract PMC ID from filename (fallback)
                import os
                filename = os.path.basename(file_path)
                if filename.startswith("PMC") and not metadata.get("pmc_id"):
                    pmc_from_filename = filename.split("_")[0]
                    metadata["pmc_id"] = pmc_from_filename

        except Exception as e:
            # Silently continue in multiprocessing
            pass

        return metadata

    @staticmethod
    def _load_xml_directly_static(file_path: str) -> List[Document]:
        """Static method: directly parses an XML file to extract text along with academic metadata (for multiprocessing)."""
        try:
            from bs4 import BeautifulSoup
            from langchain_core.documents import Document

            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # XML parsing with BeautifulSoup (preserve all text)
            try:
                soup = BeautifulSoup(content, 'xml')
            except:
                soup = BeautifulSoup(content, 'html.parser')

            # Extract academic metadata
            metadata = DocumentRetrievalChain._extract_academic_metadata_static(soup, file_path)

            # Extract text
            extracted_text = soup.get_text(separator=' ', strip=True)

            # Add text length info
            metadata["original_length"] = len(extracted_text)

            if extracted_text and len(extracted_text.strip()) > 10:
                return [Document(
                    page_content=extracted_text,
                    metadata=metadata
                )]
            return []
        except Exception as e:
            return []

    @staticmethod
    def _process_file_batch(file_batch: List[str], chunk_size: int, chunk_overlap: int) -> List[Document]:
        """Static method: worker function that processes a batch of files (for multiprocessing)."""
        import os
        import logging
        from langchain_community.document_loaders import PDFPlumberLoader, UnstructuredMarkdownLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document

        # Configure logging in each process (suppress excessive logging)
        logging.getLogger("unstructured").setLevel(logging.ERROR)
        logging.getLogger("unstructured.partition").setLevel(logging.ERROR)
        logging.getLogger("unstructured.cleaners").setLevel(logging.ERROR)

        documents = []

        for uri in file_batch:
            try:
                file_extension = os.path.splitext(uri)[1].lower()
                if file_extension == ".pdf":
                    loader = PDFPlumberLoader(uri)
                    doc = loader.load()
                    if doc:
                        for page_doc in doc:
                            page_doc.metadata["source"] = uri
                            page_doc.page_content = page_doc.page_content.replace("\n", " ")

                            # Add basic academic metadata to PDF files (for multiprocessing)
                            page_doc.metadata["document_type"] = "PDF Document"
                            filename = os.path.basename(uri)
                            if "_" in filename:
                                parts = filename.replace(".pdf", "").split("_")
                                if parts[0].startswith("PMC"):
                                    page_doc.metadata["pmc_id"] = parts[0]
                                if len(parts) > 1:
                                    page_doc.metadata["title"] = " ".join(parts[1:]).replace("_", " ")
                        documents.extend(doc)

                elif file_extension == ".xml":
                    # Preserve 100% of text via direct XML parsing (for multiprocessing)
                    xml_docs = DocumentRetrievalChain._load_xml_directly_static(uri)
                    if xml_docs:
                        for page_doc in xml_docs:
                            page_doc.metadata["source"] = uri
                            # XML preserves line breaks (retains structure info)
                        documents.extend(xml_docs)

                elif file_extension == ".md":
                    loader = UnstructuredMarkdownLoader(uri)
                    doc = loader.load()
                    if doc:
                        for page_doc in doc:
                            page_doc.metadata["source"] = uri
                            page_doc.page_content = page_doc.page_content.replace("\n", " ")

                            # Add basic academic metadata to MD files (for multiprocessing)
                            page_doc.metadata["document_type"] = "Markdown Document"
                            content_lines = page_doc.page_content.split('\n')[:5]
                            for line in content_lines:
                                if line.strip().startswith('#'):
                                    title_text = line.strip().lstrip('#').strip()
                                    if len(title_text) > 5:
                                        page_doc.metadata["title"] = title_text
                                        break
                        documents.extend(doc)
                else:
                    continue  # Skip unsupported file types

            except Exception as e:
                # Silently skip in multiprocessing
                pass

        # Perform text splitting for each batch
        if documents:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            split_docs_raw = text_splitter.split_documents(documents)

            # Add chunk IDs
            final_split_docs = []
            chunks_per_source = {}

            for chunk_doc in split_docs_raw:
                source = chunk_doc.metadata.get("source")
                if source:
                    chunk_index = chunks_per_source.get(source, 0)
                    chunks_per_source[source] = chunk_index + 1
                    chunk_doc.metadata["chunk_id"] = f"chunk_{chunk_index:03d}"
                    final_split_docs.append(chunk_doc)

            return final_split_docs

        return []

    def _load_or_create_vector_store(self, embedding_function) -> QdrantVectorStore:
        """Loads or creates a Qdrant vector store."""
        try:
            # Qdrant client configuration (improved timeout and stability)
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
            timeout_seconds = float(os.getenv("QDRANT_TIMEOUT", "120.0"))  # 120 seconds to account for model loading

            client = QdrantClient(
                host=qdrant_host,
                port=qdrant_port,
                api_key=os.getenv("QDRANT_API_KEY", None),  # When using the cloud
                timeout=timeout_seconds,
                prefer_grpc=False,  # Use HTTP for improved stability
            )

            logger.info(f"Qdrant client configured: {qdrant_host}:{qdrant_port}, timeout: {timeout_seconds}s")

            # Collection name configuration (get RDA from .env)
            collection_name = os.getenv("QDRANT_COLLECTION", "personaai_rag")

            logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}, collection: {collection_name}")

            # Check whether the collection exists and create it (handle race conditions)
            from qdrant_client.models import Distance, VectorParams
            import time as _time

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    collection_info = client.get_collection(collection_name)
                    logger.info(f"✅ Existing collection found: {collection_name} ({collection_info.points_count:,} points)")
                    break  # Success if the collection exists
                except Exception as get_err:
                    # Attempt to create the collection if it does not exist
                    vector_size = 4096 if self.embedding_model == "Qwen/Qwen3-Embedding-8B" else 1536

                    try:
                        logger.info(f"🔧 Creating collection: {collection_name} (vector dimension: {vector_size})")
                        client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=vector_size,
                                distance=Distance.COSINE
                            )
                        )
                        logger.info(f"✅ New collection created: {collection_name}")
                        break  # Creation successful
                    except Exception as create_err:
                        # 409 Conflict = another worker already created it -> retry
                        if "already exists" in str(create_err) or "409" in str(create_err):
                            logger.info(f"⏳ Collection created by another worker, retrying... ({attempt + 1}/{max_retries})")
                            _time.sleep(0.5)  # Wait briefly before retrying
                            continue
                        else:
                            raise create_err
            else:
                # If all retries fail, try get one last time
                collection_info = client.get_collection(collection_name)
                logger.info(f"✅ Collection confirmed after retries: {collection_name} ({collection_info.points_count:,} points)")

            # Create QdrantVectorStore (works around a LangChain bug)
            vector_store = QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=embedding_function,
                validate_collection_config=False  # Disable all validation to work around the bug
            )

            logger.info(f"Qdrant vector store initialized: collection='{collection_name}'")
            return vector_store

        except Exception as e:
            logger.error(f"Failed to load or initialize Qdrant: {e}", exc_info=True)
            raise ValueError(f"Qdrant initialization failed: {e}") from e

    def _create_retrievers(self, vector_store: QdrantVectorStore) -> Dict[str, BaseRetriever]:
        """Creates different types of retrievers from the vector store."""
        retriever_dict = {}
        try:
            semantic_retriever = vector_store.as_retriever(search_kwargs={"k": self.k})
            retriever_dict["semantic"] = semantic_retriever
            logger.info("Semantic retriever created successfully.")
        except Exception as e:
            logger.error(f"Failed to create semantic retriever: {e}", exc_info=True)
            # semantic_retriever = None # Indicate failure if needed
        # Add other retriever types (keyword, hybrid) here if needed
        return retriever_dict

    # --- Add implementations for the missing abstract methods ---
    def load_documents(self, source_uris: List[str]) -> List[Document]:
        """
        (Abstract method implementation)
        Loads documents from source URIs.
        Note: Primarily used internally by initialize now.
        """
        logger.debug("load_documents called, but initialization handles loading.")
        return []

    def create_text_splitter(self) -> RecursiveCharacterTextSplitter:
        """
        (Abstract method implementation)
        Creates the text splitter.
        """
        return RecursiveCharacterTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)

    def create_vectorstore(self) -> QdrantVectorStore:
        """
        (Abstract method implementation)
        Loads or creates the vector store.
        Note: Primarily used internally by initialize now.
        """
        embedding_function = self._create_embedding_function(self.embedding_model)
        return self._load_or_create_vector_store(embedding_function)
    # ------------------------------------

    def initialize(self, index: bool = True) -> "DocumentRetrievalChain":
        """
        Initializes the DocumentRetrievalChain. Loads an existing vector store
        or creates a new one if it doesn't exist. Indexes only new documents
        found in the source_uris that are not already in the vector store.

        If index=False, skips embedding/indexing and only builds the retriever.
        (Prevents re-embedding already-processed files during a post-indexing
         verification init, which would create duplicate points in Qdrant.)
        """
        logger.info("Initializing retrieval chain for incremental updates...")

        # Actual throughput statistics (tracked so workers can report accurate processing results)
        self.requested_file_count = len(self.source_uris)
        self.total_chunk_count = 0      # Number of chunks created
        self.indexed_chunk_count = 0    # Number of chunks successfully added to Qdrant
        self.failed_batch_count = 0     # Number of batches that finally failed

        # --- Common: initialize the vector store (shared by all processes) ---
        embedding_function = self._create_embedding_function(self.embedding_model)
        vector_store = self._load_or_create_vector_store(embedding_function)

        # Worker processes skip the duplicate check and process directly
        is_worker = os.getenv("IS_WORKER") == "true"
        if not index:
            # Verification/result-checking init: build the retriever only, do not (re-)embed.
            logger.info("index=False: skipping indexing, building retriever only.")
            new_files_to_index = []
        elif is_worker:
            worker_id = os.getenv("WORKER_ID", "0")
            gpu_id = os.getenv("GPU_ID", "0")
            print(f"📊 Worker {worker_id} (GPU {gpu_id}) processing assignment:")
            print(f"  📁 Assigned files: {len(self.source_uris):,} (filtered in main)")
            print(f"  🆕 All scheduled for new processing: {len(self.source_uris):,}")

            # Already filtered in main, so process all files as new files
            new_files_to_index = self.source_uris
        else:
            # The main process also skips the duplicate check (already filtered in run_full_indexing.py)
            print("🔧 Main process: processing files already filtered in run_full_indexing.py")
            new_files_to_index = self.source_uris
            print(f"🔧 Main process: starting to process {len(new_files_to_index):,} files")

        # --- Common: index new files (shared by worker/main) ---
        if new_files_to_index:
            logger.info(f"Found {len(new_files_to_index)} new documents to index.")
            try:
                # Multiprocessing for large files, default method for small ones
                if len(new_files_to_index) > 1000:
                    logger.info("🚀 Large-scale data detected: enabling multiprocessing mode")
                    new_documents = self._load_and_split_docs_multiprocessing(new_files_to_index, embedding_function)
                else:
                    logger.info("📄 Small-scale data: default processing mode")
                    new_documents = self._load_and_split_docs(new_files_to_index, embedding_function)
                if new_documents:
                    total_chunks = len(new_documents)
                    self.total_chunk_count = total_chunks
                    # Dynamic batch size for large-scale data (considering collection stability)
                    if total_chunks > 100000:  # More than 100,000
                        batch_size = 25   # Smaller for stability
                    elif total_chunks > 10000:  # More than 10,000
                        batch_size = 50   # Medium size
                    else:
                        batch_size = 100  # Moderate for small volumes

                    logger.info(f"Adding {total_chunks:,} new document chunks to Qdrant in batches of {batch_size}...")
                    logger.info(f"⏱️  Estimated processing time: {(total_chunks // batch_size) * 0.5:.1f} - {(total_chunks // batch_size) * 2:.1f} seconds")

                    # Display tqdm progress with a unique position per worker process
                    worker_id = os.getenv("WORKER_ID", "0")
                    gpu_id = os.getenv("GPU_ID", "0")

                    # Display batch processing progress with tqdm (separate line per worker)
                    position_offset = int(worker_id) + 10  # Start position at 10 to separate from other output
                    with tqdm(total=total_chunks, desc=f"🚀 GPU {gpu_id} Worker {worker_id}",
                            unit="chunks", unit_scale=True, position=position_offset, leave=False,
                            ncols=120, bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} chunks [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
                        # Process the new_documents list in batches of batch_size
                        for i in range(0, total_chunks, batch_size):
                            batch = new_documents[i:i + batch_size]

                            # Retry logic (handle collection issues)
                            max_retries = 3
                            retry_count = 0

                            while retry_count < max_retries:
                                try:
                                    # Check collection status (on the first batch or when an error occurs)
                                    if i == 0 or retry_count > 0:
                                        try:
                                            collection_info = vector_store.client.get_collection(vector_store.collection_name)
                                        except:
                                            # Recreate the collection if it disappeared
                                            logger.warning(f"Collection disappeared. Recreating: {vector_store.collection_name}")
                                            from qdrant_client.models import Distance, VectorParams
                                            vector_size = 4096 if self.embedding_model == "Qwen/Qwen3-Embedding-8B" else 1536
                                            vector_store.client.create_collection(
                                                collection_name=vector_store.collection_name,
                                                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                                            )

                                    # Attempt to add documents
                                    vector_store.add_documents(documents=batch)
                                    self.indexed_chunk_count += len(batch)
                                    pbar.update(len(batch))
                                    logger.debug(f"✅ Batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size} added")
                                    break  # Break out of the loop on success

                                except Exception as batch_e:
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        logger.warning(f"⚠️  Batch {i//batch_size + 1} failed (retry {retry_count}/{max_retries}): {str(batch_e)[:100]}")
                                        import time
                                        time.sleep(1)  # Wait 1 second before retrying
                                    else:
                                        logger.error(f"❌ Batch {i//batch_size + 1} finally failed: {batch_e}")
                                        self.failed_batch_count += 1
                                        # Continue even on final failure

                    logger.info(f"Successfully added {total_chunks} new document chunks to Qdrant.")
                else:
                    logger.warning("No processable content found in the new files.")
            except Exception as e:
                # When an error occurs anywhere in document loading/splitting or batch addition
                logger.error(f"Failed to process or add new documents: {e}", exc_info=True)
        else:
            logger.info("✅ No new documents found to index - all files are already processed!")
            # Provide current collection status info
            try:
                current_collection_info = vector_store.client.get_collection(vector_store.collection_name)
                logger.info(f"📊 Current collection status: {current_collection_info.points_count:,} total chunks indexed")
            except:
                logger.debug("Could not retrieve current collection info for status display.")

        # --- 5. Create retrievers ---
        self.retrievers = self._create_retrievers(vector_store)
        logger.info(f"Retriever initialization complete. Using Qdrant collection: {os.getenv('QDRANT_COLLECTION', 'personaai_rag')}")

        return self
    # -----------------------------------------

    def load_vectorstore(self) -> Any:
        """
        Load the vector store from the persistence directory.
        """
        if not self.persist_directory:
            raise ValueError("Persistence directory not set.")

        embedding_function = self._create_embedding_function(self.embedding_model)
        return self._load_or_create_vector_store(embedding_function)

    def load(self) -> Dict[str, BaseRetriever]:
        """
        Load the vector store and create retrievers.
        """
        vectorstore = self.load_vectorstore()
        self.retrievers = self._create_retrievers(vectorstore)
        logger.info("Retriever loaded successfully.")
        return self.retrievers

class KeywordRetriever(BaseRetriever):
    """Wrapper retriever for DocumentRetrievalChain's search_keyword"""
