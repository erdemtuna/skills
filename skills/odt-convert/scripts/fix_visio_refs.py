#!/usr/bin/env python3
"""Fix ObjectReplacements references in pandoc-generated markdown to point at extracted Visio files."""

import argparse
import re


def fix_visio_refs(md_path: str, embed_dir_rel: str) -> None:
    with open(md_path, "r") as f:
        content = f.read()

    def replace_ref(m):
        num = m.group(1)
        return (
            f"![Visio Diagram {num}]({embed_dir_rel}/object-{num}.png)\n\n"
            f"[📎 Visio source]({embed_dir_rel}/object-{num}.vsdx)"
        )

    updated = re.sub(
        r"!\[\]\(ObjectReplacements/Object (\d+)\)\{[^}]*\}",
        replace_ref,
        content,
    )

    if updated != content:
        with open(md_path, "w") as f:
            f.write(updated)
        print("Fixed Visio ObjectReplacements references in markdown")
    else:
        print("No ObjectReplacements references found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix Visio references in pandoc markdown output")
    parser.add_argument("md", help="Path to the .md file")
    parser.add_argument("embed_dir_rel", help="Relative path to the embedded media directory (for markdown refs)")
    args = parser.parse_args()

    fix_visio_refs(args.md, args.embed_dir_rel)
