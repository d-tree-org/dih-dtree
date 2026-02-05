from collections import deque
import dihlibs.functions as fn
from dihlibs.node import Node  # adjust import if needed

# Sentinel to allow early stop in traversals
DONE = object()


class Graph:
    """
    Directed graph of Node objects.
    Edge A -> B means: A must be processed before B (B depends on A).
    """

    def __init__(self, edges, func_get_id=None):
        """
        Build the graph from iterable of (src, dst) edges.
        `dst` can be None to register an isolated node.

        func_get_id(value) -> hashable id. If omitted, uses `id(value)`.
        For deterministic IDs, pass `lambda x: x` when `x` is a unique string.
        """
        get_id = func_get_id if func_get_id else id

        # Node registry/id maps
        self.node_cache = {}     # node_id -> Node()
        self.adj_list = {}       # forward: node_id -> [Node children...]
        self.nodes = []          # list of Node (unique)

        # Build forward graph
        for e1, e2 in edges:
            self._add_edge(e1, e2, get_id)

        # Build reverse adjacency once (child_id -> [parent Node, ...])
        self.rev_adj_list = {nid: [] for nid in self.node_cache.keys()}
        for parent_id, children in self.adj_list.items():
            for child in children:
                self.rev_adj_list.setdefault(child.id, []).append(
                    self.node_cache[parent_id]
                )

    # ------------------------------------------------------------------
    # Alternate constructor for reversed-dependency dicts
    # ------------------------------------------------------------------
    @classmethod
    def from_dependency_dict(cls, deps_dict, func_get_id=None):
        """
        deps_dict[target] = [dep1, dep2, ...]  (deps must come BEFORE target)
        This flips into edges dep -> target. Empty deps still register the node.
        """
        edges = []
        for target, deps_list in deps_dict.items():
            if deps_list:
                for dep in deps_list:
                    edges.append((dep, target))  # dep -> target
            else:
                edges.append((target, None))    # ensure target exists
        return cls(edges, func_get_id=func_get_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_node(self, value, get_id):
        """Return canonical Node() for `value`, creating if missing."""
        if fn.is_null(value):
            return None
        nid = get_id(value)
        if nid in self.node_cache:
            return self.node_cache[nid]

        n = Node()
        n.id = nid
        n.value = value
        self.node_cache[nid] = n
        self.nodes.append(n)
        self.adj_list.setdefault(nid, [])
        return n

    def _add_edge(self, e1, e2, get_id):
        """Add directed edge (e1 -> e2). If e2 is None, just register e1."""
        node1 = self._get_node(e1, get_id)
        node2 = self._get_node(e2, get_id)
        if fn.no_null(node1):
            self.adj_list.setdefault(node1.id, [])
        if fn.no_null(node2):
            self.adj_list.setdefault(node2.id, [])
        if fn.no_null(node1, node2):
            self.adj_list[node1.id].append(node2)

    def _resolve_id(self, target):
        """
        Normalize `target` to an internal node_id.
        Accepts: Node | node_id | node.value (if unique).
        """
        if isinstance(target, Node):
            return target.id
        if target in self.node_cache:
            return target
        for nid, node in self.node_cache.items():
            if node.value == target:
                return nid
        raise KeyError(f"Unknown node '{target}'")

    # ------------------------------------------------------------------
    # Generic DFS (parametric on adjacency)
    # ------------------------------------------------------------------
    def _dfs_with_adj(self, target, func_check_node, adj, visited=None):
        """
        DFS using given adjacency dict: node_id -> [Node neighbors...].
        func_check_node(path, node) may return:
          - DONE: stop and return results
          - non-None: value appended to results
          - None: collect nothing for this node
        """
        start_id = self._resolve_id(target)
        start_node = self.node_cache[start_id]

        stack = [(start_node, [])]
        if visited is None:
            visited = set()
        results = []

        while stack:
            node, path = stack.pop()
            if fn.is_null(node) or node.id in visited:
                continue

            rs = func_check_node(path, node)
            if rs is DONE:
                return results
            elif rs is not None:
                results.append(rs)

            visited.add(node.id)
            for nei in adj.get(node.id, []):
                stack.append((nei, path + [node]))

        return [x for x in results if x]

    # ------------------------------------------------------------------
    # Traversals (forward & upstream)
    # ------------------------------------------------------------------
    def bfs(self, root, func_check_node=lambda x,y:y, visited=None):
        """
        Forward BFS (downstream dependents). Who depends on `root`?
        """
        graph = self.adj_list
        start_id = self._resolve_id(root)
        root = self.node_cache[start_id]
        queue = deque([(root, [])])
        if visited is None:
            visited = set()
        results = []

        while queue:
            node, path = queue.popleft()
            if fn.is_null(node) or node.id in visited:
                continue

            rs = func_check_node(path, node)
            if rs is DONE:
                return results
            elif rs is not None:
                results.append(rs)

            visited.add(node.id)
            for child in graph.get(node.id, []):
                queue.append((child, path + [node]))

        return results

    def dfs(self, root, func_check_node=lambda x,y:y, visited=None):
        """Forward DFS (downstream dependents)."""
        return self._dfs_with_adj(root, func_check_node, self.adj_list, visited)

    def dfs_upstream(self, root, func_check_node, visited=None):
        """Upstream DFS (reverse edges). Who does `root` depend on?"""
        return self._dfs_with_adj(root, func_check_node, self.rev_adj_list, visited)

    def dfs_post_order(self, root, func_check_node, visited=None):
        """
        Forward post-order DFS (process node after children).
        """
        graph = self.adj_list
        stack = [(root, [], False)]
        if visited is None:
            visited = set()
        results = []

        while stack:
            node, path, children_processed = stack.pop()
            if fn.is_null(node) or node.id in visited:
                continue

            if children_processed:
                rs = func_check_node(path, node)
                if rs is DONE:
                    return results
                elif fn.no_null(rs):
                    results.append(rs)
                visited.add(node.id)
            else:
                stack.append((node, path, True))
                for child in reversed(graph.get(node.id, [])):
                    stack.append((child, path + [node], False))

        return results

    # ------------------------------------------------------------------
    # Dependencies (upstream) API
    # ------------------------------------------------------------------
    def get_all_dependencies(self, target, include_self=False, topo_sorted=False):
        """
        Return all upstream dependencies (ancestors) of `target` as list[Node].
        If topo_sorted=True, return them in global topological (build) order.
        """
        start_id = self._resolve_id(target)
        start_node = self.node_cache[start_id]

        def collect(_, node):
            return node  # collect Node objects

        nodes = self.dfs_upstream(start_node, collect, visited=set())

        if not include_self:
            nodes = [n for n in nodes if n.id != start_id]

        if not topo_sorted:
            return nodes

        wanted = {n.id for n in nodes}
        topo = self.topological_sort()
        return [n for n in topo if n.id in wanted]

    def get_all_dependents(self, target, include_self=False, topo_sorted=False):
        """
        Return all downstream dependents (descendants) of `target` as list[Node].
        These are nodes that directly or indirectly depend on `target`.
        If topo_sorted=True, return them in global topological (build) order.
        """
        start_id = self._resolve_id(target)

        nodes = self.dfs(target)

        if not include_self:
            nodes = [n for n in nodes if n.id != start_id]

        if not topo_sorted:
            return nodes

        wanted = {n.id for n in nodes}
        topo = self.topological_sort()
        return [n for n in topo if n.id in wanted]

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------
    def topological_sort(self):
        """
        Return list[Node] in topological order (Kahn's algorithm).
        Raises ValueError on cycles.
        """
        indegree = {n.id: 0 for n in self.nodes}
        for parent_id, children in self.adj_list.items():
            for child in children:
                indegree[child.id] = indegree.get(child.id, 0) + 1

        q = deque(self.node_cache[nid] for nid, d in indegree.items() if d == 0)
        order = []
        indeg = dict(indegree)

        while q:
            node = q.popleft()
            order.append(node)
            for child in self.adj_list.get(node.id, []):
                indeg[child.id] -= 1
                if indeg[child.id] == 0:
                    q.append(child)

        if len(order) != len(indegree):
            raise ValueError("Graph has a cycle or unresolved dependencies")

        return order
