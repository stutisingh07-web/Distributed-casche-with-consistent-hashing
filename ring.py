class HashRing:
    def __init__(self, nodes=None, replicas: int = 100):
        self.replicas = replicas
        self._ring: dict[int, str] = {}   # hash position -> node name
        self._keys: list[int] = []        # sorted hash positions
        self._nodes: set[str] = set()
        for node in nodes or []:
            self.add_node(node)

    @staticmethod
    def _hash(s: str) -> int:
        # md5 is stable across processes (unlike built-in hash()).
        return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)

    @property
    def nodes(self) -> list[str]:
        return sorted(self._nodes)

    def add_node(self, node: str) -> None:
        if node in self._nodes:
            return
        self._nodes.add(node)
        for i in range(self.replicas):
            h = self._hash(f"{node}#{i}")
            self._ring[h] = node
            bisect.insort(self._keys, h)

    def remove_node(self, node: str) -> None:
        if node not in self._nodes:
            return
        self._nodes.discard(node)
        for i in range(self.replicas):
            h = self._hash(f"{node}#{i}")
            self._ring.pop(h, None)
            idx = bisect.bisect_left(self._keys, h)
            if idx < len(self._keys) and self._keys[idx] == h:
                del self._keys[idx]

    def get_node(self, key: str) -> str | None:
        if not self._keys:
            return None
        idx = bisect.bisect(self._keys, self._hash(key)) % len(self._keys)
        return self._ring[self._keys[idx]]
