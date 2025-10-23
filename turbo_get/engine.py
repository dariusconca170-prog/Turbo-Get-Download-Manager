# turbo_get/engine.py
"""
Core download engine with multi-threading, chunking, and optimization.
"""

import asyncio
import aiohttp
import hashlib
import json
import os
import time
import ssl
import certifi
from pathlib import Path
from dataclasses import asdict
from collections import deque
from datetime import datetime
from typing import Optional, List

# Local imports
from models import ChunkInfo, DownloadMetadata, ServerCapabilities

class DownloadEngine:
    """Manages the entire download process for a single file."""

    def __init__(self, url: str, output_path: str, num_threads: int = 8):
        self.url = url
        self.output_path = Path(output_path)
        self.num_threads = num_threads

        self.total_size = 0
        self.downloaded_size = 0
        self.chunks: List[ChunkInfo] = []
        self.capabilities: Optional[ServerCapabilities] = None
        self.mirrors: List[str] = []
        self.current_mirror_index = 0

        # State flags
        self.is_paused = False
        self.is_stopped = False

        # Speed and performance
        self.speed_limit = None  # bytes per second
        self.speed_history = deque(maxlen=100)
        self.last_downloaded = 0
        self.last_time = time.time()
        
        # Session and metadata
        self.session: Optional[aiohttp.ClientSession] = None
        self.metadata_file = self.output_path.with_suffix(f"{self.output_path.suffix}.metadata")
        
        # Callbacks for GUI updates
        self.progress_callback = None
        self.speed_callback = None
        self.status_callback = None

    def is_running(self) -> bool:
        """Check if the download is active (not paused, not stopped)."""
        return not self.is_paused and not self.is_stopped

    async def initialize(self):
        """Initialize download session and detect server capabilities."""
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(limit_per_host=self.num_threads, ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=30)
        
        headers = {
            'User-Agent': 'TurboGet/1.0',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers)
        await self.detect_capabilities()

    async def detect_capabilities(self):
        """Probe the server to determine its features."""
        try:
            self._update_status("Detecting server capabilities...")
            async with self.session.head(self.url, allow_redirects=True, headers={'Range': 'bytes=0-0'}) as response:
                headers = response.headers
                self.capabilities = ServerCapabilities(
                    supports_range='Accept-Ranges' in headers and headers['Accept-Ranges'] != 'none',
                    supports_resume='Accept-Ranges' in headers,
                    content_encoding=headers.get('Content-Encoding')
                )
                
                if 'Content-Range' in headers:
                    self.total_size = int(headers['Content-Range'].split('/')[-1])
                elif 'Content-Length' in headers:
                    self.total_size = int(headers['Content-Length'])
                else:
                    self.total_size = 0 # For streams of unknown length

                if not self.capabilities.supports_range:
                    self.num_threads = 1
                    
                self._update_status(f"Server supports range: {self.capabilities.supports_range}. "
                                  f"Total size: {self.total_size / (1024*1024):.2f} MB")
        except Exception as e:
            self._update_status(f"Capability detection failed: {e}. Using defaults.")
            self.capabilities = ServerCapabilities() # Fallback to default

    async def prepare_chunks(self):
        """Prepare download chunks, resuming if metadata exists."""
        if self.metadata_file.exists():
            await self.load_metadata()
        else:
            if self.capabilities.supports_range and self.total_size > 0:
                chunk_size = self.total_size // self.num_threads
                for i in range(self.num_threads):
                    start = i * chunk_size
                    end = start + chunk_size - 1
                    if i == self.num_threads - 1:
                        end = self.total_size - 1
                    self.chunks.append(ChunkInfo(start=start, end=end))
            else:
                self.chunks.append(ChunkInfo(start=0, end=self.total_size - 1 if self.total_size > 0 else -1))

    async def download(self):
        """Main download orchestration method."""
        try:
            await self.initialize()
            await self.prepare_chunks()

            # Pre-allocate file space
            if self.total_size > 0 and not self.output_path.exists():
                 with open(self.output_path, 'wb') as f:
                    f.seek(self.total_size - 1)
                    f.write(b'\0')
            
            tasks = [self.download_worker(i) for i in range(self.num_threads)]
            monitor_task = asyncio.create_task(self.monitor_speed())
            
            await asyncio.gather(*tasks)

            if not self.is_stopped:
                await self.verify_download()
        finally:
            monitor_task.cancel()
            if self.session:
                await self.session.close()

    async def download_worker(self, worker_id: int):
        """A worker that downloads assigned chunks."""
        while not self.is_stopped:
            while self.is_paused:
                await asyncio.sleep(0.1)
                if self.is_stopped: return

            chunk = self.get_next_chunk(worker_id)
            if not chunk:
                break # No more chunks to download

            success = await self.download_chunk_with_retry(chunk, worker_id)
            if success:
                await self.save_metadata()
            else:
                self._update_status(f"Worker {worker_id}: Chunk failed after all retries.")

    async def download_chunk_with_retry(self, chunk: ChunkInfo, worker_id: int, max_retries: int = 5):
        """Download a single chunk with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                if self.is_stopped: return False
                
                url = self.get_current_url()
                start = chunk.start + chunk.downloaded
                end = chunk.end
                
                headers = {'Range': f'bytes={start}-{end}'} if self.capabilities.supports_range and start <= end else {}
                
                async with self.session.get(url, headers=headers) as response:
                    if response.status not in [200, 206]:
                        raise aiohttp.ClientResponseError(response.request_info, response.history, status=response.status, message=f"HTTP Error {response.status}")
                    
                    # 'r+b' is crucial for seeking and writing in the middle of the file
                    with open(self.output_path, 'r+b') as f:
                        f.seek(start)
                        async for data in response.content.iter_chunked(8192):
                            if self.is_stopped: return False
                            
                            if self.speed_limit:
                                await self.apply_speed_limit(len(data))
                            
                            f.write(data)
                            chunk.downloaded += len(data)
                            self.downloaded_size += len(data)
                            
                            if self.progress_callback:
                                self.progress_callback(self.downloaded_size, self.total_size)
                    
                    chunk.completed = True
                    return True
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                chunk.retries += 1
                wait_time = min(2 ** attempt, 30)
                self._update_status(f"Worker {worker_id} (Retry {attempt+1}/{max_retries}): {type(e).__name__}. Retrying in {wait_time}s.")
                await asyncio.sleep(wait_time)
                
        return False
        
    def get_next_chunk(self, worker_id: int) -> Optional[ChunkInfo]:
        """Get the next available incomplete chunk."""
        # Simple round-robin assignment for now. Could be enhanced with work-stealing.
        for chunk in self.chunks:
            if not chunk.completed and chunk.thread_id is None:
                chunk.thread_id = worker_id
                return chunk
        return None
        
    async def monitor_speed(self):
        """Periodically calculate and report download speed."""
        while not self.is_stopped:
            await asyncio.sleep(1)
            
            current_time = time.time()
            elapsed = current_time - self.last_time
            if elapsed > 0:
                bytes_diff = self.downloaded_size - self.last_downloaded
                speed = bytes_diff / elapsed
                
                self.speed_history.append(speed)
                self.last_downloaded = self.downloaded_size
                self.last_time = current_time
                
                if self.speed_callback and self.speed_history:
                    avg_speed = sum(self.speed_history) / len(self.speed_history)
                    self.speed_callback(speed, avg_speed)

    async def apply_speed_limit(self, bytes_downloaded: int):
        """Delay execution to enforce the speed limit."""
        if self.speed_limit and self.speed_limit > 0:
            expected_time = bytes_downloaded / self.speed_limit
            actual_time = time.time() - self.last_time
            sleep_duration = expected_time - actual_time
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)

    def pause(self):
        self.is_paused = True
        self._update_status("Download paused.")
        
    def resume(self):
        self.is_paused = False
        self._update_status("Download resumed.")
        
    def stop(self):
        self.is_stopped = True
        self._update_status("Download stopping...")
        
    def set_speed_limit(self, limit_kbps: Optional[float]):
        self.speed_limit = limit_kbps * 1024 if limit_kbps is not None else None
            
    async def save_metadata(self):
        """Save download progress to a .metadata file."""
        if not self.capabilities.supports_resume: return
        metadata = DownloadMetadata(
            url=self.url,
            filename=str(self.output_path),
            total_size=self.total_size,
            chunks=[asdict(chunk) for chunk in self.chunks],
            created_at=datetime.now().isoformat(),
            supports_resume=self.capabilities.supports_resume,
            mirrors=self.mirrors
        )
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(asdict(metadata), f, indent=4)
        except IOError as e:
            self._update_status(f"Error saving metadata: {e}")
            
    async def load_metadata(self):
        """Load download progress from a .metadata file to resume."""
        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
            
            # Basic validation
            if data.get('url') != self.url or data.get('total_size') != self.total_size:
                 self._update_status("Metadata mismatch. Starting new download.")
                 self.metadata_file.unlink() # Delete invalid metadata
                 return

            self.chunks = [ChunkInfo(**chunk) for chunk in data['chunks']]
            self.downloaded_size = sum(chunk.downloaded for chunk in self.chunks)
            self._update_status(f"Resuming download. {self.downloaded_size / (1024*1024):.2f} MB already downloaded.")
        except (IOError, json.JSONDecodeError, KeyError) as e:
            self._update_status(f"Failed to load metadata: {e}. Starting fresh.")
            if self.metadata_file.exists(): self.metadata_file.unlink()

    async def verify_download(self):
        """Verify file integrity after download."""
        self._update_status("Verifying download...")
        if not self.output_path.exists():
            self._update_status("Verification failed: File not found.")
            return

        actual_size = self.output_path.stat().st_size
        if self.total_size > 0 and actual_size != self.total_size:
            self._update_status(f"Verification failed: Size mismatch. Expected: {self.total_size}, Got: {actual_size}")
            return
        
        self._update_status("Calculating checksum...")
        sha256 = hashlib.sha256()
        with open(self.output_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256.update(byte_block)
        
        checksum = sha256.hexdigest()
        self._update_status(f"Verification complete. SHA256: {checksum[:16]}...")

        # Clean up metadata file on successful download
        if self.metadata_file.exists():
            self.metadata_file.unlink()

    def get_current_url(self) -> str:
        """Get current URL (main or mirror)."""
        if self.mirrors and self.current_mirror_index < len(self.mirrors):
            return self.mirrors[self.current_mirror_index]
        return self.url
        
    def _update_status(self, message: str):
        """Send status update to the GUI via callback."""
        if self.status_callback:
            self.status_callback(message)
