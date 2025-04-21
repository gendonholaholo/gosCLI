import functools
import hashlib
import logging
import time # Added for sliding TTL
from typing import Any, Callable, Optional, Tuple, List

import diskcache as dc

# Placeholder for vector cache - requires additional dependencies (e.g., chromadb, sentence-transformers)
# from goscli.infrastructure.services.vector_cache import VectorCache 

# Configure logging
logger = logging.getLogger(__name__)

# --- Cache Configuration ---
# L1 Cache (In-Memory) - Simple LRU cache
# Size can be adjusted based on expected usage patterns
L1_CACHE_SIZE = 128 

# L2 Cache (File-Based)
# Directory will be created in the user's cache directory
CACHE_DIR = "goscli_cache"
# L2 Default TTL (e.g., 24 hours)
L2_DEFAULT_TTL_SECONDS = 60 * 60 * 24 
# L1 Default TTL (e.g., 15 minutes)
L1_DEFAULT_TTL_SECONDS = 60 * 15 
# L3 Vector Cache TTL (e.g., 7 days) - applied when storing embeddings
L3_DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7

# Sliding TTL configuration
ENABLE_SLIDING_TTL = True
SLIDING_TTL_EXTENSION_SECONDS = 60 * 60 # Extend by 1 hour on access

class CachingService:
    """Provides multi-level caching (L1: in-memory, L2: disk-based, L3: vector placeholder)."""

    def __init__(self, 
                 cache_dir: str = CACHE_DIR, 
                 l2_default_ttl: int = L2_DEFAULT_TTL_SECONDS, 
                 l1_default_ttl: int = L1_DEFAULT_TTL_SECONDS):
        """Initializes the CachingService."""
        self.l2_default_ttl = l2_default_ttl
        self.l1_default_ttl = l1_default_ttl
        self._l1_expiry: dict[str, float] = {} # Store expiry times for L1 entries
        
        # Initialize L2 Disk Cache
        try:
            # Diskcache uses seconds for expire
            self.disk_cache = dc.Cache(cache_dir, timeout=1, expire=self.l2_default_ttl) 
            logger.info(f"Initialized L2 disk cache at: {self.disk_cache.directory} with default TTL: {self.l2_default_ttl}s")
        except Exception as e:
            logger.error(f"Failed to initialize L2 disk cache at {cache_dir}: {e}", exc_info=True)
            self.disk_cache = None

        # Initialize L1 In-Memory Cache (Simple dictionary + expiry tracking)
        self._memory_cache: dict[str, Any] = {}
        self._memory_cache_keys: list[str] = [] 
        self._l1_max_size = L1_CACHE_SIZE
        logger.info(f"Initialized L1 in-memory cache with size: {self._l1_max_size}, TTL: {self.l1_default_ttl}s")
        
        # Initialize L3 Vector Cache Placeholder
        # self.vector_cache = VectorCache() # Requires implementation and dependencies
        # logger.info("Initialized L3 vector cache (placeholder).")

    def _generate_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generates a consistent cache key."""
        # Remove internal TTL arg if present before generating key
        kwargs.pop('ttl_seconds', None)
        kwargs.pop('l1_ttl_seconds', None)
        kwargs.pop('l2_ttl_seconds', None)
        
        key_parts = [prefix]
        key_parts.extend(map(str, args))
        # Ensure consistent order for kwargs
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()

    # --- L1 Cache Operations ---
    def _prune_l1_cache(self) -> None:
        """Removes expired or LRU items from L1 cache."""
        now = time.monotonic()
        # Remove expired items first
        expired_keys = [k for k, expiry in self._l1_expiry.items() if expiry < now]
        for key in expired_keys:
            if key in self._memory_cache: del self._memory_cache[key]
            if key in self._l1_expiry: del self._l1_expiry[key]
            if key in self._memory_cache_keys: self._memory_cache_keys.remove(key)
            logger.debug(f"L1 Cache EXPIRED key: {key[:10]}...")

        # Enforce max size using LRU if needed after expiry pruning
        while len(self._memory_cache) > self._l1_max_size:
            if not self._memory_cache_keys:
                break # Should not happen if cache is not empty
            lru_key = self._memory_cache_keys.pop(0)
            if lru_key in self._memory_cache: del self._memory_cache[lru_key]
            if lru_key in self._l1_expiry: del self._l1_expiry[lru_key]
            logger.debug(f"L1 Cache EVICTED key (LRU): {lru_key[:10]}...")

    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Gets an item from L1, checking expiry and applying sliding TTL."""
        self._prune_l1_cache() # Prune before getting
        now = time.monotonic()
        if key in self._memory_cache and key in self._l1_expiry and self._l1_expiry[key] > now:
            # Cache Hit & Not Expired
            self._memory_cache_keys.remove(key)
            self._memory_cache_keys.append(key) # Update LRU order
            
            # Implement Sliding TTL for L1
            if ENABLE_SLIDING_TTL:
                new_expiry = now + self.l1_default_ttl # Reset TTL on access
                self._l1_expiry[key] = new_expiry
                logger.debug(f"L1 Cache HIT (Sliding TTL applied) for key: {key[:10]}... New Expiry: {new_expiry:.0f}")
            else:
                 logger.debug(f"L1 Cache HIT for key: {key[:10]}...")
            return self._memory_cache[key]
            
        # Cache Miss or Expired
        if key in self._memory_cache: # Clean up if expired but not pruned somehow
            del self._memory_cache[key]
            del self._l1_expiry[key]
            if key in self._memory_cache_keys: self._memory_cache_keys.remove(key)
        logger.debug(f"L1 Cache MISS for key: {key[:10]}...")
        return None

    def _put_in_memory(self, key: str, value: Any, ttl_seconds: Optional[int]) -> None:
        """Puts an item into L1 with TTL, managing size."""
        self._prune_l1_cache() # Prune before putting
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.l1_default_ttl
        expiry_time = time.monotonic() + effective_ttl
        
        if key in self._memory_cache:
            self._memory_cache_keys.remove(key)
        elif len(self._memory_cache) >= self._l1_max_size:
            # Evict LRU if pruning didn't make space
             if self._memory_cache_keys:
                lru_key = self._memory_cache_keys.pop(0)
                if lru_key in self._memory_cache: del self._memory_cache[lru_key]
                if lru_key in self._l1_expiry: del self._l1_expiry[lru_key]
                logger.debug(f"L1 Cache EVICTED key (LRU on put): {lru_key[:10]}...")

        self._memory_cache[key] = value
        self._l1_expiry[key] = expiry_time
        self._memory_cache_keys.append(key)
        logger.debug(f"L1 Cache PUT key: {key[:10]}... TTL: {effective_ttl}s")

    # --- L2 Cache Operations ---
    def _get_from_disk(self, key: str) -> Optional[Any]:
        """Gets an item from L2, applying sliding TTL if enabled."""
        if self.disk_cache is None: return None
        try:
            # Diskcache get doesn't automatically slide TTL, we need to reset it on hit
            value = self.disk_cache.get(key, default=None, expire_time=ENABLE_SLIDING_TTL)
            if value is not None:
                logger.debug(f"L2 Cache HIT for key: {key[:10]}...")
                # Manually update expiry if sliding TTL is desired (more involved)
                # Diskcache v5.2+ `expire_time=True` *should* handle sliding TTL on get.
                # If using older version or explicit control needed:
                # if ENABLE_SLIDING_TTL:
                #     current_ttl = self.disk_cache.get(key, default=None, read=True).expire # Read expiry without resetting
                #     if current_ttl is not None: # Check if TTL exists
                #          new_expire = time.time() + self.l2_default_ttl # Reset based on access time
                #          self.disk_cache.touch(key, expire=new_expire) # Update TTL
                #          logger.debug(f"L2 Sliding TTL applied for key {key[:10]}... New Expiry: {new_expire:.0f}")
                return value
        except Exception as e:
            logger.error(f"Error getting from L2 cache (key: {key[:10]}...): {e}", exc_info=True)
        logger.debug(f"L2 Cache MISS for key: {key[:10]}...")
        return None

    def _put_in_disk(self, key: str, value: Any, ttl_seconds: Optional[int]) -> None:
        """Puts an item into L2 with specified TTL."""
        if self.disk_cache is None: return
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.l2_default_ttl
        try:
            self.disk_cache.set(key, value, expire=effective_ttl)
            logger.debug(f"L2 Cache PUT key: {key[:10]}... TTL: {effective_ttl}s")
        except Exception as e:
            logger.error(f"Error putting into L2 cache (key: {key[:10]}...): {e}", exc_info=True)

    # --- L3 Vector Cache Operations (Placeholder) ---
    def _find_similar_in_vector_cache(self, query_text: str, threshold: float = 0.8) -> Optional[Any]:
        """Placeholder for finding similar items in vector cache."""
        # if not hasattr(self, 'vector_cache') or self.vector_cache is None:
        #     return None
        logger.debug(f"L3 Vector Cache lookup for: '{query_text[:30]}...' (Placeholder - Not Implemented)")
        # try:
        #     results = self.vector_cache.find_similar(query_text, threshold=threshold, limit=1)
        #     if results:
        #         # Assuming results contain the cached value or a key to retrieve it
        #         similar_key, similarity_score, cached_data = results[0] 
        #         logger.info(f"L3 Vector Cache HIT. Found similar item (Score: {similarity_score:.2f}) for key: {similar_key}")
        #         # Potentially retrieve full data from L2 using similar_key if only key is stored
        #         return cached_data # Return the cached data associated with the similar item
        # except Exception as e:
        #      logger.error(f"Error querying L3 vector cache: {e}", exc_info=True)
        return None

    def _put_in_vector_cache(self, key: str, text_to_embed: str, data_to_store: Any) -> None:
        """Placeholder for adding item to vector cache."""
        # if not hasattr(self, 'vector_cache') or self.vector_cache is None:
        #     return None
        logger.debug(f"L3 Vector Cache store attempt for key: {key} (Placeholder - Not Implemented)")
        # try:
        #      self.vector_cache.add(key, text_to_embed, data_to_store, ttl_seconds=L3_DEFAULT_TTL_SECONDS)
        #      logger.info(f"Stored item in L3 vector cache with key: {key}")
        # except Exception as e:
        #      logger.error(f"Error putting into L3 vector cache: {e}", exc_info=True)
        pass

    # --- Public Get/Put Interface --- 
    def get(self, prefix: str, *args: Any, **kwargs: Any) -> Optional[Any]:
        """Retrieves item from cache (L1 -> L2 -> L3 placeholder)."""
        key = self._generate_key(prefix, *args, **kwargs)
        l1_ttl = kwargs.pop('l1_ttl_seconds', None)
        
        value = self._get_from_memory(key)
        if value is not None: return value

        value = self._get_from_disk(key)
        if value is not None:
            self._put_in_memory(key, value, ttl_seconds=l1_ttl) # Use specific L1 TTL if provided
            return value
            
        # L3 Vector Cache Fallback (Placeholder)
        # Extract a representative query string from args/kwargs if appropriate
        # Example: if prefix == 'chat_response': query_text = args[0] # Assume first arg is user prompt
        # query_text = self._extract_query_text(prefix, *args, **kwargs)
        # if query_text:
        #      similar_value = self._find_similar_in_vector_cache(query_text)
        #      if similar_value is not None:
        #          logger.info("CacheUsedFallback event: Returning result from L3 vector cache.")
        #          # Populate L1/L2 with the fallback result?
        #          # self._put_in_memory(key, similar_value, ttl_seconds=l1_ttl)
        #          # self._put_in_disk(key, similar_value, ttl_seconds=self.l2_default_ttl) # Use default L2 TTL for fallback?
        #          return similar_value

        return None # Cache miss in all levels

    def put(self, value: Any, prefix: str, *args: Any, **kwargs: Any) -> None:
        """Stores an item in the cache (L1, L2, and L3 placeholder)."""
        l1_ttl = kwargs.pop('l1_ttl_seconds', None)
        l2_ttl = kwargs.pop('l2_ttl_seconds', None)
        key = self._generate_key(prefix, *args, **kwargs)
        
        self._put_in_memory(key, value, ttl_seconds=l1_ttl)
        self._put_in_disk(key, value, ttl_seconds=l2_ttl)
        
        # L3 Vector Cache Store (Placeholder)
        # Extract text to embed from the value or args/kwargs
        # text_to_embed = self._extract_text_for_embedding(prefix, value, *args, **kwargs)
        # if text_to_embed:
        #      self._put_in_vector_cache(key, text_to_embed, value)

    def clear(self, level: str = 'all') -> None:
        """Clears the cache.

        Args:
            level: Which cache level to clear ('l1', 'l2', 'all'). Defaults to 'all'.
        """
        if level in ['l1', 'all']:
            self._memory_cache.clear()
            self._memory_cache_keys.clear()
            self._l1_expiry.clear()
            logger.info("Cleared L1 (in-memory) cache.")
        
        if level in ['l2', 'all'] and self.disk_cache is not None:
            try:
                count = self.disk_cache.clear()
                logger.info(f"Cleared L2 (disk) cache. Removed {count} items.")
            except Exception as e:
                 logger.error(f"Failed to clear L2 disk cache: {e}", exc_info=True)
        # if level in ['l3', 'all'] and hasattr(self, 'vector_cache'):
             # self.vector_cache.clear()
             # logger.info("Cleared L3 (vector) cache.")

    # --- Decorator (Optional convenience) ---
    def cache_result(self, prefix: str, ttl_seconds: Optional[int] = None) -> Callable:
        """Decorator to cache the result of a function.

        Args:
            prefix: A prefix for the cache key.
            ttl_seconds: Optional custom TTL for L2 cache entry.

        Returns:
            A decorator.
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Pass TTL args down if needed by get/put
                l1_ttl = kwargs.pop('l1_ttl_seconds', None)
                l2_ttl = kwargs.pop('l2_ttl_seconds', ttl_seconds) # Use decorator ttl for L2 if provided
                
                cached_value = self.get(prefix, *args, **kwargs, l1_ttl_seconds=l1_ttl)
                if cached_value is not None:
                    return cached_value
                result = func(*args, **kwargs)
                # Pass TTLs to put method
                self.put(result, prefix, *args, **kwargs, l1_ttl_seconds=l1_ttl, l2_ttl_seconds=l2_ttl)
                return result
            return wrapper
        return decorator

# --- Helper for File Fingerprinting ---
def generate_file_fingerprint(file_path: str, algorithm: str = 'sha1') -> Optional[str]:
    """Generates a hash fingerprint for a file's content.

    Args:
        file_path: The path to the file.
        algorithm: Hashing algorithm ('md5' or 'sha1'). Defaults to 'sha1'.

    Returns:
        The hex digest of the file hash, or None if the file cannot be read.
    """
    hasher: Any
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    else:
        logger.error(f"Unsupported hashing algorithm: {algorithm}")
        return None

    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(4096) # Read in chunks to handle large files
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error(f"Could not generate fingerprint for '{file_path}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating fingerprint for '{file_path}': {e}", exc_info=True)
        return None 