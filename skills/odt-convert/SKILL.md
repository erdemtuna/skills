---
name: odt-convert
description: Convert ODT (OpenDocument Text) files to Markdown, with a separate threaded comments file. Extracts document body via pandoc and comment threads (with anchor text and reply grouping) via Python XML parsing. Also extracts embedded images and Visio diagrams (with PNG export). Triggers include 'convert odt', 'extract odt comments', 'odt to markdown', or when working with .odt files.
---

# ODT to Markdown + Comments Skill

## Overview

Convert an `.odt` file into companion output files:

1. **`<name>.md`** — The document body, converted via `pandoc`, with image refs updated to point at exported artifacts.
2. **`<name>-comments.md`** — All document comments, grouped into threads with anchor text and chronological reply ordering.
3. **`<name>-embedded/`** — Subdirectory for all extracted media:
   - Inline images extracted by pandoc (PNG, JPEG, SVG, etc. from `Pictures/`)
   - **`object-<N>.vsdx`** + **`object-<N>.png`** — Visio diagrams with PNG previews.

## When to Use This Skill

- User asks to convert an `.odt` file to Markdown
- User asks to extract or review comments from an `.odt` file
- User provides an `.odt` file path and wants readable output

## Prerequisites

- `pandoc` must be installed (`pandoc --version`)
- Python 3 with standard library (`zipfile`, `xml.etree.ElementTree`, `re`, `io`)
- `olefile` Python package (install via `pip install olefile` if needed — only required for Visio extraction)
- `libreoffice` (headless mode) for converting EMF previews of Visio diagrams to PNG

## Workflow

### Step 1: Validate Input

Confirm the `.odt` file exists and is a valid OpenDocument file:

```bash
file <path>.odt
```

### Step 2: Convert Document Body

Use pandoc to convert the document body to Markdown, placing the output alongside the source. Use `--extract-media` to pull out any inline images into the shared `<name>-embedded/` directory:

```bash
pandoc <path>.odt -t markdown -o <path>.md --wrap=none --extract-media=<dir>/<name>-embedded
```

The `--wrap=none` flag prevents pandoc from inserting hard line breaks. The `--extract-media` flag extracts any images pandoc recognizes into the `<name>-embedded/` subdirectory and rewrites image references in the markdown accordingly. If no images are extracted and no OLE objects exist, remove the empty directory.

### Step 3: Extract Embedded Images and Visio Diagrams

ODT files are ZIP archives that can contain:
- **`Pictures/`** or **`media/`** — Inline images (PNG, JPEG, SVG, etc.) referenced by the document. Pandoc's `--extract-media` handles `Pictures/` but may fail on `media/` paths, emitting `[]{.image}` placeholders instead.
- **`Object N`** — OLE-embedded objects (e.g., Visio diagrams, Excel sheets). These are NOT handled by pandoc and require separate extraction into the `<name>-embedded/` directory.
- **`ObjectReplacements/Object N`** — EMF/WMF preview renderings of each embedded object, used by LibreOffice for display.

#### Extracting Inline Images

After pandoc runs, check if images were actually extracted. If the markdown contains `[]{.image}` placeholders, pandoc failed to extract them. Manually extract from the ODT zip:

```python
import zipfile, os, re

INPUT_PATH = "<path>.odt"
MD_PATH = "<path>.md"
EMBED_DIR = "<dir>/<name>-embedded"
BASENAME = "<name>"

os.makedirs(EMBED_DIR, exist_ok=True)

# Extract images from Pictures/ or media/ directories
with zipfile.ZipFile(INPUT_PATH, 'r') as z:
    image_files = sorted([n for n in z.namelist()
                          if (n.startswith('Pictures/') or n.startswith('media/'))
                          and not n.endswith('/')])
    for img in image_files:
        data = z.read(img)
        fname = os.path.basename(img)
        out = os.path.join(EMBED_DIR, fname)
        with open(out, 'wb') as f:
            f.write(data)
        print(f'Extracted: {out} ({len(data):,} bytes)')

# Fix []{.image} placeholders in markdown (sequential replacement)
with open(MD_PATH, 'r') as f:
    content = f.read()

if '[]{.image}' in content and image_files:
    counter = [0]
    def replace_placeholder(m):
        counter[0] += 1
        if counter[0] <= len(image_files):
            fname = os.path.basename(image_files[counter[0] - 1])
            return f'![Image {counter[0]}]({BASENAME}-embedded/{fname})'
        return m.group(0)

    content = re.sub(r'\[\]\{\.image\}', replace_placeholder, content)
    with open(MD_PATH, 'w') as f:
        f.write(content)
    print(f'Fixed {counter[0]} image placeholders in markdown')
```

