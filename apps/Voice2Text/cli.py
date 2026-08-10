"""Arnes de desarrollo del lote 1 (ARCHITECTURE.md Sec.13).

Demuestra `transcribe.py` + `export.py` sin ventana ni servidor, mientras `app.py`
(lote 3) y `serve.py` (lote 6) no existen. NO forma parte del contrato de las tres
capas de Sec.2: no lo consume ningun otro modulo, se descarta o se reduce cuando
llegue la cascara real. No importa `webview` ni `http.server`.

Salida de consola SIN acentos ni caracteres no ASCII (regla de la casa,
CLAUDE.md / principles.md). El contenido transcrito, en cambio, es dato del
usuario: puede llevar acentos, y por eso la consola se reconfigura a UTF-8 para
no reventar con `UnicodeEncodeError` al imprimirlo.

Uso:
    py -3 cli.py "C:\\ruta\\audio.wav"
    py -3 cli.py "C:\\ruta\\video.mp4" --language es --model-id base
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from datetime import datetime
from pathlib import Path

from errors import CoreError
import export
import transcribe

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = TOOL_DIR / "models"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe un archivo local con faster-whisper (lote 1, sin cascara).",
    )
    parser.add_argument("media_path", type=Path, help="ruta al archivo de audio o video")
    parser.add_argument("--model-id", default="small", help="small (por defecto) o base")
    parser.add_argument("--language", default=None, help="es | en (vacio = deteccion automatica)")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--output-dir", type=Path, default=None, help="por defecto, la carpeta del archivo")
    parser.add_argument("--formats", default="txt,md")
    parser.add_argument(
        "--device-preference", choices=["auto", "cuda", "cpu"], default="auto",
        help="lo unico que la cascara puede pedir; la politica la fija resolve_device()",
    )
    parser.add_argument("--compute-type", default=None, help="fija a mano para depurar (por defecto, lo decide resolve_device())")
    parser.add_argument("--cpu-threads", type=int, default=None, help="fija a mano para depurar (por defecto, 0 = decide CTranslate2)")
    parser.add_argument("--no-vad", action="store_true", help="desactiva el filtro de silencios")
    parser.add_argument("--no-download", action="store_true", help="no descargar el modelo si falta")
    return parser.parse_args(argv)


def _print(message: str) -> None:
    print(message)


def _print_error(err: CoreError) -> None:
    _print(f"ERROR [{err.code.value}] detalles={err.details} tecnico={err.technical}")


def main(argv: list[str] | None = None) -> int:
    # UTF-8 explicito: el texto transcrito puede llevar acentos aunque nuestra
    # prosa fija de consola no los use.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = _parse_args(sys.argv[1:] if argv is None else argv)

    media_path = args.media_path.resolve()
    output_dir = (args.output_dir or media_path.parent).resolve()
    formats = [item.strip() for item in args.formats.split(",") if item.strip()]

    # Resolucion de dispositivo (ARCHITECTURE.md Sec.3): la cascara solo pide una
    # preferencia; la politica vive entera en transcribe.resolve_device().
    caps = transcribe.probe_devices()
    device_choice = transcribe.resolve_device(args.model_id, caps, preference=args.device_preference)
    if args.compute_type:
        device_choice = dataclasses.replace(device_choice, compute_type=args.compute_type)
    if args.cpu_threads is not None:
        device_choice = dataclasses.replace(device_choice, cpu_threads=args.cpu_threads)

    if device_choice.fell_back_from:
        _print(
            f"Aviso: se prefiere '{device_choice.fell_back_from}' pero no esta disponible "
            f"({device_choice.fallback_reason}); se usa {device_choice.device}."
        )

    _print(f"Cargando modelo '{args.model_id}' en {device_choice.device} (compute_type={device_choice.compute_type})...")
    load_start = time.monotonic()
    try:
        model = transcribe.load_model(
            args.model_id,
            args.models_dir,
            device_choice,
            allow_download=not args.no_download,
        )
    except CoreError as err:
        _print_error(err)
        return 1
    _print(f"Modelo listo en {time.monotonic() - load_start:.1f} s")

    last_reported_pct = -1

    def on_segment(segment: transcribe.Segment, progress: float) -> None:
        nonlocal last_reported_pct
        pct = int(progress * 100)
        if pct != last_reported_pct:
            last_reported_pct = pct
            _print(f"  [{pct:3d}%] {segment.start:7.1f}s  {segment.text}")

    def should_cancel() -> bool:
        return False

    _print(f"Transcribiendo: {media_path}")
    try:
        result = transcribe.transcribe(
            media_path,
            model,
            language=args.language,
            vad_filter=not args.no_vad,
            on_segment=on_segment,
            should_cancel=should_cancel,
        )
    except CoreError as err:
        _print_error(err)
        return 1

    _print(
        "Terminado: idioma=%s (%.0f%%) duracion=%.1fs elapsed=%.1fs speed_ratio=%.2fx "
        "segmentos=%d dispositivo=%s"
        % (
            result.language,
            result.language_probability * 100,
            result.media_duration_seconds,
            result.elapsed_seconds,
            result.speed_ratio,
            len(result.segments),
            result.device_used.device,
        )
    )

    meta = {
        "title": media_path.stem,
        "source": str(media_path),
        "media_duration_seconds": result.media_duration_seconds,
        "language": result.language,
        "language_probability": result.language_probability,
        "model_id": args.model_id,
        "compute_type": result.device_used.compute_type,
        "device": result.device_used.device,
        "transcribed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    try:
        written = export.write_outputs(result.segments, meta, output_dir, media_path.stem, formats)
    except OSError as exc:
        _print(f"ERROR al escribir la salida: {exc}")
        return 1

    for written_file in written:
        _print(f"Escrito: {written_file.path} ({written_file.bytes} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
