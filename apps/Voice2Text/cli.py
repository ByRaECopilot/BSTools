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
    py -3 cli.py --self-check                    (lote 7 / ADR-0002 Sec.6 y 14)

`--self-check` no transcribe nada del usuario: imprime las `DeviceCapabilities`
reales, la `DeviceChoice` que resuelve `resolve_device()` y ejecuta la prueba de
humo real de GPU (fusionada con la primera carga en `load_model`, ADR-0002 E8).
Es el comando que ejecuta `install-gpu.ps1` al terminar de instalar, y el que hay
que correr tal cual en la RTX 3080 quien migre (ARCHITECTURE.md Sec.14).
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from datetime import datetime
from pathlib import Path

from catalog import CATALOG
from errors import CoreError
import export
import transcribe

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = TOOL_DIR / "models"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe un archivo local con faster-whisper (lote 1, sin cascara).",
    )
    parser.add_argument(
        "media_path", type=Path, nargs="?", default=None,
        help="ruta al archivo de audio o video. Omitir junto con --self-check",
    )
    parser.add_argument(
        "--self-check", action="store_true",
        help="no transcribe nada: prueba de humo de GPU (ADR-0002 Sec.6/14). Ver cabecera del archivo",
    )
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
    parser.add_argument(
        "--no-word-timestamps", action="store_true",
        help="desactiva word_timestamps (Segment.speech_end queda en None; se desactiva la regla de corte por pausa)",
    )
    parser.add_argument(
        "--paragraph-gap-seconds", type=float, default=None,
        help="hueco de pausa (segundos) que abre parrafo nuevo; por defecto, el de export.py (2.0)",
    )
    parser.add_argument("--no-download", action="store_true", help="no descargar el modelo si falta")
    return parser.parse_args(argv)


def _print(message: str) -> None:
    print(message)


def _print_error(err: CoreError) -> None:
    _print(f"ERROR [{err.code.value}] detalles={err.details} tecnico={err.technical}")


# Motivo estable (transcribe.DeviceCapabilities.unavailable_reason /
# smoke_test_cuda) -> accion sugerida en una linea (mismo vocabulario que
# install-gpu.ps1 imprime al terminar la instalacion, ver su bloque final).
_FALLBACK_REASON_ACTIONS = {
    "no_nvidia_gpu": "no se detecta ninguna GPU NVIDIA visible para CUDA.",
    "cuda_libs_missing": "el complemento de GPU no esta instalado. Corre install-gpu.ps1.",
    "cuda_libs_not_on_path": "la instalacion del complemento de GPU quedo a medias. Vuelve a correr install-gpu.ps1.",
    "cuda_libs_mismatch": "las librerias CUDA no cargan (version incompatible). Revisa requirements-gpu.txt y reinstala.",
    "compute_capability_too_low": "esta GPU no soporta ningun compute_type utilizable.",
    "insufficient_vram": "no queda VRAM suficiente para este modelo con la holgura exigida. Prueba un modelo mas chico.",
    "gpu_libraries_missing": "falta una DLL o la instalacion quedo a medias. Vuelve a correr install-gpu.ps1.",
    "gpu_out_of_memory": "no hay VRAM suficiente para este modelo en esta GPU. Prueba un modelo mas chico.",
    "gpu_unavailable": "la GPU no paso la prueba de humo real. Revisa que el driver NVIDIA este instalado y actualizado.",
}


def _report_device_fallback(preference: str, choice: "transcribe.DeviceChoice") -> None:
    """Avisa de una caida de GPU a CPU -- NUNCA muda (ADR-0002, regla dura).

    `preference == "cuda"` es un pedido EXPLICITO del usuario: se avisa en un
    bloque prominente con el motivo y la accion sugerida, porque instalar ~2 GB
    de CUDA y terminar en CPU sin enterarse es exactamente lo que ADR-0002
    prohibe. `preference == "auto"` no pidio nada en concreto: basta una linea.
    """
    if not choice.fell_back_from:
        return

    action = _FALLBACK_REASON_ACTIONS.get(choice.fallback_reason, "revisa el motivo de arriba.")

    if preference == "cuda":
        _print("")
        _print("=" * 70)
        _print("AVISO: se pidio GPU (--device-preference cuda) y NO se esta usando.")
        _print(f"  Motivo: {choice.fallback_reason}")
        _print(f"  {action}")
        _print(f"  Se transcribe en {choice.device} (compute_type={choice.compute_type}).")
        _print("=" * 70)
        _print("")
    else:
        _print(
            f"Aviso: se prefiere '{choice.fell_back_from}' pero no esta disponible "
            f"({choice.fallback_reason}); se usa {choice.device}."
        )