#### Detecting and Extracting OLE Objects (Visio, etc.)

Run the following Python script to detect and extract Visio diagrams. Replace `INPUT_PATH` and `OUTPUT_DIR`:

```python
import zipfile, io, os, subprocess

INPUT_PATH = "<path>.odt"
OUTPUT_DIR = os.path.dirname(INPUT_PATH)
BASENAME = os.path.splitext(os.path.basename(INPUT_PATH))[0]
EMBED_DIR = os.path.join(OUTPUT_DIR, f'{BASENAME}-embedded')

with zipfile.ZipFile(INPUT_PATH, 'r') as z:
    all_names = z.namelist()
    
    # Find OLE embedded objects (named "Object 1", "Object 2", etc.)
    objects = sorted([n for n in all_names if n.startswith('Object ') and '/' not in n])
    
    if not objects:
        print('No embedded objects found.')
    else:
        os.makedirs(EMBED_DIR, exist_ok=True)
    
    for obj_name in objects:
        obj_num = obj_name.split(' ')[-1]
        data = z.read(obj_name)
        
        # Check for OLE Compound File signature (d0cf11e0a1b11ae1)
        if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            print(f'{obj_name}: Not an OLE compound file, skipping')
            continue
        
        # Inspect OLE streams to identify file type
        try:
            import olefile
        except ImportError:
            print('olefile not installed. Run: pip install olefile')
            break
        
        ole = olefile.OleFileIO(io.BytesIO(data))
        
        # Check CompObj stream for type identification
        try:
            compobj = ole.openstream(['\x01CompObj']).read()
            is_visio = b'Visio' in compobj
        except:
            is_visio = False
        
        if is_visio and ole.exists('Package'):
            # Extract the .vsdx from the Package stream
            pkg = ole.openstream(['Package']).read()
            
            if pkg[:2] == b'PK':  # ZIP-based .vsdx format
                vsdx_path = os.path.join(EMBED_DIR, f'object-{obj_num}.vsdx')
                with open(vsdx_path, 'wb') as f:
                    f.write(pkg)
                print(f'Extracted Visio: {vsdx_path} ({len(pkg):,} bytes)')
                
                # Extract PNG preview from ObjectReplacements
                replacement_name = f'ObjectReplacements/{obj_name}'
                if replacement_name in all_names:
                    emf_data = z.read(replacement_name)
                    emf_path = f'/tmp/odt_obj_{obj_num}.emf'
                    png_path = os.path.join(EMBED_DIR, f'object-{obj_num}.png')
                    
                    with open(emf_path, 'wb') as f:
                        f.write(emf_data)
                    
                    result = subprocess.run(
                        ['libreoffice', '--headless', '--convert-to', 'png', '--outdir', '/tmp', emf_path],
                        capture_output=True, text=True, timeout=60
                    )
                    
                    tmp_png = emf_path.replace('.emf', '.png')
                    if os.path.exists(tmp_png):
                        os.rename(tmp_png, png_path)
                        print(f'Exported PNG:   {png_path} ({os.path.getsize(png_path):,} bytes)')
                        os.remove(emf_path)
                    else:
                        print(f'Warning: PNG conversion failed for {obj_name}')
            else:
                print(f'{obj_name}: Visio object but not .vsdx format (legacy .vsd), extracting raw')
                vsd_path = os.path.join(EMBED_DIR, f'object-{obj_num}.vsd')
                with open(vsd_path, 'wb') as f:
                    f.write(data)
                print(f'Extracted legacy Visio: {vsd_path}')
        else:
            print(f'{obj_name}: Non-Visio OLE object (CLSID: {ole.root.clsid}), skipping')
        
        ole.close()
```

