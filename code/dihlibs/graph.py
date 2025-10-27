from collections import deque
import dihlibs.functions as fn
from dihlibs.node import Node  # update this import path if needed

# Sentinel to allow early stop in traversals
DONE = object()


class Graph:
    """
    Directed graph of Node objects.

    Each logical value (like "useview_chv") maps to exactly one Node(),
    and edges are stored as parent -> [children].

    Typical usage for dependency graphs:
    dep -> target
    meaning "dep must be processed before target".
    """

    def __init__(self, edges, func_get_id=None):
        """
        Build the graph from a list of edges.

        edges: iterable of (src, dst)
            src and dst are arbitrary payloads (often strings).
            dst can be None to mean "src exists but has no outgoing edges".

        func_get_id:
            Callable(value) -> hashable ID
            If not provided, defaults to Python's id().
            In most DAG/build cases, pass `lambda x: x`
            when x is already a unique string key.
        """
        get_id = func_get_id if func_get_id else id

        # node_cache maps node_id -> Node()
        self.node_cache = {}

        # adjacency list: node_id -> [Node children...]
        self.adj_list = {}

        # list of Node objects (1 per unique node in graph)
        self.nodes = []

        # actually build the graph
        for e1, e2 in edges:
            self._add_edge(e1, e2, get_id)

    # ------------------------------------------------------------------
    # Alternate constructor for reversed-dependency dicts
    # ------------------------------------------------------------------
    @classmethod
    def from_dependency_dict(cls, deps_dict, func_get_id=None):
        """
        Create a Graph from a dict shaped like:

            deps_dict[target] = [dep1, dep2, ...]

        interpreted as:
            target depends on dep1, dep2, ...

        That means each dep must come BEFORE target.

        For a DAG, topo sort should output:
            dep1, dep2, ..., target

        Internally we flip this into edges:
            dep -> target

        We ALSO include nodes with no deps ([]) so they don't get lost.
        """
        edges = []
        for target, deps_list in deps_dict.items():
            if deps_list:
                for dep in deps_list:
                    edges.append((dep, target))  # dep -> target
            else:
                # ensure isolated nodes still show up in the graph
                edges.append((target, None))

        return cls(edges, func_get_id=func_get_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_node(self, value, get_id):
        """
        Return the canonical Node() for 'value', creating it if missing.

        value can be None, in which case we return None.
        """
        if fn.is_null(value):
            return None

        nid = get_id(value)

        # reuse if we already created this node
        cached = self.node_cache.get(nid)
        if cached:
            return cached

        # create new Node wrapper
        n = Node()
        n.id = nid
        n.value = value

        self.node_cache[nid] = n
        self.nodes.append(n)

        # make sure node id exists in adjacency dict
        self.adj_list.setdefault(nid, [])

        return n

    def _add_edge(self, e1, e2, get_id):
        """
        Add an edge (e1 -> e2).
        If e2 is None, we just register e1 as a node.
        """
        node1 = self._get_node(e1, get_id)
        node2 = self._get_node(e2, get_id)

        # make sure both appear in adj_list even if no children
        if fn.no_null(node1):
            self.adj_list.setdefault(node1.id, [])
        if fn.no_null(node2):
            self.adj_list.setdefault(node2.id, [])

        # actual directed edge
        if fn.no_null(node1, node2):
            self.adj_list[node1.id].append(node2)

    # ------------------------------------------------------------------
    # Traversals
    # ------------------------------------------------------------------
    def bfs(self, root, func_check_node, visited=None):
        """
        Breadth-first search starting from Node 'root'.

        func_check_node(path, node) can return:
          - DONE (sentinel above) => stop traversal early and return results
          - any non-None value    => append that to results
          - None                  => nothing collected for this node

        'path' is a list of Node objects from the start node to node's parent.
        """
        graph = self.adj_list
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

    def dfs(self, root, func_check_node, visited=None):
        """
        Depth-first (pre-order) traversal using an explicit stack.

        Same func_check_node contract as bfs().
        """
        graph = self.adj_list
        stack = [(root, [])]
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

            for child in graph.get(node.id, []):
                stack.append((child, path + [node]))

        return results

    def dfs_post_order(self, root, func_check_node, visited=None):
        """
        Depth-first traversal that processes a node AFTER its children.
        This is classic post-order.

        We simulate recursion with a stack of:
           (node, path, children_processed_flag)

        func_check_node(path, node) runs when `children_processed_flag` is True.
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
                # push parent back, marked "ready to process after children"
                stack.append((node, path, True))

                # push children first so they get processed before parent
                for child in reversed(graph.get(node.id, [])):
                    stack.append((child, path + [node], False))

        return results

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------
    def topological_sort(self):
        """
        Return a list[Node] in topological order.

        Uses Kahn's algorithm (BFS over in-degree-0 nodes).

        Raises ValueError if a cycle is detected.
        """
        # 1. compute in-degrees
        indegree = {n.id: 0 for n in self.nodes}
        for parent_id, children in self.adj_list.items():
            for child in children:
                indegree[child.id] = indegree.get(child.id, 0) + 1

        # 2. init queue with all in-degree-0 nodes
        q = deque(
            self.node_cache[node_id]
            for node_id, deg in indegree.items()
            if deg == 0
        )

        topo_order = []
        indegree_mut = dict(indegree)

        # 3. pop nodes with in-degree 0, "remove" their edges
        while q:
            node = q.popleft()
            topo_order.append(node)

            for child in self.adj_list.get(node.id, []):
                indegree_mut[child.id] -= 1
                if indegree_mut[child.id] == 0:
                    q.append(child)

        # 4. if we didn't output all nodes, there's a cycle
        if len(topo_order) != len(indegree):
            raise ValueError("Graph has a cycle or unresolved dependencies")

        return topo_order