def _self_check(args: argparse.Namespace) -> int:
    """Prueba de humo de GPU, sin transcribir nada del usuario (ADR-0002 Sec.6/14).

    Codigo de salida: 0 = GPU confirmada funcionando. 1 = GPU no confirmada (se
    quedo en CPU) o fallo al cargar el modelo. NUNCA levanta una excepcion sin
    capturar: es lo que llama `install-gpu.ps1` para decidir que mensaje mostrar.
    """
    _print("Voice2Text - autochequeo de GPU (ADR-0002 Sec.6 / ARCHITECTURE.md Sec.14)")
    _print("")

    spec = CATALOG.get(args.model_id)
    if spec is None:
        _print(f"ERROR: model-id desconocido: {args.model_id!r}")
        return 2

    caps = transcribe.probe_devices()
    _print(f"  cuda_status: {caps.cuda_status}")
    _print(f"  gpu: {caps.gpu_name or '(ninguna detectada)'}")
    if caps.compute_capability:
        _print(f"  compute capability: {caps.compute_capability[0]}.{caps.compute_capability[1]}")
    if caps.vram_total_mb is not None and caps.vram_free_mb is not None:
        _print(f"  VRAM libre: {caps.vram_free_mb} MiB de {caps.vram_total_mb} MiB")
    _print(f"  compute types soportados: {caps.supported_compute_types}")
    if caps.unavailable_reason:
        _print(f"  motivo: {caps.unavailable_reason}")
    _print("")

    if caps.cuda_status == "unavailable":
        _print(f"RESULTADO: sin GPU utilizable ({caps.unavailable_reason}). Se sigue usando CPU.")
        return 1

    device_choice = transcribe.resolve_device(spec, caps, preference="cuda")
    _print(f"  resolve_device(model_id={args.model_id!r}): device={device_choice.device} compute_type={device_choice.compute_type}")
    if device_choice.device != "cuda":
        _print("")
        _print(
            f"RESULTADO: hay GPU visible pero no cabe el modelo '{args.model_id}' con la "
            f"holgura de VRAM exigida (motivo: {device_choice.fallback_reason}). Se usa CPU."
        )
        return 1

    _print(f"  cargando '{args.model_id}' y ejecutando la prueba de humo real (no solo construir)...")
    try:
        model = transcribe.load_model(
            args.model_id, args.models_dir, device_choice, allow_download=not args.no_download,
        )
    except CoreError as err:
        _print_error(err)
        _print("")
        _print("RESULTADO: fallo al cargar el modelo. No se pudo probar la GPU.")
        return 1

    used = getattr(model, transcribe._ATTR_DEVICE_CHOICE, None)
    _print("")
    if used is not None and used.device == "cuda":
        _print(f"RESULTADO: GPU CONFIRMADA ({caps.gpu_name}, compute_type={used.compute_type}).")
        return 0

    reason = used.fallback_reason if used is not None else "desconocido"
    _print(f"RESULTADO: GPU NO confirmada tras la prueba de humo real (motivo: {reason}). Se uso CPU.")
    return 1


def main(argv: list[str] | None = None) -> int:
    # UTF-8 explicito: el texto transcrito puede llevar acentos aunque nuestra
    # prosa fija de consola no los use.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.self_check:
        return _self_check(args)

    if args.media_path is None:
        _print("ERROR: falta la ruta del archivo (o usa --self-check).")
        return 2

    spec = CATALOG.get(args.model_id)
    if spec is None:
        _print(f"ERROR: model-id desconocido: {args.model_id!r}")
        return 2

    media_path = args.media_path.resolve()
    output_dir = (args.output_dir or media_path.parent).resolve()
    formats = [item.strip() for item in args.formats.split(",") if item.strip()]

    # Resolucion de dispositivo (ARCHITECTURE.md Sec.3): la cascara solo pide una
    # preferencia; la politica vive entera en transcribe.resolve_device().
    caps = transcribe.probe_devices()
    device_choice = transcribe.resolve_device(spec, caps, preference=args.device_preference)
    if args.compute_type:
        device_choice = dataclasses.replace(device_choice, compute_type=args.compute_type)
    if args.cpu_threads is not None:
        device_choice = dataclasses.replace(device_choice, cpu_threads=args.cpu_threads)

    _report_device_fallback(args.device_preference, device_choice)

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
            word_timestamps=not args.no_word_timestamps,
            on_segment=on_segment,
            should_cancel=should_cancel,
        )
    except CoreError as err:
        _print_error(err)
        return 1

    # Segundo punto donde puede aparecer un fallback (ADR-0002 E8): si
    # `device_choice.device == "cuda"` no hubo aviso previo (se creia disponible),
    # pero `load_model()` pudo haber recaido en CPU tras la prueba de humo real
    # DENTRO de `transcribe.load_model()`. `result.device_used` es la verdad final;
    # `device_choice` (arriba) es solo la intencion antes de cargar. Sin este
    # chequeo, esa caida queda muda -- exactamente el sintoma que ADR-0002 prohibe.
    if device_choice.device == "cuda":
        _report_device_fallback(args.device_preference, result.device_used)

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

    write_kwargs = {}
    if args.paragraph_gap_seconds is not None:
        write_kwargs["paragraph_gap_seconds"] = args.paragraph_gap_seconds

    try:
        written = export.write_outputs(
            result.segments, meta, output_dir, media_path.stem, formats, **write_kwargs
        )
    except OSError as exc:
        _print(f"ERROR al escribir la salida: {exc}")
        return 1

    for written_file in written:
        _print(f"Escrito: {written_file.path} ({written_file.bytes} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
