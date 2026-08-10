"""HOJA: catalogo de modelos de faster-whisper. Tabla de HECHOS, no comportamiento.

CERO imports de otros modulos del proyecto (ARCHITECTURE.md Sec.2: "catalog.py ...
Datos puros, CERO imports. NO IMPORTAN A NADIE"). Es lo que permite que tanto
`transcribe.py` (politica de dispositivo/modelo) como `models.py` (descarga,
borrado, E/S) lean la MISMA tabla sin que ninguno de los dos tenga que importar al
otro -- ese acoplamiento cruzado es justo el ciclo que este archivo existe para
evitar (ver el recuadro "Donde vive esto" en ARCHITECTURE.md Sec.3).

`ModelSpec` y `CATALOG` vivian en `models.py` desde el lote 2. Se extraen aqui en
el lote 8, sin cambiar un solo valor: repos, bytes y cifras medidas son los mismos,
solo cambia donde viven. Cifras: ADR-0002 Sec.3 y Sec.6 (catalogo y velocidad),
ARCHITECTURE.md Sec.3 (nota sobre `large-v3-turbo`). `tiny`, los `.en` y las
variantes `distil` quedan fuera por decision de ADR-0001 D5 (solo ingles).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    model_id: str            # "small"
    repo_id: str              # "Systran/faster-whisper-small"
    expected_bytes: int       # tamano de descarga anunciado como PLAN B si el Hub
                               # no responde (ver `models._resolve_download_plan`);
                               # el numero real y medido en el momento manda siempre
                               # que el Hub esta disponible
    params_millions: int
    quality_rank: int                  # 1 = mejor. ORDINAL y [E] (ADR-0002 Sec.3):
                                        # nunca se ha medido calidad en espanol
    vram_peak_mb: dict[str, int]       # por compute_type, medido donde exista
                                        # (ADR-0002 Sec.3 y Sec.7). Vacio = sin medir.
                                        # `resolve_device()` (transcribe.py) NUNCA
                                        # asume que cabe sin medicion: descarta el
                                        # candidato (ADR-0002 Sec.7)
    speed_ratio: dict[str, float]      # clave "{device}_{compute_type}", medido
                                        # donde exista (ADR-0002 Sec.3). Alimenta
                                        # tanto la ETA (jobs.py) como el filtro de
                                        # viabilidad de `recommend_profile()`
                                        # (transcribe.py, ADR-0002 E2)


# `expected_bytes`: se sigue la misma convencion que ya fijo `small` (464 MB
# medidos = 486 539 264 bytes exactos, es decir MiB, no MB decimales) para que las
# cifras encajen con lo que ya publica ARCHITECTURE.md.
CATALOG: dict[str, ModelSpec] = {
    "base": ModelSpec(
        model_id="base",
        repo_id="Systran/faster-whisper-base",
        expected_bytes=145 * 1024 * 1024,  # ~145 MB [E], ADR-0001 Sec.6
        params_millions=74,
        quality_rank=5,
        vram_peak_mb={},       # sin medir (ADR-0002 Sec.3: "-")
        speed_ratio={},        # sin medir en ADR-0002; ADR-0001 estimaba ~8-12x [E]
    ),
    "small": ModelSpec(
        model_id="small",
        repo_id="Systran/faster-whisper-small",
        expected_bytes=486_539_264,  # 464 MB [M], ARCHITECTURE.md Sec.3
        params_millions=244,
        quality_rank=4,
        vram_peak_mb={"int8": 1314, "float32": 2032},  # tope de los rangos medidos
        speed_ratio={"cpu_int8": 1.15, "cuda_int8": 7.94},  # ADR-0002 Sec.3 [M-dev]
        # OJO: ADR-0002 Sec.8.6 desautorizo el 1.15 de CPU (contaminado por
        # contencion) y dejo 1.534x(en)/1.725x(es) como la medicion limpia. No se
        # actualiza aqui -- fuera del alcance del lote 8, que solo mueve la tabla
        # de sitio -- pero cualquiera que toque este numero debe leer esa seccion.
    ),
    "medium": ModelSpec(
        model_id="medium",
        repo_id="Systran/faster-whisper-medium",
        expected_bytes=1_610_612_736,  # 1,5 GB [M-dev], ADR-0002 Sec.3
        params_millions=769,
        quality_rank=3,
        # float32: "no concluyente" en ADR-0002 Sec.3, pero es EXACTAMENTE el caso
        # de degradacion silenciosa medido en ADR-0002/ARCHITECTURE.md Sec.3
        # (3881-3927 MiB de 4096, 13 min sin terminar ni lanzar excepcion). Se usa
        # el tope del rango a proposito: la holgura ABSOLUTA de 512 MiB de
        # `resolve_device()` lo excluye sola, sin necesidad de omitir la clave.
        vram_peak_mb={"int8": 2416, "float32": 3927},
        speed_ratio={"cpu_int8": 0.30, "cuda_int8": 3.73},
    ),
    "large-v3-turbo": ModelSpec(
        model_id="large-v3-turbo",
        # OJO (ADR-0002 E12 / ARCHITECTURE.md Sec.3): NO tiene repo de Systran.
        # El de referencia de facto es este, tambien en fp16 (nunca pre-cuantizado).
        repo_id="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        expected_bytes=1_717_986_918,  # 1,6 GB [M-dev], ADR-0002 Sec.3
        params_millions=809,
        quality_rank=2,  # [E]
        vram_peak_mb={"int8": 1575},
        speed_ratio={"cpu_int8": 0.34, "cuda_int8": 7.05},
    ),
    "large-v3": ModelSpec(
        model_id="large-v3",
        repo_id="Systran/faster-whisper-large-v3",
        expected_bytes=3_328_599_655,  # tope del rango "~2,9-3,1 GB" [M-dev/E]
        params_millions=1550,  # [E]: cifra publica conocida de Whisper large-v3
        quality_rank=1,  # [E]
        # int8: OOM medido en 4 GiB (Pascal, dev). No hay cifra de float16 (ADR-0002
        # Sec.4: se estima 5,4-6,1 GiB [E], pendiente de medir en la 3080, V7 abierta)
        vram_peak_mb={"int8": 3951},
        speed_ratio={"cpu_int8": 0.2},  # ADR-0002: "~0,15-0,3x [E]", sin medir preciso
    ),
}
