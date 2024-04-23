import json
from collections import namedtuple
import dihlibs.functions as fn


Graph = namedtuple("Graph", ["get"])


class Node:
    # class Node(JSONSerializable):
    def __init__(self, dictionary=None):
        self._dict = dictionary if isinstance(dictionary, dict) else {}

    def __getattr__(self, attr):
        if attr.startswith("_"):
            # If attribute starts with '_', it's a built-in attribute or method
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}'"
            )
        return self._dict.get(attr)

    def __setattr__(self, attr, value):
        if attr.startswith("_"):
            # If attribute starts with '_', set it normally to avoid recursion
            super().__setattr__(attr, value)
        else:
            self._dict[attr] = value

    def __getitem__(self, key):
        return self._dict.get(key)

    def __setitem__(self, key, value):
        self._dict[key] = value

    def __json__(self):
        return self.json()

    def json(self):
        return json.dumps(self.to_dict())

    def __dict__(self):
        return self.to_dict()

    def to_dict(self):
        def get_dict(x):
            return x._dict if hasattr(x, "_dict") else x

        return fn.walk(self._dict, get_dict)

    def get(self, field, defaultValue=None):
        return fn.get(self._dict, field, defaultValue)

    def __str__(self):
        return json.dumps(self._dict, indent=2)

    def __repr__(self):
        return f"Node ({json.dumps(self._dict,indent=2)})"

    @staticmethod
    def nodify(data, id_path=None, get_id=lambda n: n.get("id")):
        if id_path:
            return [Node({**d, "node_id": fn.get(d, id_path)}) for d in data]
        if get_id:
            return [Node({**d, "node_id": get_id(d)}) for d in data]
        return [Node(x) for x in data] if data else []
