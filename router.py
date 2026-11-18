import os
from collections import Counter

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from ring import HashRing

app = FastAPI(title="cache-router")

ring = HashRing(replicas=int(os.getenv("VNODES", "100")))
node_urls: dict[str, str] = {}   # node name -> base URL
client = httpx.AsyncClient(timeout=2.0)


def _parse_nodes(spec: str) -> dict[str, str]:
    out = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        name, url = part.split("=", 1)
        out[name] = url
    return out


@app.on_event("startup")
def load_initial_nodes():
    for name, url in _parse_nodes(os.getenv("CACHE_NODES", "")).items():
        node_urls[name] = url
        ring.add_node(name)


@app.on_event("shutdown")
async def close_client():
    await client.aclose()


def _node_for(key: str) -> str:
    name = ring.get_node(key)
    if name is None:
        raise HTTPException(status_code=503, detail="no cache nodes registered")
    return name


async def _forward(method: str, key: str, body: dict | None = None):
    name = _node_for(key)
    url = f"{node_urls[name]}/cache/{key}"
    try:
        resp = await client.request(method, url, json=body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"node {name} unreachable: {exc}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="key not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    data["node"] = name
    return data


class PutBody(BaseModel):
    value: str
    ttl: int | None = None


@app.put("/cache/{key}")
async def put(key: str, body: PutBody):
    return await _forward("PUT", key, body.model_dump())


@app.get("/cache/{key}")
async def get(key: str):
    return await _forward("GET", key)


@app.delete("/cache/{key}")
async def delete(key: str):
    return await _forward("DELETE", key)


# ---- admin: membership ----

class NodeBody(BaseModel):
    name: str
    url: str


@app.get("/admin/nodes")
def list_nodes():
    return {"nodes": [{"name": n, "url": node_urls[n]} for n in ring.nodes]}


@app.post("/admin/nodes", status_code=201)
def add_node(body: NodeBody):
    if body.name in node_urls:
        raise HTTPException(status_code=409, detail="node already exists")
    node_urls[body.name] = body.url
    ring.add_node(body.name)
    return {"added": body.name, "nodes": ring.nodes}


@app.delete("/admin/nodes/{name}")
def remove_node(name: str):
    if name not in node_urls:
        raise HTTPException(status_code=404, detail="node not found")
    ring.remove_node(name)
    node_urls.pop(name)
    return {"removed": name, "nodes": ring.nodes}


# ---- admin: stats and routing check ----

@app.get("/admin/route/{key}")
def route(key: str):
    return {"key": key, "node": _node_for(key)}


@app.get("/stats")
async def stats():
    """Key counts per node, from each node's /stats endpoint."""
    result = {}
    for name in ring.nodes:
        try:
            resp = await client.get(f"{node_urls[name]}/stats")
            result[name] = resp.json()
        except httpx.RequestError as exc:
            result[name] = {"error": str(exc)}
    return {"nodes": result, "total_items": sum(
        v.get("items", 0) for v in result.values() if isinstance(v, dict)
    )}