#### What This Extracts

| Object Type | Output Files (in `<name>-embedded/`) |
|---|---|
| Visio .vsdx diagram | `object-<N>.vsdx` + `object-<N>.png` |
| Legacy Visio .vsd | `object-<N>.vsd` (no PNG — would need full Visio) |
| Other OLE objects | Skipped with a log message |

#### Fix Image References in Markdown

After extracting embedded objects, fix the broken `ObjectReplacements/` references that pandoc emits for OLE objects. Replace them with an inline PNG preview and a link to the Visio source file:

```python
import re

MD_PATH = "<path>.md"
BASENAME = ...  # e.g. "Director in Orleans - WatchTower"
EMBED_DIR = f"{BASENAME}-embedded"

with open(MD_PATH, 'r') as f:
    content = f.read()

def replace_ref(m):
    num = m.group(1)
    return (
        f'![Visio Diagram {num}]({EMBED_DIR}/object-{num}.png)\n\n'
        f'[📎 Visio source]({EMBED_DIR}/object-{num}.vsdx)'
    )

content = re.sub(
    r'!\[\]\(ObjectReplacements/Object (\d+)\)\{[^}]*\}',
    replace_ref, content
)

with open(MD_PATH, 'w') as f:
    f.write(content)
```

This rewrites each `![](ObjectReplacements/Object N){...}` into:

```markdown
![Visio Diagram N](<name>-embedded/object-N.png)

[📎 Visio source](<name>-embedded/object-N.vsdx)
```

### Step 4: Extract Threaded Comments

ODT files are ZIP archives. Comments live in `content.xml` as `<office:annotation>` elements. Each annotation has:
- `office:name` attribute — pairs with a matching `<office:annotation-end>` to define the anchor range
- `dc:creator` — comment author
- `dc:date` — timestamp
- `text:p` children — comment text

**Threading logic:** Comments sharing identical anchor text are part of the same thread. Within each thread, sort by date. The first comment is the opener (💬), subsequent ones are replies (↩️).

**Anchor text extraction:** The anchored text is the document content between the closing `</office:annotation>` tag and the corresponding `<office:annotation-end office:name="N"/>` tag. Strip XML tags and normalize whitespace to get plain text.

Run the following Python script, replacing `INPUT_PATH` and `OUTPUT_PATH`:

