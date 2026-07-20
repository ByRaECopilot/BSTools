#!/usr/bin/env python3
"""
PDF2MD - Convierte PDF a Markdown optimizado para LLMs (Claude, GPT, etc.)

Parte de BSTools - https://www.byraesoftware.com
Licencia: CC0 1.0 Universal (dominio publico)

Uso:
    python pdf2md.py archivo.pdf                 -> archivo.md
    python pdf2md.py archivo.pdf salida.md
    python pdf2md.py carpeta\                    -> convierte todos los PDF
    python pdf2md.py archivo.pdf --images        -> extrae tambien las imagenes
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from collections import Counter
from pathlib import Path

MIN_PYTHON = (3, 9)
if sys.version_info < MIN_PYTHON:
    sys.exit(f"Se necesita Python {'.'.join(map(str, MIN_PYTHON))} o superior.")


# --------------------------------------------------------------------------- #
# Dependencias
# --------------------------------------------------------------------------- #
def _import_backend():
    """Importa pymupdf4llm, ofreciendo instalarlo si falta."""
    try:
        import pymupdf4llm  # noqa: F401
        import pymupdf  # noqa: F401
    except ImportError:
        print("Falta la dependencia 'pymupdf4llm'. Instalando...", file=sys.stderr)
        import subprocess

        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", "pymupdf4llm"]
            )
        except subprocess.CalledProcessError:
            sys.exit(
                "No se pudo instalar automaticamente.\n"
                "Ejecuta manualmente:  pip install pymupdf4llm"
            )
        import pymupdf4llm  # noqa: F401
        import pymupdf  # noqa: F401

    import pymupdf
    import pymupdf4llm

    return pymupdf, pymupdf4llm


# --------------------------------------------------------------------------- #
# Limpieza y post-proceso del Markdown
# --------------------------------------------------------------------------- #
LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "ﬅ": "st", "ﬆ": "st",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    " ": " ", "​": "", "﻿": "",
    "–": "-", "—": "--", "…": "...",
}


def _normalize_chars(text: str) -> str:
    for bad, good in LIGATURES.items():
        text = text.replace(bad, good)
    return text


def _detect_running_heads(pages: list[str]) -> set[str]:
    """Detecta encabezados/pies repetidos en la mayoria de las paginas."""
    if len(pages) < 4:
        return set()

    counter: Counter[str] = Counter()
    for page in pages:
        lines = [ln.strip() for ln in page.strip().splitlines() if ln.strip()]
        for line in lines[:2] + lines[-2:]:
            # Ignora lineas largas (parrafos) y titulos markdown reales
            if 3 <= len(line) <= 80 and not line.startswith(("#", "|", "-", "*", ">")):
                # Normaliza numeros de pagina: "Pagina 12" -> "Pagina #"
                counter[re.sub(r"\d+", "#", line)] += 1

    threshold = max(3, int(len(pages) * 0.5))
    return {key for key, count in counter.items() if count >= threshold}


def _strip_running_heads(page: str, heads: set[str]) -> str:
    if not heads:
        return page
    out = []
    for line in page.splitlines():
        if re.sub(r"\d+", "#", line.strip()) in heads:
            continue
        out.append(line)
    return "\n".join(out)


def _fix_hyphenation(text: str) -> str:
    """Une palabras partidas por guion al final de linea: 'exten-\\nsion' -> 'extension'."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def _tidy(text: str) -> str:
    text = _normalize_chars(text)
    text = _fix_hyphenation(text)
    # Espacios al final de linea
    text = re.sub(r"[ \t]+\n", "\n", text)
    # Maximo una linea en blanco seguida
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Encabezados vacios que deja el extractor
    text = re.sub(r"^#+\s*$", "", text, flags=re.MULTILINE)
    # "# **Titulo**" -> "# Titulo" (la negrita dentro de un heading es ruido)
    text = re.sub(r"^(#{1,6})\s*\*\*(.+?)\*\*\s*$", r"\1 \2", text, flags=re.MULTILINE)
    # Compacta listas: el extractor separa cada item con una linea en blanco
    list_item = r"(?:[-*]|\d+\.)\s"
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            rf"^({list_item}.*)\n\n(?={list_item})", r"\1\n", text, flags=re.MULTILINE
        )
    # Linea en blanco antes y despues de cada encabezado
    text = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", text)
    text = re.sub(r"^(#{1,6} .*)\n(?!\n)", r"\1\n\n", text, flags=re.MULTILINE)
    # Bullets sueltos vacios
    text = re.sub(r"^[-*]\s*$", "", text, flags=re.MULTILINE)
    return text.strip() + "\n"


