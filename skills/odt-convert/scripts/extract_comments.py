#!/usr/bin/env python3
"""Extract threaded comments from an ODT file into a structured Markdown file."""

import argparse
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict

NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS = {"office": NS_OFFICE, "text": NS_TEXT, "dc": NS_DC}


def _extract_text_from_xml(xml_fragment: str) -> str:
    """Extract visible text from an XML fragment, handling ODT whitespace elements."""
    xml_fragment = re.sub(
        r"<office:annotation\b.*?</office:annotation>", "", xml_fragment, flags=re.DOTALL
    )
    xml_fragment = re.sub(r"<text:s[^/]*/>", " ", xml_fragment)
    xml_fragment = re.sub(r"<text:s/>", " ", xml_fragment)
    xml_fragment = re.sub(r"<text:tab[^/]*/>", "\t", xml_fragment)
    xml_fragment = re.sub(r"<text:line-break[^/]*/>", "\n", xml_fragment)
    text = re.sub(r"<[^>]+>", "", xml_fragment)
    return re.sub(r"\s+", " ", text).strip()


def extract_comments(odt_path: str, output_path: str) -> None:
    with zipfile.ZipFile(odt_path, "r") as z:
        content = z.read("content.xml").decode("utf-8")

    # Locate annotation start/end positions in raw XML
    starts = {
        m.group(1): m.end()
        for m in re.finditer(
            r'<office:annotation\s+office:name="(\d+)"[^>]*>.*?</office:annotation>',
            content,
            re.DOTALL,
        )
    }
    ends = {
        m.group(1): m.start()
        for m in re.finditer(r'<office:annotation-end\s+office:name="(\d+)"', content)
    }

    root = ET.fromstring(content)
    annotations = root.findall(f".//{{{NS_OFFICE}}}annotation")

    comments = []
    for ann in annotations:
        name = ann.get(f"{{{NS_OFFICE}}}name")
        author_el = ann.find("dc:creator", NS)
        date_el = ann.find("dc:date", NS)
        paragraphs = ann.findall(f".//{{{NS_TEXT}}}p")
        text = "\n".join(
            t.strip() for p in paragraphs for t in ["".join(p.itertext())] if t.strip()
        )

        s, e = starts.get(name), ends.get(name)
        anchor = _extract_text_from_xml(content[s:e]) if s and e and e > s else ""

        comments.append(
            {
                "name": name,
                "author": author_el.text if author_el is not None else "",
                "date": date_el.text if date_el is not None else "",
                "text": text,
                "anchor": anchor,
                "start": s or 0,
            }
        )

    # Group into threads by anchor text, preserving document order
    threads: OrderedDict = OrderedDict()
    for c in comments:
        key = c["anchor"] or f"_no_anchor_{c['name']}"
        threads.setdefault(key, []).append(c)

    for key in threads:
        threads[key].sort(key=lambda c: c["date"])

    # Write threaded comments file
    filename = odt_path.split("/")[-1]
    lines = [f"# Comments from {filename}\n\n"]
    lines.append(f"**Total:** {len(comments)} comments in {len(threads)} threads\n\n---\n\n")

    for thread_num, (anchor, thread_comments) in enumerate(threads.items(), 1):
        is_thread = len(thread_comments) > 1
        lines.append(f"## Thread {thread_num}")
        if is_thread:
            lines.append(f" ({len(thread_comments)} replies)")
        lines.append("\n\n")

        if anchor and not anchor.startswith("_no_anchor_"):
            lines.append(f"> **Anchor:** {anchor}\n\n")

        for i, c in enumerate(thread_comments):
            prefix = "💬" if i == 0 else "↩️"
            lines.append(f'{prefix} **{c["author"]}** — {c["date"]}\n\n')

            if is_thread and i > 0:
                for line in c["text"].split("\n"):
                    lines.append(f"> {line}\n")
                lines.append("\n")
            else:
                lines.append(f'{c["text"]}\n\n')

        lines.append("---\n\n")

    with open(output_path, "w") as f:
        f.writelines(lines)

    print(f"Saved {len(comments)} comments in {len(threads)} threads to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract threaded comments from ODT to Markdown")
    parser.add_argument("odt", help="Path to the .odt file")
    parser.add_argument("output", help="Path for the output comments .md file")
    args = parser.parse_args()

    extract_comments(args.odt, args.output)
