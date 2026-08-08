"""Tokenization and chunking. Pure text in, pure data out — no I/O, no framework."""

import re

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be been being this that "
    "these those it its as at by from into out over under then than so such but if "
    "how what when where who whom which why do does did done has have had not no".split()
)


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def chunk_text(text, target=600):
    """Split into ~`target`-character chunks on paragraph/sentence boundaries."""
    paras = re.split(r"\n\s*\n", text.strip())
    chunks, buf = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 <= target:
            buf = (buf + "\n\n" + p).strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) > target:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) + 1 <= target:
                        buf = (buf + " " + s).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = s
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks
