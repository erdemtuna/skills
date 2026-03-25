#!/usr/bin/env python3
"""Extract inline images from an ODT file and fix broken placeholders in the markdown."""

import argparse
import os
import re
import zipfile


def extract_images(odt_path: str, md_path: str, embed_dir: str, basename: str) -> None:
    os.makedirs(embed_dir, exist_ok=True)

    with zipfile.ZipFile(odt_path, "r") as z:
        image_files = sorted(
            n
            for n in z.namelist()
            if (n.startswith("Pictures/") or n.startswith("media/"))
            and not n.endswith("/")
        )
        for img in image_files:
            data = z.read(img)
            fname = os.path.basename(img)
            out = os.path.join(embed_dir, fname)
            with open(out, "wb") as f:
                f.write(data)
            print(f"Extracted: {out} ({len(data):,} bytes)")

    with open(md_path, "r") as f:
        content = f.read()

    if "[]{.image}" in content and image_files:
        counter = [0]

        def replace_placeholder(m):
            counter[0] += 1
            if counter[0] <= len(image_files):
                fname = os.path.basename(image_files[counter[0] - 1])
                return f"![Image {counter[0]}]({basename}-embedded/{fname})"
            return m.group(0)

        content = re.sub(r"\[\]\{\.image\}", replace_placeholder, content)
        with open(md_path, "w") as f:
            f.write(content)
        print(f"Fixed {counter[0]} image placeholders in markdown")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract images from ODT and fix markdown placeholders")
    parser.add_argument("odt", help="Path to the .odt file")
    parser.add_argument("md", help="Path to the generated .md file")
    parser.add_argument("embed_dir", help="Path to the embedded media directory")
    parser.add_argument("basename", help="Base name of the document (for relative refs)")
    args = parser.parse_args()

    extract_images(args.odt, args.md, args.embed_dir, args.basename)
