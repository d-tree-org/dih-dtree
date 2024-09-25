import json
from collections import namedtuple
import dihlibs.functions as fn
from dihlibs.node import Node
from collections import deque
import numpy as np

DONE = object()


class Graph:
    def __init__(self, edges, func_get_id=None):
        get_id = func_get_id if func_get_id else id
        self.adj_list = {get_id(n[0]): [] for n in edges}
        self.nodes = []
        for edge in edges:
            self._add_edge(edge, get_id)

    def _add_edge(self, edge, get_id):
        e1, e2 = edge
        node1 = Node()
        node2 = Node()
        node1.id = get_id(e1)
        node2.id = get_id(e2)
        if fn.no_null(e1):
            self.nodes.append(node1)
            node1.value = e1
        if fn.no_null(e2):
            self.nodes.append(node2)
            node2.value = e2
        if fn.no_null(e1, e2):
            self.adj_list[node1.id].append(node2)

    def bfs(self, root, func_check_node,visited=None):
        graph = self.adj_list
        queue = deque([(root, [])])
        if visited is None:
            visited = set()
        results = []
        while queue:
            node, path = queue.popleft()
            if fn.is_null(node) or node.id in visited:
                continue
            elif (rs := func_check_node(path, node)) is DONE:
                return results
            elif rs is not None:
                results.append(rs)

            visited.add(node.id)
            for child in graph.get(node.id, []):
                queue.append((child, path + [node]))
        return results

    def dfs(self, root, func_check_node,visited=None):
        graph = self.adj_list
        stack = [(root, [])]
        if visited is None:
            visited = set()
        results = []

        while stack:
            node, path = stack.pop()

            if fn.is_null(node) or node.id in visited:
                continue
            elif (rs := func_check_node(path, node)) is DONE:
                return results
            elif rs is not None:
                results.append(rs)

            visited.add(node.id)

            for child in graph.get(node.id, []):
                stack.append((child, path + [node]))
        return results

    def dfs_post_order(self, root, func_check_node,visited):
        graph = self.adj_list
        stack = [
            (root, [], False)
        ]  # The third element in the tuple indicates if children are processed
        if visited is None:
            visited = set()
        results = []

        while stack:
            node, path, children_processed = stack.pop()
            if fn.is_null(node) or node.id in visited:
                continue

            if children_processed:
                # Process the parent node after all children have been processed
                if (rs := func_check_node(path, node)) is DONE:
                    return results
                elif fn.no_null(rs):
                    results.append(rs)
                visited.add(node.id)
            else:
                # Push the parent node back onto the stack, indicating that its children will be processed next
                stack.append((node, path, True))
                # Push all children onto the stack to be processed first
                for child in reversed(graph.get(node.id, [])):
                    stack.append((child, path + [node], False))
        return results

    def topological_sort(self):
        results = []
        visited = set()
        for root in self.nodes:
            if root.id in visited:
                continue
            res = self.dfs_post_order(root, lambda _, x: x,visited)
            results = results + res
            res = [n for n in res if n.id not in visited]
            for n in res:
                visited.add(n.id)
        return results
