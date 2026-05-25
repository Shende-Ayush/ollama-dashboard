"""Simple in-memory LRU cache for completions."""
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

@dataclass
class CacheEntry:
    completion: str
    model: str
    timestamp: float

class CompletionCache:
    """LRU cache for code completions."""
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, prefix: str, suffix: str, language: str) -> str:
        """Create cache key from completion context."""
        # Use last 200 chars of prefix + first 100 of suffix as key
        key_content = f"{language}:{prefix[-200:]}{suffix[:100]}"
        return hashlib.sha256(key_content.encode()).hexdigest()[:32]
    
    def get(self, prefix: str, suffix: str, language: str) -> Optional[CacheEntry]:
        """Get cached completion if available and not expired."""
        key = self._make_key(prefix, suffix, language)
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        # Check TTL
        if time.time() - entry.timestamp > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return entry
    
    def put(self, prefix: str, suffix: str, language: str, completion: str, model: str) -> None:
        """Store a completion in cache."""
        key = self._make_key(prefix, suffix, language)
        
        # Evict oldest if full
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = CacheEntry(
            completion=completion,
            model=model,
            timestamp=time.time(),
        )
    
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    @property
    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate * 100, 1),
        }

# Module singleton
completion_cache = CompletionCache()
