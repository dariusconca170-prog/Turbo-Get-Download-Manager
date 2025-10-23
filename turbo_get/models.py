# turbo_get/models.py
"""
Data Models for TurboGet Download Manager
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class ChunkInfo:
    """Information about a download chunk"""
    start: int
    end: int
    downloaded: int = 0
    completed: bool = False
    retries: int = 0
    thread_id: Optional[int] = None
    speed: float = 0.0

@dataclass
class DownloadMetadata:
    """Metadata for resumable downloads"""
    url: str
    filename: str
    total_size: int
    chunks: List[Dict]
    created_at: str
    supports_resume: bool
    checksum: Optional[str] = None
    mirrors: List[str] = field(default_factory=list)

@dataclass
class ServerCapabilities:
    """Detected server capabilities"""
    supports_range: bool = False
    supports_resume: bool = False
    supports_compression: bool = False
    supports_http2: bool = False
    max_connections: int = 8
    content_encoding: Optional[str] = None
