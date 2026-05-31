#!/usr/bin/env python3
"""
🚀 Full Data Indexing Main Script
- Process 566,157 XML files with Qwen3-Embedding-8B + Qdrant
- Multiprocessing + direct XML parsing + H100 GPU acceleration
"""

from dotenv import load_dotenv
import sys
import os
import time
import torch
import logging

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from backend.agent.utils import get_search_tool

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", ".env"))

# Check whether this is a worker process or the main process
IS_MAIN_PROCESS = __name__ == "__main__"

# Set logging level to INFO to hide DEBUG logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

# Load and validate environment variables from the .env file
required_vars = [
    "DATA_DIR", "EMBEDDING_MODEL", "QDRANT_HOST",
    "QDRANT_PORT", "QDRANT_COLLECTION", "EMBEDDING_BATCH_SIZE"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print("❌ The following environment variables are not set in the .env file:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\n📋 Please refer to env_settings_template.txt and update your .env file.")
    exit(1)

# System information
# Query CUDA only in the main process (so spawn workers do not create a CUDA context at import time).
# Workers recompute torch.cuda.device_count() inside gpu_worker().
if IS_MAIN_PROCESS and torch.cuda.is_available():
    num_gpus = torch.cuda.device_count()
else:
    num_gpus = 0

import multiprocessing as mp

def get_gpu_memory_info():
    """Get each GPU's memory info and compute 80% of the available memory"""
    import subprocess
    try:
        # Resolve environment variable issues when running nvidia-smi
        result = subprocess.run([
            'nvidia-smi', '--query-gpu=index,memory.total,memory.used,memory.free',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, check=True, timeout=10)

        gpu_memory_info = {}
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line.strip():  # Ignore empty lines
                    parts = line.split(', ')
                    if len(parts) >= 4:
                        gpu_id, total, used, free = map(int, parts[:4])
                        # Compute 80% of the available memory in MB
                        available_80_percent = free * 0.8
                        # Convert to a PyTorch fraction (relative to total memory)
                        fraction = min(available_80_percent / total, 0.9)  # Max 90%
                        gpu_memory_info[gpu_id] = {
                            'total_mb': total,
                            'used_mb': used,
                            'free_mb': free,
                            'usable_mb': available_80_percent,
                            'fraction': fraction
                        }
        return gpu_memory_info
    except Exception as e:
        print(f"Could not get GPU memory info: {e}")
        return {}

def gpu_worker(gpu_id: int, worker_id: int, file_batch: list, gpu_memory_fraction: float = 0.6):
    """Worker function that processes a specific file batch on each GPU"""
    import os
    import torch
    os.environ["GPU_ID"] = str(gpu_id)
    # Removed CUDA_VISIBLE_DEVICES - manage GPUs directly in PyTorch

    batch_file_path = None  # Temporary batch file path (cleaned up in finally)

    def _empty_result():
        # Result when processing fails/is interrupted (actual throughput 0)
        return {"files": 0, "indexed_chunks": 0, "failed_batches": 0, "ok": False}

    try:
        print(f"🚀 Worker {worker_id} (GPU {gpu_id}) starting: processing {len(file_batch):,} files")

        # Dynamically compute 80% of each GPU's available memory
        if torch.cuda.is_available():
            # Check the number of GPUs
            num_gpus = torch.cuda.device_count()
            print(f"Worker {worker_id}: {num_gpus} GPUs detected")

            if gpu_id >= num_gpus:
                print(f"❌ Worker {worker_id}: GPU {gpu_id} does not exist (max: {num_gpus-1})")
                return _empty_result()

            # GPU setup and initialization
            torch.cuda.set_device(gpu_id)
            torch.cuda.empty_cache()
            print(f"Worker {worker_id}: GPU {gpu_id} ({torch.cuda.get_device_name(gpu_id)}) setup complete")

            # Use the memory fraction passed from the main process (no nvidia-smi call)
            torch.cuda.set_per_process_memory_fraction(gpu_memory_fraction, device=gpu_id)
            print(f"GPU {gpu_id}: memory fraction = {gpu_memory_fraction:.3f} setup complete")
        else:
            print(f"❌ Worker {worker_id}: CUDA is not available")
            return _empty_result()

        # Pass via a temporary file so only the specific file batch is processed
        # (avoids the size limit of putting tens of thousands of paths directly into an env var / comma-in-path issues with comma separation)
        import tempfile
        fd, batch_file_path = tempfile.mkstemp(prefix=f"worker_{worker_id}_batch_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as bf:
            bf.write("\n".join(file_batch))
        os.environ["WORKER_FILE_BATCH_FILE"] = batch_file_path

        # Set an environment variable marking this as a worker (prevents header output)
        os.environ["IS_WORKER"] = "true"

        # Set worker ID (for tqdm position)
        os.environ["WORKER_ID"] = str(worker_id)

        # Set logging level to WARNING in the worker (hides INFO logs)
        import logging
        logging.getLogger().setLevel(logging.WARNING)

        # Also set additional loggers to WARNING in the worker (prevents duplicate logs)
        logging.getLogger("backend.agent.utils").setLevel(logging.WARNING)
        logging.getLogger("backend.tools.retrieval").setLevel(logging.WARNING)

        print(f"🔧 Worker {worker_id} (GPU {gpu_id}): loading embedding model...")
        retrievers_dict, stats = get_search_tool(return_stats=True)
        fail_note = f" ({stats['failed_batches']} failed batches)" if stats['failed_batches'] else ""
        print(f"✅ Worker {worker_id} (GPU {gpu_id}) complete: {len(file_batch):,} files / {stats['indexed_chunks']:,} chunks added{fail_note}")
        return {
            "files": len(file_batch),
            "indexed_chunks": stats["indexed_chunks"],
            "failed_batches": stats["failed_batches"],
            "ok": True,
        }
    except KeyboardInterrupt:
        print(f"⚠️  Worker {worker_id} (GPU {gpu_id}): user interrupt request")
        return _empty_result()
    except Exception as e:
        print(f"❌ Worker {worker_id} (GPU {gpu_id}) error: {e}")
        import traceback
        traceback.print_exc()
        return _empty_result()
    finally:
        # Clean up the temporary batch file (always runs)
        if batch_file_path and os.path.exists(batch_file_path):
            try:
                os.remove(batch_file_path)
            except Exception:
                pass

        # GPU memory cleanup (always runs)
        if torch.cuda.is_available() and gpu_id < torch.cuda.device_count():
            try:
                torch.cuda.set_device(gpu_id)
                torch.cuda.empty_cache()
                print(f"🧹 Worker {worker_id} (GPU {gpu_id}): GPU memory cleanup complete")
            except Exception as cleanup_e:
                print(f"⚠️  Worker {worker_id} (GPU {gpu_id}): memory cleanup failed - {cleanup_e}")

if __name__ == "__main__":
    # Print header
    print("=" * 80)
    print(f"🚀 Starting full data indexing for {os.getenv('QDRANT_COLLECTION', 'data')}")
    print("=" * 80)
    print("📂 Data path:", os.getenv("DATA_DIR"))
    print("🤖 Embedding model:", os.getenv("EMBEDDING_MODEL"))
    print("🗄️  Vector DB:", f"Qdrant ({os.getenv('QDRANT_COLLECTION')} collection)")

    # Print GPU information
    if torch.cuda.is_available():
        print(f"🎮 GPU: {num_gpus} NVIDIA H200 GPUs detected")
        print(f"💾 Total GPU memory: {num_gpus * torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")

        # Print info for all GPUs (check actual usage via nvidia-smi)
        gpu_memory_info = get_gpu_memory_info()
        for i in range(num_gpus):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3

            if i in gpu_memory_info:
                actual_used = gpu_memory_info[i]['used_mb'] / 1024
                actual_free = gpu_memory_info[i]['free_mb'] / 1024
                print(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f}GB, in use: {actual_used:.2f}GB, available: {actual_free:.2f}GB)")
            else:
                print(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f}GB, usage: unavailable)")

    # Set spawn method for CUDA multiprocessing
    mp.set_start_method('spawn', force=True)

    # Compute the number of workers
    cpu_cores = mp.cpu_count()
    max_workers = min(num_gpus, 8) if num_gpus > 0 else min(cpu_cores, 8)
    print(f"🖥️  CPU cores: {cpu_cores}")
    print(f"🔄 Number of workers to use: {max_workers} (1 worker per GPU)")
    print("🔧 Multiprocessing method: spawn (CUDA compatible)")

    print("\n" + "=" * 80)
    print("⚠️  Notes:")
    estimated_hours = 111 // max_workers if max_workers > 0 else 111
    print(f"   - Estimated processing time: about {estimated_hours} hours (8 GPUs parallel acceleration)")
    print(f"   - GPUs used: {max_workers} H200 (each processing independently)")
    print(f"   - Each GPU: dynamically allocates 80% of available VRAM")
    print(f"   - Batch split: even split with no duplicates")
    print(f"   - Vector DB size after processing: tens of GB")
    print("   - If interrupted, already-processed data is preserved")
    print("=" * 80)

    # User confirmation
    response = input("\nDo you want to continue? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("❌ Indexing was cancelled.")
        exit(0)

    print("\n" + "=" * 80)
    print("🚀 Starting indexing...")
    print("=" * 80)

    start_time = time.time()

    try:
        print("📚 Starting multi-GPU document scan and indexing...")

        # Step 1: Collect the full file list
        print("📂 Scanning file list...")
        data_dir = os.getenv("DATA_DIR")

        # Find all XML files
        all_files = []
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.lower().endswith('.xml'):
                    all_files.append(os.path.join(root, file))

        print(f"📊 Found {len(all_files):,} XML files total")

        # Step 2: Check already-indexed files (only once in main)
        print("🔍 Checking already-indexed files...")
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333"))
            )

            collection_name = os.getenv("QDRANT_COLLECTION", "personaai_rag")
            collection_info = client.get_collection(collection_name)
            indexed_sources = set()

            if collection_info.points_count > 0:
                print(f"🔍 Scanning Qdrant collection '{collection_name}'... ({collection_info.points_count:,} points)")

                # Extract existing sources via a fast scan
                next_page_offset = None
                batch_size = 2000
                scanned_count = 0

                while True:
                    points, next_page_offset = client.scroll(
                        collection_name=collection_name,
                        limit=batch_size,
                        offset=next_page_offset,
                        with_payload=True,
                        with_vectors=False
                    )

                    if not points:
                        break

                    for point in points:
                        if point.payload and "metadata" in point.payload:
                            metadata = point.payload["metadata"]
                            if metadata and "source" in metadata:
                                indexed_sources.add(metadata["source"])

                    scanned_count += len(points)
                    if scanned_count % 20000 == 0:
                        print(f"  Scan progress: {scanned_count:,}/{collection_info.points_count:,} ({len(indexed_sources):,} unique sources)")

                    if next_page_offset is None or len(points) < batch_size:
                        break

                print(f"✅ Existing source scan complete: {len(indexed_sources):,} files")

            # Filter for new files only
            current_sources = set(os.path.normpath(uri) for uri in all_files)
            normalized_indexed_sources = set(os.path.normpath(src) for src in indexed_sources)
            new_files_only = list(current_sources - normalized_indexed_sources)

            print(f"📊 File analysis results:")
            print(f"  📁 Total files: {len(all_files):,}")
            print(f"  ✅ Already indexed: {len(indexed_sources):,}")
            print(f"  🆕 Newly processed: {len(new_files_only):,}")

            if len(new_files_only) == 0:
                print("✅ All files have already been processed!")
                # Initialize the final search tool (verification only - do not re-embed)
                os.environ["GPU_ID"] = "0"
                retrievers_dict = get_search_tool(index=False)
                print("📋 Search tool initialization complete")
                exit(0)

            # Distribute only the new files to the workers
            all_files = new_files_only
            percentage_new = (len(new_files_only) / len(current_sources)) * 100
            print(f"🎯 Files to actually process: {len(all_files):,} ({percentage_new:.1f}%)")

        except Exception as e:
            print(f"⚠️  Failed to check existing files: {e}")
            print("   Processing all files (risk of duplicates)")
            # On error, process all files

        if max_workers > 1 and num_gpus > 1 and len(all_files) > 1000:
            # Multi-GPU processing - split files per GPU
            print(f"🔄 Starting parallel processing on {max_workers} GPUs...")

            # Split files evenly across the number of GPUs
            files_per_gpu = len(all_files) // max_workers
            file_batches = []

            for i in range(max_workers):
                start_idx = i * files_per_gpu
                if i == max_workers - 1:  # The last worker processes all remaining files
                    end_idx = len(all_files)
                else:
                    end_idx = (i + 1) * files_per_gpu

                batch = all_files[start_idx:end_idx]
                file_batches.append(batch)
                print(f"  Worker {i} (GPU {i % num_gpus}): {len(batch):,} files assigned (index {start_idx}-{end_idx-1})")
                print(f"    First file: {os.path.basename(batch[0]) if batch else 'None'}")
                print(f"    Last file: {os.path.basename(batch[-1]) if batch else 'None'}")

            # Validate the batch split
            total_distributed = sum(len(batch) for batch in file_batches)
            print(f"📦 Split a total of {total_distributed:,} files into {len(file_batches)} batches")

            # Duplicate validation: verify every file was distributed exactly once
            all_distributed_files = []
            for batch in file_batches:
                all_distributed_files.extend(batch)

            if len(all_distributed_files) == len(all_files) and len(set(all_distributed_files)) == len(all_files):
                print(f"✅ Batch split validation succeeded: {len(all_files):,} files, no duplicates")
            else:
                print(f"❌ Batch split error: original {len(all_files)}, distributed {len(all_distributed_files)}, unique {len(set(all_distributed_files))}")
                raise ValueError("Duplicate or missing files in batch split!")

            pool = None
            pool_closed_cleanly = False  # Whether it terminated normally (prevents duplicate terminate in finally)
            try:
                pool = mp.Pool(processes=max_workers)
                print(f"🚀 Starting {max_workers} worker processes...")

                # Pre-collect GPU memory info in the main process
                print("🔍 Collecting GPU memory info...")
                gpu_memory_info = get_gpu_memory_info()

                # Assign a unique file batch and memory fraction to each GPU
                gpu_assignments = []
                for i in range(max_workers):
                    gpu_id = i % num_gpus
                    if gpu_id in gpu_memory_info:
                        memory_fraction = min(gpu_memory_info[gpu_id]['fraction'], 0.9)
                        usable_mb = gpu_memory_info[gpu_id]['usable_mb']
                        print(f"  GPU {gpu_id}: allocating 80% of {usable_mb:.0f}MB available memory (fraction: {memory_fraction:.3f})")
                    else:
                        memory_fraction = 0.6  # Default value
                        print(f"  GPU {gpu_id}: memory info unavailable - allocating default 60%")

                    gpu_assignments.append((gpu_id, i, file_batches[i], memory_fraction))

                # Use starmap_async + polling to periodically print progress (heartbeat),
                # and detect hangs via an optional timeout (WORKER_TIMEOUT_SEC, default 0=unlimited)
                async_result = pool.starmap_async(gpu_worker, gpu_assignments)
                heartbeat_interval = int(os.getenv("WORKER_HEARTBEAT_SEC", "300"))  # Default every 5 minutes
                worker_timeout = int(os.getenv("WORKER_TIMEOUT_SEC", "0"))          # 0 means no timeout
                mp_start = time.time()
                while not async_result.ready():
                    async_result.wait(heartbeat_interval)
                    elapsed = time.time() - mp_start
                    print(f"⏳ Multiprocessing in progress... elapsed {elapsed/60:.1f} min ({max_workers} workers)")
                    if worker_timeout > 0 and elapsed > worker_timeout:
                        print(f"⏰ Worker timeout ({worker_timeout}s) exceeded - forcing shutdown")
                        pool.terminate()
                        pool.join(timeout=10)
                        raise TimeoutError(f"Workers did not finish within {worker_timeout} seconds")

                results = async_result.get()

                # Close the pool if it finished normally
                pool.close()
                pool.join()
                pool_closed_cleanly = True
                print("🏁 All worker processes terminated normally")

            except KeyboardInterrupt:
                print("\n🛑 User interrupt request - forcing shutdown of worker processes...")
                if pool is not None:
                    pool.terminate()  # Force shutdown
                    pool.join(timeout=10)  # Wait up to 10 seconds
                    print("⚡ All worker processes force-shutdown complete")
                raise  # Re-raise the exception to be handled upstream

            except Exception as e:
                print(f"\n❌ Error during multiprocessing execution: {e}")
                if pool is not None:
                    pool.terminate()
                    pool.join(timeout=10)
                    print("⚡ Force shutdown of worker processes")
                raise

            finally:
                # Force cleanup only on abnormal termination (prevents duplicate terminate after normal close()/join())
                if pool is not None and not pool_closed_cleanly:
                    try:
                        pool.terminate()
                        pool.join(timeout=5)
                    except:
                        pass  # Ignore if already terminated

                # Clean up all GPU memory
                if torch.cuda.is_available():
                    print("🧹 Main process: cleaning up all GPU memory...")
                    for i in range(num_gpus):
                        try:
                            torch.cuda.set_device(i)
                            torch.cuda.empty_cache()
                        except:
                            pass

            # Aggregate worker results (based on actual throughput)
            results = [r for r in results if isinstance(r, dict)]
            processed_files = sum(r["files"] for r in results)
            total_indexed_chunks = sum(r["indexed_chunks"] for r in results)
            total_failed_batches = sum(r["failed_batches"] for r in results)
            failed_workers = sum(1 for r in results if not r["ok"])
            print(f"✅ Processed {processed_files:,} files total / indexed {total_indexed_chunks:,} chunks")
            if total_failed_batches or failed_workers:
                print(f"⚠️  {total_failed_batches:,} failed batches, {failed_workers} failed/interrupted workers - some data may be missing")

            # Create a retriever for verifying results after multiprocessing completes
            # (verification only - workers already embedded everything; do not re-embed)
            os.environ["GPU_ID"] = "0"
            print("📋 Initializing final search tool...")
            retrievers_dict = get_search_tool(index=False)

        else:
            # Single GPU or small-scale data processing
            print("📚 Processing in a single process...")
            if num_gpus > 0:
                os.environ["GPU_ID"] = "0"
            retrievers_dict = get_search_tool()

        end_time = time.time()
        total_time = end_time - start_time

        print("\n" + "=" * 80)
        print("🎉 Indexing complete!")
        print("=" * 80)
        print(f"⏱️  Total time taken: {total_time:.1f}s ({total_time/60:.1f}min, {total_time/3600:.1f}h)")

        # Check GPU memory usage
        if torch.cuda.is_available():
            print("💾 GPU memory usage:")
            for i in range(num_gpus):
                final_memory = torch.cuda.memory_allocated(i) / 1024**3
                print(f"   GPU {i}: {final_memory:.2f}GB")

        # Check retriever status
        print("\n📋 Created retrievers:")
        for key, value in retrievers_dict.items():
            if value is not None:
                print(f"   ✅ {key}: {type(value).__name__}")
            else:
                print(f"   ❌ {key}: None")

        # Search test
        if 'semantic' in retrievers_dict and retrievers_dict['semantic'] is not None:
            print("\n🔍 Search functionality test:")
            try:
                semantic_retriever = retrievers_dict['semantic']
                results = semantic_retriever.invoke("research", config={"k": 3})
                print(f"   ✅ Search test succeeded: {len(results)} results")
                print(f"   📄 First result preview: {results[0].page_content[:100]}...")
            except Exception as search_e:
                print(f"   ⚠️  Search test failed: {search_e}")

        print("\n" + "=" * 80)
        print("✅ Full indexing process complete!")
        print(f"   🗄️  Searchable in Qdrant collection '{os.getenv('QDRANT_COLLECTION')}'")
        print("   🔍 Use get_search_tool() in backend/agent/utils.py")
        print("=" * 80)

    except KeyboardInterrupt:
        end_time = time.time()
        total_time = end_time - start_time
        print("\n" + "=" * 80)
        print("🛑 Interrupted by the user")
        print(f"⏱️  Run time: {total_time:.1f}s ({total_time/60:.1f}min)")
        print("   💾 Already-processed data is saved in Qdrant")
        print("   🔄 Re-running will continue from the interruption point")
        print("=" * 80)

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        print("\n" + "=" * 80)
        print(f"❌ Indexing failed: {e}")
        print(f"⏱️  Time taken until failure: {total_time:.1f}s")
        print("   💾 Partially processed data may be preserved")
        print("=" * 80)
        import traceback
        traceback.print_exc()

    finally:
        # Final cleanup work
        print("\n🧹 Final system cleanup...")
        try:
            # Clean up cached memory on all GPUs
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    try:
                        torch.cuda.set_device(i)
                        torch.cuda.empty_cache()
                    except:
                        pass
                print("✅ GPU memory cleanup complete")
        except:
            pass

        print("🏁 Program exit")
