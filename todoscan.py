#!/usr/bin/env python3
"""todoscan - scan a directory tree for TODO/FIXME/HACK/XXX comments (read-only)."""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

TAGS = ("TODO", "FIXME", "HACK", "XXX")
SKIP_DIRS = {
    "node_modules", "build", ".git", ".gradle", "venv", ".venv", "env",
    "__pycache__", "site-packages", "dist", ".idea", ".tox", ".mypy_cache",
}
EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs", ".rb", ".php", ".swift",
    ".sh", ".bash", ".zsh", ".sql", ".lua", ".pl", ".r", ".scala", ".dart",
    ".html", ".css", ".scss", ".xml", ".yml", ".yaml", ".toml", ".gradle",
    ".vue", ".svelte", ".md", ".txt", ".ini", ".cfg",
}
# tag must follow a comment marker (//, #, /*, *, --, <!--, ;) to count as a comment
PATTERN = re.compile(
    r"(?://|#|/\*|\*|--|<!--|;|\"\"\"|''')\s*.*?\b(" + "|".join(TAGS) + r")\b\s*(?:\([^)]*\))?\s*[:\-]?\s*(.*)"
)
MAX_SIZE = 2 * 1024 * 1024


def default_exclude_file():
    return os.environ.get("DEVTOOLS_EXCLUDE_FILE") or os.path.join(
        os.path.expanduser("~"), ".config", "devtools", "exclude")


def load_exclude_file(path=None):
    """Directory names from the exclude config (one per line, # comments). Missing file = none."""
    path = path or default_exclude_file()
    names = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    names.add(line)
    except OSError:
        pass
    return names


def is_binary(path):
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(4096)
    except OSError:
        return True


def iter_files(root, exclude=()):
    exclude = set(exclude)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and d not in exclude and not os.path.exists(os.path.join(dirpath, d, "pyvenv.cfg"))
        )
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() not in EXTS:
                continue
            p = os.path.join(dirpath, name)
            try:
                if os.path.islink(p) or os.path.getsize(p) > MAX_SIZE:
                    continue
            except OSError:
                continue
            if not is_binary(p):
                yield p


def scan_file(path):
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                m = PATTERN.search(line)
                if m:
                    text = m.group(2).strip().rstrip("*/>-").strip()
                    results.append({"line": n, "tag": m.group(1), "text": text})
    except OSError:
        pass
    return results


def blame(path, line):
    """Author for a line via read-only git blame; None if unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", os.path.dirname(os.path.abspath(path)), "blame", "-L",
             f"{line},{line}", "--porcelain", "--", os.path.basename(path)],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        for l in out.stdout.splitlines():
            if l.startswith("author "):
                return l[7:]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def scan(root, tags=None, use_blame=False, exclude=()):
    tags = {t.upper() for t in tags} if tags else set(TAGS)
    items = []
    for path in iter_files(root, exclude):
        for r in scan_file(path):
            if r["tag"] not in tags:
                continue
            r["file"] = os.path.relpath(path, root)
            if use_blame:
                r["author"] = blame(path, r["line"])
            items.append(r)
    return items


def format_text(items):
    by_file = defaultdict(list)
    for r in items:
        by_file[r["file"]].append(r)
    lines = []
    for f in sorted(by_file):
        lines.append(f)
        for r in by_file[f]:
            a = f" [{r['author']}]" if r.get("author") else ""
            lines.append(f"  {f}:{r['line']}: {r['tag']} {r['text']}{a}")
    return "\n".join(lines)


def summary(items):
    return {
        "total": len(items),
        "by_tag": dict(Counter(r["tag"] for r in items)),
        "by_file": dict(Counter(r["file"] for r in items)),
    }


def format_summary(items):
    s = summary(items)
    lines = [f"Total: {s['total']}", "By tag:"]
    lines += [f"  {t}: {c}" for t, c in sorted(s["by_tag"].items())]
    lines.append("By file:")
    lines += [f"  {c:4d}  {f}" for f, c in sorted(s["by_file"].items(), key=lambda x: (-x[1], x[0]))]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan for TODO/FIXME/HACK/XXX comments.")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--tag", action="append", help="limit to tag (repeatable)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--blame", action="store_true", help="add author via git blame")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME",
                    help="directory name to never enter (repeatable); also read from "
                         "~/.config/devtools/exclude")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.path):
        print(f"not a directory: {args.path}", file=sys.stderr)
        return 2
    items = scan(args.path, args.tag, args.blame,
                 load_exclude_file() | set(args.exclude))
    if args.json:
        out = {"summary": summary(items), "items": items} if args.summary else items
        print(json.dumps(out, indent=2))
    elif args.summary:
        print(format_summary(items))
    else:
        print(format_text(items) or "No matches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
