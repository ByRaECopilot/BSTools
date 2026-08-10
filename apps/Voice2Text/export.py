"""MOTOR: composicion de `.txt` y `.md` a partir de segmentos ya transcritos.

Puro (ADR-0001 D11): sin estado global, sin leer configuracion, sin `print`. Los
nombres de datos van en ingles `snake_case`; el UNICO texto en castellano que este
archivo produce es el que compone dentro del propio `.md`, porque el `.md` es
salida para el usuario (ADR-0001 D12) -- distinto de la consola, que no lleva
acentos. Reglas de agrupacion y formato: ARCHITECTURE.md Sec.7.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcribe import Segment

_INVALID_CHARS = '<>:"/\\|?*'
_MAX_BASE_NAME_LENGTH = 120
_DEFAULT_BASE_NAME = "transcripcion"

_PARAGRAPH_GAP_SECONDS = 2.0
_PARAGRAPH_SOFT_LIMIT_CHARS = 400
_PARAGRAPH_HARD_LIMIT_CHARS = 700
_SENTENCE_ENDINGS = (".", "?", "!", "…")

_HOUR_SECONDS = 3600

_DEVICE_LABELS = {"cpu": "CPU", "cuda": "GPU"}


@dataclass(frozen=True)
class WrittenFile:
    format: str      # "txt" | "md"
    path: Path
    bytes: int


def _group_paragraphs(
    segments: list[Segment],
    paragraph_gap_seconds: float = _PARAGRAPH_GAP_SECONDS,
) -> list[list[Segment]]:
    """Aplica las tres reglas de corte de parrafo de ARCHITECTURE.md Sec.7.

    Regla 1 (hueco de pausa) se calcula SIEMPRE con `speech_end`, nunca con `end`
    -- `end` esta estirado por faster-whisper hasta el `start` del segmento
    siguiente y el hueco medido ahi es SIEMPRE 0 (verificado en el lote 1.b, V2,
    incluso con vad_filter=True). Si `speech_end` es `None` (word_timestamps
    desactivado) la regla 1 se DESACTIVA ENTERA para ese hueco: no se finge una
    pausa que no se puede medir. Las reglas 2 y 3 no dependen de `speech_end` y
    siguen activas siempre.
    """
    paragraphs: list[list[Segment]] = []
    current: list[Segment] = []
    current_len = 0
    previous_speech_end: float | None = None

    for segment in segments:
        gap = (
            (segment.start - previous_speech_end)
            if previous_speech_end is not None
            else None
        )
        ends_sentence = bool(current) and current[-1].text.rstrip().endswith(_SENTENCE_ENDINGS)

        starts_new = False
        if current and gap is not None and gap > paragraph_gap_seconds:
            starts_new = True
        elif current and current_len >= _PARAGRAPH_SOFT_LIMIT_CHARS and ends_sentence:
            starts_new = True
        elif current and current_len >= _PARAGRAPH_HARD_LIMIT_CHARS:
            starts_new = True

        if starts_new:
            paragraphs.append(current)
            current = []
            current_len = 0

        current.append(segment)
        current_len += len(segment.text) + 1
        previous_speech_end = segment.speech_end

    if current:
        paragraphs.append(current)

    return paragraphs


def _paragraph_text(group: list[Segment]) -> str:
    return " ".join(s.text for s in group if s.text).strip()


def to_plain_text(
    segments: list[Segment],
    paragraph_gap_seconds: float = _PARAGRAPH_GAP_SECONDS,
) -> str:
    paragraphs = _group_paragraphs(segments, paragraph_gap_seconds)
    blocks = [_paragraph_text(group) for group in paragraphs]
    return "\n\n".join(block for block in blocks if block)


def _format_timestamp(seconds: float, use_hours: bool) -> str:
    total = max(0, int(round(seconds)))
    hh, remainder = divmod(total, 3600)
    mm, ss = divmod(remainder, 60)
    if use_hours:
        return "%d:%02d:%02d" % (hh, mm, ss)
    return "%02d:%02d" % (mm, ss)


def to_markdown(
    segments: list[Segment],
    meta: dict[str, Any],
    paragraph_gap_seconds: float = _PARAGRAPH_GAP_SECONDS,
) -> str:
    paragraphs = _group_paragraphs(segments, paragraph_gap_seconds)
    duration = meta.get("media_duration_seconds") or 0.0
    use_hours = duration >= _HOUR_SECONDS

    lines: list[str] = [f"# {meta.get('title') or _DEFAULT_BASE_NAME}", ""]

    if meta.get("source"):
        lines.append(f"- **Origen:** {meta['source']}")
    if duration:
        lines.append(f"- **Duración:** {_format_timestamp(duration, use_hours)}")
    if meta.get("language"):
        probability = meta.get("language_probability")
        probability_text = f" ({round(probability * 100)} %)" if probability is not None else ""
        lines.append(f"- **Idioma detectado:** {meta['language']}{probability_text}")
    if meta.get("model_id"):
        # "small (int8, CPU)" -- el dispositivo viaja siempre (ARCHITECTURE.md Sec.3:
        # device_used llega a la cabecera del .md). Sin eso, quien instale el paquete
        # de GPU no tiene forma de saber si le esta sirviendo de algo.
        compute_type = meta.get("compute_type")
        device_label = _DEVICE_LABELS.get(meta.get("device"), meta.get("device"))
        details = ", ".join(part for part in (compute_type, device_label) if part)
        model_text = f"{meta['model_id']} ({details})" if details else meta["model_id"]
        lines.append(f"- **Modelo:** {model_text}")
    if meta.get("transcribed_at"):
        lines.append(f"- **Transcrito:** {meta['transcribed_at']}")

    lines.append("")
    lines.append("---")
    lines.append("")

    for group in paragraphs:
        text = _paragraph_text(group)
        if not text:
            continue
        timestamp = _format_timestamp(group[0].start, use_hours)
        lines.append(f"[{timestamp}] {text}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _sanitize_base_name(name: str) -> str:
    cleaned = "".join(ch for ch in (name or "") if ch not in _INVALID_CHARS and ord(ch) >= 32)
    cleaned = cleaned.strip(" .")
    if len(cleaned) > _MAX_BASE_NAME_LENGTH:
        cleaned = cleaned[:_MAX_BASE_NAME_LENGTH].strip(" .")
    return cleaned or _DEFAULT_BASE_NAME


def _unique_path(directory: Path, base_name: str, extension: str) -> Path:
    """Nunca se sobrescribe en silencio: si `nombre.ext` existe, prueba `nombre (2).ext`..."""
    candidate = directory / f"{base_name}.{extension}"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = directory / f"{base_name} ({counter}).{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


_FORMAT_NEWLINES = {
    "txt": "\r\n",   # para que el Bloc de notas lo abra bien
    "md": "\n",
}


def write_outputs(
    segments: list[Segment],
    meta: dict[str, Any],
    output_dir: Path,
    base_name: str,
    formats: list[str],
    overwrite: bool = False,
    paragraph_gap_seconds: float = _PARAGRAPH_GAP_SECONDS,
) -> list[WrittenFile]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_base_name = _sanitize_base_name(base_name)

    written: list[WrittenFile] = []
    for fmt in formats:
        if fmt == "txt":
            content = to_plain_text(segments, paragraph_gap_seconds)
        elif fmt == "md":
            content = to_markdown(segments, meta, paragraph_gap_seconds)
        else:
            raise ValueError(f"unsupported format: {fmt}")

        newline = _FORMAT_NEWLINES[fmt]
        # UTF-8 sin BOM, saltos de linea segun el formato (ARCHITECTURE.md Sec.7).
        normalized = content.replace("\r\n", "\n").replace("\n", newline)
        data = normalized.encode("utf-8")

        path = (
            output_dir / f"{safe_base_name}.{fmt}"
            if overwrite
            else _unique_path(output_dir, safe_base_name, fmt)
        )
        path.write_bytes(data)
        written.append(WrittenFile(format=fmt, path=path, bytes=len(data)))

    return written
