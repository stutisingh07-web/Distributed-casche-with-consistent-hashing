from collections import Counter

from ring import HashRing


def keys(n=10_000):
    return [f"key-{i}" for i in range(n)]


def test_empty_ring_returns_none():
    assert HashRing().get_node("anything") is None


def test_single_node_gets_everything():
    ring = HashRing(["a"])
    assert all(ring.get_node(k) == "a" for k in keys(100))


def test_distribution_is_roughly_even():
    ring = HashRing(["a", "b", "c"], replicas=150)
    counts = Counter(ring.get_node(k) for k in keys())
    expected = 10_000 / 3
    for node, count in counts.items():
        assert abs(count - expected) / expected < 0.15, (node, count)


def test_adding_node_moves_only_about_its_share():
    ring = HashRing(["a", "b", "c"], replicas=150)
    before = {k: ring.get_node(k) for k in keys()}
    ring.add_node("d")
    after = {k: ring.get_node(k) for k in keys()}

    moved = [k for k in before if before[k] != after[k]]
    # Every moved key must now live on the new node.
    assert all(after[k] == "d" for k in moved)
    # Roughly 1/4 of keys should move.
    assert 0.18 < len(moved) / len(before) < 0.32


def test_removing_node_only_reassigns_its_keys():
    ring = HashRing(["a", "b", "c"], replicas=150)
    before = {k: ring.get_node(k) for k in keys()}
    ring.remove_node("b")
    after = {k: ring.get_node(k) for k in keys()}

    for k in before:
        if before[k] != "b":
            assert after[k] == before[k]
        else:
            assert after[k] in {"a", "c"}


def test_add_and_remove_are_idempotent():
    ring = HashRing(["a"], replicas=10)
    ring.add_node("a")
    ring.remove_node("missing")
    assert ring.nodes == ["a"]
    assert len(ring._keys) == 10

