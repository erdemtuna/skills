#!/usr/bin/env python3
"""Detect and extract OLE-embedded objects (Visio diagrams) from an ODT file."""

import argparse
import io
import os
import subprocess
import zipfile


def extract_ole_objects(odt_path: str, embed_dir: str) -> None:
    with zipfile.ZipFile(odt_path, "r") as z:
        all_names = z.namelist()

        objects = sorted(n for n in all_names if n.startswith("Object ") and "/" not in n)

        if not objects:
            print("No embedded objects found.")
            return

        os.makedirs(embed_dir, exist_ok=True)

        for obj_name in objects:
            obj_num = obj_name.split(" ")[-1]
            data = z.read(obj_name)

            # Check for OLE Compound File signature
            if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                print(f"{obj_name}: Not an OLE compound file, skipping")
                continue

            try:
                import olefile
            except ImportError:
                print("olefile not installed. Run: pip install olefile")
                break

            ole = olefile.OleFileIO(io.BytesIO(data))

            try:
                compobj = ole.openstream(["\x01CompObj"]).read()
                is_visio = b"Visio" in compobj
            except Exception:
                is_visio = False

            if is_visio and ole.exists("Package"):
                pkg = ole.openstream(["Package"]).read()

                if pkg[:2] == b"PK":  # ZIP-based .vsdx format
                    vsdx_path = os.path.join(embed_dir, f"object-{obj_num}.vsdx")
                    with open(vsdx_path, "wb") as f:
                        f.write(pkg)
                    print(f"Extracted Visio: {vsdx_path} ({len(pkg):,} bytes)")

                    _convert_emf_preview(z, all_names, obj_name, obj_num, embed_dir)
                else:
                    print(f"{obj_name}: Visio object but not .vsdx format (legacy .vsd), extracting raw")
                    vsd_path = os.path.join(embed_dir, f"object-{obj_num}.vsd")
                    with open(vsd_path, "wb") as f:
                        f.write(data)
                    print(f"Extracted legacy Visio: {vsd_path}")
            else:
                print(f"{obj_name}: Non-Visio OLE object (CLSID: {ole.root.clsid}), skipping")

            ole.close()


def _convert_emf_preview(
    z: zipfile.ZipFile,
    all_names: list,
    obj_name: str,
    obj_num: str,
    embed_dir: str,
) -> None:
    """Convert EMF preview rendering to PNG via LibreOffice."""
    replacement_name = f"ObjectReplacements/{obj_name}"
    if replacement_name not in all_names:
        return

    emf_data = z.read(replacement_name)
    emf_path = f"/tmp/odt_obj_{obj_num}.emf"
    png_path = os.path.join(embed_dir, f"object-{obj_num}.png")

    with open(emf_path, "wb") as f:
        f.write(emf_data)

    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "png", "--outdir", "/tmp", emf_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        print(f"Warning: libreoffice not found — skipping PNG conversion for {obj_name}")
        return

    tmp_png = emf_path.replace(".emf", ".png")
    if os.path.exists(tmp_png):
        os.rename(tmp_png, png_path)
        print(f"Exported PNG:   {png_path} ({os.path.getsize(png_path):,} bytes)")
        os.remove(emf_path)
    else:
        print(f"Warning: PNG conversion failed for {obj_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract OLE-embedded objects (Visio) from ODT")
    parser.add_argument("odt", help="Path to the .odt file")
    parser.add_argument("embed_dir", help="Path to the embedded media directory")
    args = parser.parse_args()

    extract_ole_objects(args.odt, args.embed_dir)
