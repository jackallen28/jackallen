"""The code review coach: tips on HOW code is written, not whether it works.

A teacher reading over a student's shoulder looks for the same few things, and so does this:
repeated code, magic numbers, unclear names, a long program with no functions, input that isn't
validated, `global`, bare `except:`, deep nesting, and functions that have never been tested.
Each tip names the Year 9-10 idea behind it (modular programs, validation, test cases...).
Standard library only (ast); no AI.

    tips = review(code)        # [Tip(title, text, idea), ...], most useful first
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass

OK_NUMBERS = {0, 1, 2, -1, 10, 100, 1000, 0.5, 0.1}
SHORT_OK = {"i", "j", "k", "n", "x", "y", "_", "e", "f"}
MAX_TIPS = 3


@dataclass
class Tip:
    title: str
    text: str          # markdown
    idea: str          # the computing idea, e.g. "Modular programs"


def review(code: str, max_tips: int = MAX_TIPS) -> list[Tip]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    tips: list[tuple[int, Tip]] = []         # (priority, tip): lower comes first
    for check in (_repeated_code, _no_functions, _input_not_validated, _magic_numbers, _bare_except,
                  _globals, _short_names, _deep_nesting, _long_functions, _untested_functions):
        found = check(tree, code)
        if found:
            tips.append(found)
    tips.sort(key=lambda t: t[0])
    return [t for _p, t in tips[:max_tips]]


# ---------------------------------------------------------------- the checks

def _stmt_key(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False)


def _repeated_code(tree: ast.Module, code: str):
    """The same line(s) written out again and again: a loop or a function would do it once."""
    for body in _bodies(tree):
        keys = [_stmt_key(s) for s in body if not isinstance(s, (ast.FunctionDef, ast.ClassDef, ast.Import,
                                                                   ast.ImportFrom))]
        # a run of the same two-line pattern 3+ times, or one line 4+ times in a row
        for size in (3, 2, 1):
            need = 3 if size > 1 else 4
            for start in range(len(keys) - size * need + 1):
                chunk = keys[start:start + size]
                if all(keys[start + k * size:start + (k + 1) * size] == chunk for k in range(need)):
                    return 1, Tip("Don't repeat yourself",
                                  f"The same {'lines are' if size > 1 else 'line is'} written out {need} times or "
                                  "more in a row. Put them in a `for` loop (or a function) so they're written "
                                  "once. Shorter code is easier to read, test and change.",
                                  "Modular programs")
    # two functions-worth of code repeated anywhere
    lines = [l.strip() for l in code.splitlines() if l.strip() and not l.strip().startswith("#")]
    pairs = Counter(zip(lines, lines[1:], lines[2:]))
    if any(n >= 3 and len("".join(p)) > 40 for p, n in pairs.items()):
        return 2, Tip("Spot the pattern",
                      "A block of three lines appears three times. Could it become a function with a "
                      "parameter for the part that changes?", "Modular programs")
    return None


def _no_functions(tree: ast.Module, code: str):
    top = [s for s in tree.body if not isinstance(s, (ast.Import, ast.ImportFrom, ast.Expr))]
    has_def = any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in ast.walk(tree))
    count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.stmt))
    if not has_def and count >= 25 and len(top) >= 12:
        return 2, Tip("Break it into parts",
                      f"Your program is {count} statements long with no functions. Decompose it: give each "
                      "job its own `def` with a clear name (like `read_sensor()` or `show_score()`), then "
                      "the main part reads like a plan.", "Decomposition")
    return None


def _input_not_validated(tree: ast.Module, code: str):
    """int(input(...)) with no try/except: one typo crashes the program."""
    inside_try = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Try) and any(h.type is None or "ValueError" in ast.unparse(h.type) for h in n.handlers):
            inside_try.update(id(x) for x in ast.walk(n))
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("int", "float")
                and n.args and isinstance(n.args[0], ast.Call) and getattr(n.args[0].func, "id", "") == "input"
                and id(n) not in inside_try):
            return 3, Tip("Validate the input",
                          f"Line {n.lineno} turns typed text into a number. What if someone types `ten`? "
                          "Catch it: put it in `try:` / `except ValueError:` inside a loop that asks again. "
                          "Real programs never trust input.", "Validating data")
    return None


def _magic_numbers(tree: ast.Module, code: str):
    nums = Counter()
    first = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            if n.value not in OK_NUMBERS:
                nums[n.value] += 1
                first.setdefault(n.value, n.lineno)
    repeated = [v for v, c in nums.most_common() if c >= 3]
    if repeated:
        v = repeated[0]
        return 4, Tip("Name your numbers",
                      f"The number `{v}` appears {nums[v]} times (first on line {first[v]}). Give it a name at "
                      f"the top, like `DELAY = {v}`, and use the name. Then one change updates them all, and "
                      "the code says what the number *means*.", "Readable, maintainable code")
    return None


def _bare_except(tree: ast.Module, code: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler) and n.type is None:
            return 3, Tip("Catch the error you expect",
                          f"`except:` on line {n.lineno} catches *every* error, even typos in your own code, so "
                          "bugs hide. Name the one you expect, like `except ValueError:` or "
                          "`except FileNotFoundError:`.", "Testing and debugging")
    return None


def _globals(tree: ast.Module, code: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.Global):
            return 6, Tip("Fewer globals",
                          f"`global {', '.join(n.names)}` (line {n.lineno}) works, but it lets any function "
                          "change that value. Next step up: pass values in as parameters and `return` the new "
                          "value, or keep the state inside a class (object-oriented programming).",
                          "Modular programs")
    return None


def _short_names(tree: ast.Module, code: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and len(t.id) == 1 and t.id not in SHORT_OK:
                    return 5, Tip("Choose clear names",
                                  f"`{t.id}` (line {n.lineno}) doesn't say what it holds. A name like `score`, "
                                  "`distance_cm` or `red_led` makes your code explain itself.",
                                  "Readable, maintainable code")
    return None


def _deep_nesting(tree: ast.Module, code: str):
    def depth(node, d=0):
        best = d
        for child in ast.iter_child_nodes(node):
            inc = isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With))
            best = max(best, depth(child, d + inc))
        return best
    d = depth(tree)
    if d >= 5:
        return 5, Tip("Flatten it out",
                      f"Some code is {d} blocks deep (ifs inside loops inside ifs...). Move the inner part into "
                      "a function, or use `elif` and early `return`/`continue`, so it's easier to follow.",
                      "Algorithms")
    return None


def _long_functions(tree: ast.Module, code: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            length = (n.end_lineno or n.lineno) - n.lineno
            if length > 35:
                return 5, Tip("One job per function",
                              f"`{n.name}()` is {length} lines long. Could it be two or three smaller functions, "
                              "each with one job and a name that says what it does?", "Modular programs")
    return None


def _untested_functions(tree: ast.Module, code: str):
    """Functions that return values but are never checked with a test case."""
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and any(isinstance(r, ast.Return) and r.value is not None for r in ast.walk(n))
             and not any(isinstance(a, ast.Attribute) for a in ast.walk(n))]     # pure-ish: no hardware
    if funcs and not any(isinstance(n, ast.Assert) for n in ast.walk(tree)):
        f = funcs[0]
        return 7, Tip("Test it with a test case",
                      f"`{f.name}()` returns a value, so you can test it. Before the main code, add a line "
                      f"like `assert {f.name}(...) == ...` with an input where you know the answer. If it's "
                      "ever wrong, Python stops and tells you.", "Validating programs with test cases")
    return None


def _bodies(tree: ast.AST):
    """Every list of statements: the module, and the body of each function, loop and if."""
    for n in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            body = getattr(n, field, None)
            if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
                yield body
