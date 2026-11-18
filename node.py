import os
import threading
import time
from collections import OrderedDict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

NODE_NAME = os.getenv("NODE_NAME", "node")
MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "1000"))


class LRUCache:
    def __init__(self, max_items: int):
        self.max_items = max_items
        self._data: OrderedDict[str, tuple[str, float | None]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _expired(self, expires_at):
        return expires_at is not None and time.time() >= expires_at

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            value, expires_at = item
            if self._expired(expires_at):
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)  # mark as most recently used
            self.hits += 1
            return value

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expires_at = time.time() + ttl if ttl else None
        with self._lock:
            self._data[key] = (value, expires_at)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)  # evict least recently used

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


class PutBody(BaseModel):
    value: str
    ttl: int | None = None  # seconds


cache = LRUCache(MAX_ITEMS)
app = FastAPI(title=f"cache-node-{NODE_NAME}")


@app.get("/health")
def health():
    return {"status": "ok", "node": NODE_NAME}


@app.put("/cache/{key}")
def put(key: str, body: PutBody):
    cache.set(key, body.value, body.ttl)
    return {"key": key, "stored": True}


@app.get("/cache/{key}")
def get(key: str):
    value = cache.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="key not found")
    return {"key": key, "value": value}


@app.delete("/cache/{key}")
def delete(key: str):
    if not cache.delete(key):
        raise HTTPException(status_code=404, detail="key not found")
    return {"key": key, "deleted": True}


@app.get("/stats")
def stats():
    return {
        "node": NODE_NAME,
        "items": len(cache),
        "hits": cache.hits,
        "misses": cache.misses,
        "max_items": MAX_ITEMS,
    }