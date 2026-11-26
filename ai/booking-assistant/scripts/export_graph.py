#!/usr/bin/env python3
"""Export the current LangGraph topology as Mermaid, without calling a model."""

import argparse
from pathlib import Path

from agent.graph import build_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write Mermaid here; otherwise print it")
    args = parser.parse_args()
    mermaid = build_graph().get_graph().draw_mermaid()
    if args.output:
        args.output.write_text(mermaid + "\n", encoding="utf-8")
    else:
        print(mermaid)


if __name__ == "__main__":
    main()