def _yaml_escape(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _build_frontmatter(pdf_path: Path, meta: dict, n_pages: int, toc: list) -> str:
    """Cabecera YAML: le da a Claude el contexto del documento de un vistazo."""
    title = (meta.get("title") or "").strip() or pdf_path.stem
    lines = [
        "---",
        f"title: {_yaml_escape(title)}",
        f"source_file: {_yaml_escape(pdf_path.name)}",
        f"pages: {n_pages}",
    ]
    for key, label in (("author", "author"), ("subject", "subject"), ("keywords", "keywords")):
        value = (meta.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {_yaml_escape(value)}")
    lines.append(f"converted: {_dt.date.today().isoformat()}")
    lines.append("converter: pdf2md (BSTools)")
    lines.append("---")

    body = ["\n".join(lines), "", f"# {title}", ""]

    if toc:
        body.append("## Indice del documento")
        body.append("")
        for level, entry_title, page in toc[:60]:
            indent = "  " * max(0, level - 1)
            clean = _normalize_chars(str(entry_title)).strip()
            body.append(f"{indent}- {clean} _(p. {page})_")
        body.append("")

    return "\n".join(body)


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #
def convert(
    pdf_path: Path,
    out_path: Path | None = None,
    *,
    extract_images: bool = False,
    page_markers: bool = True,
    quiet: bool = False,
) -> Path:
    pymupdf, pymupdf4llm = _import_backend()

    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    out_path = out_path or pdf_path.with_suffix(".md")

    doc = pymupdf.open(pdf_path)
    if doc.needs_pass:
        doc.close()
        raise ValueError("El PDF esta protegido con contrasena.")

    meta = doc.metadata or {}
    n_pages = doc.page_count
    toc = doc.get_toc() or []

    image_dir = None
    if extract_images:
        image_dir = out_path.parent / f"{out_path.stem}_images"
        image_dir.mkdir(exist_ok=True)

    chunks = pymupdf4llm.to_markdown(
        doc,
        page_chunks=True,
        write_images=extract_images,
        image_path=str(image_dir) if image_dir else None,
        image_format="png",
        table_strategy="lines_strict",
        show_progress=not quiet,
    )
    doc.close()

    raw_pages = [chunk.get("text", "") for chunk in chunks]
    heads = _detect_running_heads(raw_pages)

    parts: list[str] = []
    empty_pages = 0
    for index, page_text in enumerate(raw_pages, start=1):
        cleaned = _tidy(_strip_running_heads(page_text, heads))
        if not cleaned.strip():
            empty_pages += 1
            continue
        if page_markers:
            parts.append(f"<!-- page: {index} -->")
        parts.append(cleaned)

    body = "\n\n".join(parts)

    if empty_pages == n_pages:
        raise ValueError(
            "No se extrajo texto: el PDF parece escaneado (solo imagenes). "
            "Necesita OCR."
        )

    header = _build_frontmatter(pdf_path, meta, n_pages, toc)
    out_path.write_text(f"{header}\n{body}", encoding="utf-8")

    if not quiet:
        size_kb = out_path.stat().st_size / 1024
        print(f"OK  {out_path.name}  ({n_pages} pag., {size_kb:.0f} KB)")
        if empty_pages:
            print(f"    Aviso: {empty_pages} pagina(s) sin texto (posibles escaneos).")
    return out_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convierte PDF a Markdown optimizado para LLMs (BSTools).",
    )
    parser.add_argument("input", type=Path, help="Archivo PDF o carpeta con PDFs")
    parser.add_argument("output", type=Path, nargs="?", help="Archivo .md de salida")
    parser.add_argument("--images", action="store_true", help="Extrae las imagenes a una subcarpeta")
    parser.add_argument("--no-page-markers", action="store_true", help="No inserta <!-- page: N -->")
    parser.add_argument("--quiet", "-q", action="store_true", help="Sin salida por consola")
    parser.add_argument("--pause", action="store_true", help="Espera una tecla al terminar")
    args = parser.parse_args(argv)

    targets: list[Path]
    if args.input.is_dir():
        targets = sorted(args.input.glob("*.pdf"))
        if not targets:
            print(f"No hay PDFs en {args.input}", file=sys.stderr)
            return 1
    else:
        targets = [args.input]

    errors = 0
    for pdf in targets:
        out = args.output if (args.output and len(targets) == 1) else None
        try:
            convert(
                pdf,
                out,
                extract_images=args.images,
                page_markers=not args.no_page_markers,
                quiet=args.quiet,
            )
        except Exception as exc:  # noqa: BLE001 - se reporta al usuario
            errors += 1
            print(f"ERROR  {pdf.name}: {exc}", file=sys.stderr)

    if args.pause:
        try:
            input("\nPulsa Intro para cerrar...")
        except EOFError:
            pass

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
