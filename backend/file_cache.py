"""
File Cache for Performance Optimization

Caches processed file data to avoid re-reading files on every query.
Reduces file I/O from seconds to milliseconds.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
import pickle

logger = logging.getLogger(__name__)

# In-memory cache for processed files
_file_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL = 300  # 5 minutes cache TTL


def get_file_hash(file_path: Path) -> str:
    """Generate hash for file based on path and modification time."""
    try:
        mtime = file_path.stat().st_mtime
        content = f"{file_path}_{mtime}"
        return hashlib.md5(content.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"Error getting file hash: {e}")
        return hashlib.md5(str(file_path).encode()).hexdigest()


def get_cached_data(file_path: Path, cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Get cached data for a file.
    
    Args:
        file_path: Path to file
        cache_key: Cache key (e.g., "excel_processed", "pdf_processed")
    
    Returns:
        Cached data or None if not found/expired
    """
    file_hash = get_file_hash(file_path)
    full_key = f"{file_hash}_{cache_key}"
    
    # Check if cache exists and is not expired
    if full_key in _file_cache:
        if full_key in _cache_timestamps:
            age = time.time() - _cache_timestamps[full_key]
            if age < CACHE_TTL:
                logger.info(f"Cache HIT for {file_path.name} ({cache_key})")
                return _file_cache[full_key]
            else:
                # Cache expired
                logger.info(f"Cache EXPIRED for {file_path.name} ({cache_key})")
                del _file_cache[full_key]
                del _cache_timestamps[full_key]
        else:
            return _file_cache[full_key]
    
    logger.info(f"Cache MISS for {file_path.name} ({cache_key})")
    return None


def set_cached_data(file_path: Path, cache_key: str, data: Dict[str, Any]) -> None:
    """
    Cache processed data for a file.
    
    Args:
        file_path: Path to file
        cache_key: Cache key (e.g., "excel_processed", "pdf_processed")
        data: Data to cache
    """
    file_hash = get_file_hash(file_path)
    full_key = f"{file_hash}_{cache_key}"
    
    _file_cache[full_key] = data
    _cache_timestamps[full_key] = time.time()
    
    logger.info(f"Cached data for {file_path.name} ({cache_key})")


def clear_cache(file_path: Optional[Path] = None) -> None:
    """
    Clear cache for a specific file or all files.
    
    Args:
        file_path: Optional file path to clear, or None to clear all
    """
    if file_path:
        file_hash = get_file_hash(file_path)
        keys_to_remove = [k for k in _file_cache.keys() if k.startswith(file_hash)]
        for key in keys_to_remove:
            _file_cache.pop(key, None)
            _cache_timestamps.pop(key, None)
        logger.info(f"Cleared cache for {file_path.name}")
    else:
        _file_cache.clear()
        _cache_timestamps.clear()
        logger.info("Cleared all cache")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return {
        "cached_files": len(_file_cache),
        "cache_size_mb": sum(len(str(v).encode()) for v in _file_cache.values()) / (1024 * 1024),
        "oldest_entry": min(_cache_timestamps.values()) if _cache_timestamps else None,
        "newest_entry": max(_cache_timestamps.values()) if _cache_timestamps else None,
    }