```python
import zipfile, re, xml.etree.ElementTree as ET
from collections import OrderedDict

INPUT_PATH = "<path>.odt"
OUTPUT_PATH = "<path>-comments.md"

with zipfile.ZipFile(INPUT_PATH, 'r') as z:
    content = z.read('content.xml').decode('utf-8')

NS_OFFICE = 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
NS_TEXT = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
NS_DC = 'http://purl.org/dc/elements/1.1/'
ns = {'office': NS_OFFICE, 'text': NS_TEXT, 'dc': NS_DC}

def extract_text_from_xml(xml_fragment):
    """Extract visible text from an XML fragment, handling ODT whitespace elements."""
    xml_fragment = re.sub(r'<office:annotation\b.*?</office:annotation>', '', xml_fragment, flags=re.DOTALL)
    xml_fragment = re.sub(r'<text:s[^/]*/>', ' ', xml_fragment)
    xml_fragment = re.sub(r'<text:s/>', ' ', xml_fragment)
    xml_fragment = re.sub(r'<text:tab[^/]*/>', '\t', xml_fragment)
    xml_fragment = re.sub(r'<text:line-break[^/]*/>', '\n', xml_fragment)
    text = re.sub(r'<[^>]+>', '', xml_fragment)
    return re.sub(r'\s+', ' ', text).strip()

# Locate annotation start/end positions in raw XML
starts = {m.group(1): m.end() for m in re.finditer(
    r'<office:annotation\s+office:name="(\d+)"[^>]*>.*?</office:annotation>', content, re.DOTALL)}
ends = {m.group(1): m.start() for m in re.finditer(
    r'<office:annotation-end\s+office:name="(\d+)"', content)}

# Parse annotations from XML tree
root = ET.fromstring(content)
annotations = root.findall(f'.//{{{NS_OFFICE}}}annotation')

comments = []
for ann in annotations:
    name = ann.get(f'{{{NS_OFFICE}}}name')
    author_el = ann.find('dc:creator', ns)
    date_el = ann.find('dc:date', ns)
    paragraphs = ann.findall(f'.//{{{NS_TEXT}}}p')
    text = '\n'.join(t.strip() for p in paragraphs
                     for t in [''.join(p.itertext())] if t.strip())

    s, e = starts.get(name), ends.get(name)
    anchor = extract_text_from_xml(content[s:e]) if s and e and e > s else ''

    comments.append({
        'name': name,
        'author': author_el.text if author_el is not None else '',
        'date': date_el.text if date_el is not None else '',
        'text': text,
        'anchor': anchor,
        'start': s or 0,
    })

# Group into threads by anchor text, preserving document order
threads = OrderedDict()
for c in comments:
    key = c['anchor'] or f"_no_anchor_{c['name']}"
    threads.setdefault(key, []).append(c)

for key in threads:
    threads[key].sort(key=lambda c: c['date'])

# Write threaded comments file
lines = [f'# Comments from {INPUT_PATH.split("/")[-1]}\n\n']
lines.append(f'**Total:** {len(comments)} comments in {len(threads)} threads\n\n---\n\n')

for thread_num, (anchor, thread_comments) in enumerate(threads.items(), 1):
    is_thread = len(thread_comments) > 1
    lines.append(f'## Thread {thread_num}')
    if is_thread:
        lines.append(f' ({len(thread_comments)} replies)')
    lines.append('\n\n')

    if anchor and not anchor.startswith('_no_anchor_'):
        lines.append(f'> **Anchor:** {anchor}\n\n')

    for i, c in enumerate(thread_comments):
        prefix = '💬' if i == 0 else '↩️'
        lines.append(f'{prefix} **{c["author"]}** — {c["date"]}\n\n')

        if is_thread and i > 0:
            for line in c['text'].split('\n'):
                lines.append(f'> {line}\n')
            lines.append('\n')
        else:
            lines.append(f'{c["text"]}\n\n')

    lines.append('---\n\n')

with open(OUTPUT_PATH, 'w') as f:
    f.writelines(lines)

print(f'Saved {len(comments)} comments in {len(threads)} threads to {OUTPUT_PATH}')
```

### Step 5: Report Results

After all files are created, report:
- Path to the body Markdown file and its size
- Path to the comments Markdown file, total comment count, and thread count
- Any extracted images (count and directory)
- Any extracted Visio diagrams (.vsdx paths and PNG preview paths)
- Any issues encountered (e.g., no comments found, pandoc warnings, olefile not installed)

## Output Format

### Body Markdown (`<name>.md`)
Standard pandoc Markdown output with `--wrap=none`.

### Comments Markdown (`<name>-comments.md`)

```markdown
# Comments from <filename>.odt

**Total:** N comments in M threads

---

## Thread 1 (K replies)

> **Anchor:** <highlighted text in document>

💬 **Author Name** — 2026-02-06T15:16:00

Opening comment text here.

↩️ **Reply Author** — 2026-02-06T15:46:00

> Reply text is blockquoted for visual distinction.

---
```

## Edge Cases

- **No comments:** Still generate the body `.md`. For comments file, write a note saying "No comments found."
- **Comments without anchor text:** Show `_(no anchor text)_` in place of the anchor quote.
- **Single-comment threads:** Display without reply count or reply formatting.
- **Nested annotations:** The `extract_text_from_xml` helper strips nested `<office:annotation>` elements from anchor text to avoid duplication.
- **No embedded objects:** Skip Step 3 silently — only report images/Visio if they exist.
- **olefile not installed:** Print a warning and skip Visio extraction. The body and comments conversion still works.
- **LibreOffice not available:** Extract the `.vsdx` file but skip PNG conversion. Print a warning.
- **Multiple embedded objects:** Each gets a sequential number (`object-1`, `object-2`, etc.) in the `<name>-embedded/` subdirectory, matching the ODT's internal naming.
- **Non-Visio OLE objects:** Log the CLSID and skip. Don't attempt extraction of unknown object types.
