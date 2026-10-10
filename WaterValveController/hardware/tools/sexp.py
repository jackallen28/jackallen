import re
def parse(text):
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0]
def dump(x, indent=0):
    if isinstance(x, list):
        if all(not isinstance(i, list) for i in x):
            return '(' + ' '.join(x) + ')'
        parts = [dump(i, indent + 1) for i in x]
        return '(' + parts[0] + ''.join('\n' + '  ' * (indent + 1) + p for p in parts[1:]) + ')'
    return x
def find_symbol(lib_path, name):
    tree = parse(open(lib_path).read())[0]
    for item in tree:
        if isinstance(item, list) and item[0] == 'symbol' and item[1].strip('"') == name:
            return item
    raise KeyError(name)
def pins(sym):
    out = []
    def walk(node, unit):
        for it in node:
            if isinstance(it, list):
                if it[0] == 'symbol':
                    walk(it, it[1].strip('"'))
                elif it[0] == 'pin':
                    at = next(i for i in it if isinstance(i, list) and i[0] == 'at')
                    ln = next(i for i in it if isinstance(i, list) and i[0] == 'length')
                    nm = next(i for i in it if isinstance(i, list) and i[0] == 'name')
                    nb = next(i for i in it if isinstance(i, list) and i[0] == 'number')
                    out.append(dict(unit=unit, type=it[1], x=float(at[1]), y=float(at[2]), rot=float(at[3]), len=float(ln[1]), name=nm[1].strip('"'), num=nb[1].strip('"')))
    walk(sym, sym[1])
    return out
