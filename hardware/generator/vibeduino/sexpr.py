"""Minimal S-expression reader/writer for KiCad files (keeps quoted strings quoted)."""

import re


class Q(str):
    """A quoted string atom."""


_TOKEN = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')


def parse(text):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif t.startswith('"'):
            stack[-1].append(Q(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(t)
    return stack[0]


def dump(node, indent=0):
    """Serialise, keeping child order; short all-atom lists stay on one line."""
    if isinstance(node, list):
        if not node:
            return "()"
        if all(not isinstance(c, list) for c in node) or (
                len(node) <= 4 and all(not isinstance(c, list) or
                                       all(not isinstance(x, list) for x in c) for c in node)):
            return "(" + " ".join(dump(c) for c in node) + ")"
        pad = "  " * (indent + 1)
        out = "(" + dump(node[0])
        after_list = False
        for c in node[1:]:
            if isinstance(c, list):
                out += "\n" + pad + dump(c, indent + 1)
                after_list = True
            elif after_list:
                out += "\n" + pad + dump(c)
            else:
                out += " " + dump(c)
        return out + "\n" + "  " * indent + ")"
    if isinstance(node, Q):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(node, float):
        s = f"{node:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(node)


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None
