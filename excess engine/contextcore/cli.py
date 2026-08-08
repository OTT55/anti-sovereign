"""cli.py — the command-line entry point for the ContextCore engine. No Flask, no server.

    python cli.py ingest evalset/report.txt --title "Q3 Report"
    python cli.py ask CX-AB12CD34EF "what changed in Q3?"
    python cli.py list
    python cli.py graph CX-AB12CD34EF --out graph.svg
"""

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from contextcore_engine.engine import ContextCoreEngine  # noqa: E402

DB_PATH = Path(__file__).parent / "contextcore_engine.db"


def cmd_ingest(args, engine):
    text = Path(args.file).read_text(encoding="utf-8")
    title = args.title or Path(args.file).name
    result = engine.ingest_document(title, text, category=args.category, extract_entities=not args.no_extract)
    if result is None:
        print("No extractable text — nothing ingested.")
        return
    print(f"Ingested {result['doc_id']}  ({result['chunk_count']} chunks)")
    if args.no_extract:
        return
    print(f"  entities: {result['entity_count']}  relationships: {result['relationship_count']}")
    if result["extraction_note"]:
        print(f"  note: {result['extraction_note']}")


def cmd_ask(args, engine):
    result = engine.ask(args.doc_id, args.question)
    _print_answer(result)


def cmd_ask_collection(args, engine):
    result = engine.ask_collection(args.category, args.question)
    _print_answer(result)
    if result.conflict is not None:
        tag = "CONFLICT" if result.conflict["conflict"] else "no conflict"
        print(f"\n[{tag}] {result.conflict['explanation']}")
    elif result.conflict_note:
        print(f"\n[conflict check] {result.conflict_note}")


def _print_answer(result):
    print(f"\n[{result.mode}] {result.answer}\n")
    print(f"confidence: {result.confidence['level']} (top={result.confidence['top_score']}, gap={result.confidence['gap']})")
    if result.note:
        print(f"note: {result.note}")
    print("\ncitations:")
    for c in result.citations:
        print(f"  [{c['chunk']}] score={c['score']}  {c['preview']}")


def cmd_list(args, engine):
    docs = engine.list_documents(category=args.category)
    if not docs:
        print(f"No documents in category '{args.category}'.")
        return
    for d in docs:
        print(f"{d['doc_id']}  {d['title']}  ({d['chunk_count']} chunks, {d['created_at']})")


def cmd_graph(args, engine):
    nodes, edges, svg = engine.graph_for(args.doc_ids)
    print(f"{len(nodes)} nodes, {len(edges)} edges")
    if svg is None:
        print("No entities extracted for this document yet (needs ANTHROPIC_API_KEY at ingest time).")
        return
    out_path = Path(args.out)
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description="ContextCore — retrieval-augmented reasoning over your own documents.")
    parser.add_argument("--db", default=str(DB_PATH), help="SQLite path (default: contextcore_engine.db next to this file).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a text file.")
    p_ingest.add_argument("file")
    p_ingest.add_argument("--title")
    p_ingest.add_argument("--category", default="general")
    p_ingest.add_argument("--no-extract", action="store_true", help="Skip Claude entity/relationship extraction.")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="Ask a question of one document.")
    p_ask.add_argument("doc_id")
    p_ask.add_argument("question")
    p_ask.set_defaults(func=cmd_ask)

    p_ask_c = sub.add_parser("ask-collection", help="Ask a question across a whole category.")
    p_ask_c.add_argument("category")
    p_ask_c.add_argument("question")
    p_ask_c.set_defaults(func=cmd_ask_collection)

    p_list = sub.add_parser("list", help="List ingested documents.")
    p_list.add_argument("--category", default="general")
    p_list.set_defaults(func=cmd_list)

    p_graph = sub.add_parser("graph", help="Render the knowledge graph for one or more documents to SVG.")
    p_graph.add_argument("doc_ids", nargs="+")
    p_graph.add_argument("--out", default="graph.svg")
    p_graph.set_defaults(func=cmd_graph)

    args = parser.parse_args()
    with ContextCoreEngine(db_path=args.db) as engine:
        args.func(args, engine)


if __name__ == "__main__":
    main()
