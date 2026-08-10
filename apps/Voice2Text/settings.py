"""CASCARA: valores por defecto de configuracion + `settings.json` opcional.

Capa de cascara (ADR-0001 D13): el motor NUNCA lee este archivo ni el JSON que
carga. `app.py` (lote 3, todavia no existe) y `serve.py` (lote 6) son sus dos
consumidores; los valores se resuelven aqui UNA vez y se pasan por argumento a
`jobs.py`/`transcribe.py`/`models.py`/`fetch.py` -- ninguno de esos lee esto.

Claves documentadas en ARCHITECTURE.md Sec.9. `serve.py` (lote 6) solo consume
hoy las cuatro operativas del modo servidor (`serve_port`, `max_queued_jobs`,
`model_idle_timeout_seconds`, `work_retention_hours`); el resto queda listo
para cuando `app.py` (lote 3) las necesite, sin inventar nada que no este ya
en el contrato de ARCHITECTURE.md.

`default_model_id` se queda en `None` a proposito: ADR-0002 todavia no fija el
modelo por defecto (D5 esta en cuarentena) y este archivo no puede inventar una
politica que no esta decidida. Quien encole un trabajo debe indicar `model_id`
explicitamente -- `jobs.py` ya lo exige (`_normalize_options` levanta
`ValueError` si falta).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TOOL_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = TOOL_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    "default_model_id": None,  # sin fijar: ADR-0002 pendiente (D5 en cuarentena)
    "device_preference": "auto",
    "compute_type_override": None,
    "cpu_threads": 0,
    "language": None,
    "vad_filter": True,
    "word_timestamps": True,
    "paragraph_gap_seconds": 2.0,
    "min_viable_speed_ratio": 1.0,
    "language_confidence_warn_threshold": 0.75,
    "max_input_bytes": 2147483648,
    "output_formats": ["txt", "md"],
    "output_dir": None,
    "work_retention_hours": 24,
    "ytdlp_stale_days": 60,
    "youtube_player_clients": ["android", "ios", "tv", "web"],
    "serve_port": 8317,
    "max_queued_jobs": 8,
    "model_idle_timeout_seconds": 300,
}


def load(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    """Defaults + lo que haya en `settings.json`, si existe.

    Claves desconocidas en el JSON se ignoran con un aviso (mejor un
    settings.json con una clave vieja que un arranque roto); claves ausentes
    se rellenan con su valor por defecto. Un JSON invalido o illegible tambien
    degrada a los valores por defecto, nunca revienta el arranque.
    """
    resolved = dict(DEFAULTS)
    if not path.exists():
        return resolved

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("no se pudo leer %s, se usan los valores por defecto: %s", path, exc)
        return resolved

    if not isinstance(raw, dict):
        logger.warning("%s no es un objeto JSON; se ignora entero", path)
        return resolved

    for key, value in raw.items():
        if key in DEFAULTS:
            resolved[key] = value
        else:
            logger.warning("settings.json: clave desconocida ignorada: %s", key)

    return resolved
