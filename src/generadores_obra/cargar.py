"""Lectura de estimaciones (YAML/JSON), generadores en CSV y salidas de takeoff-mx."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .modelo import ConceptoCatalogo, ErrorGenerador, Estimacion, Generador, Renglon

CAMPOS_RENGLON = {
    "cant",
    "largo",
    "ancho",
    "alto",
    "eje",
    "tramo",
    "nivel",
    "croquis",
    "nota",
    "referencia",
    "origen",
}


def _numero(valor: Any, campo: str, contexto: str) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError) as exc:
        raise ErrorGenerador(f"{contexto}: '{campo}' no es un número ({valor!r})") from exc


def renglon_desde_dict(d: dict[str, Any], contexto: str = "") -> Renglon:
    extra = set(d) - CAMPOS_RENGLON
    if extra:
        raise ErrorGenerador(f"{contexto}: campos no reconocidos {sorted(extra)}")
    cant = _numero(d.get("cant", 1), "cant", contexto)
    return Renglon(
        cant=1.0 if cant is None else cant,
        largo=_numero(d.get("largo"), "largo", contexto),
        ancho=_numero(d.get("ancho"), "ancho", contexto),
        alto=_numero(d.get("alto"), "alto", contexto),
        **{
            k: str(d.get(k) or "")
            for k in ("eje", "tramo", "nivel", "croquis", "nota", "referencia", "origen")
        },
    )


def estimacion_desde_dict(datos: dict[str, Any]) -> Estimacion:
    periodo = datos.get("periodo", {}) or {}
    est = Estimacion(
        obra=datos.get("obra", ""),
        contrato=datos.get("contrato", ""),
        contratista=datos.get("contratista", ""),
        dependencia=datos.get("dependencia", ""),
        numero=datos.get("estimacion", 1),
        periodo_del=str(periodo.get("del", "")),
        periodo_al=str(periodo.get("al", "")),
        iva=datos.get("iva", 0.16),
        anticipo=datos.get("anticipo", 0.0),
        retenciones=dict(datos.get("retenciones", {}) or {}),
        firmas=dict(datos.get("firmas", {}) or {}),
    )
    for c in datos.get("catalogo", []):
        clave = c["clave"]
        if clave in est.catalogo:
            raise ErrorGenerador(f"Clave duplicada en el catálogo: {clave}")
        est.catalogo[clave] = ConceptoCatalogo(
            clave=clave,
            descripcion=c.get("descripcion", ""),
            unidad=c.get("unidad", ""),
            cantidad=float(c.get("cantidad", 0)),
            precio_unitario=float(c.get("pu", c.get("precio_unitario", 0))),
            partida=c.get("partida", ""),
        )
    est.anteriores = {k: float(v) for k, v in (datos.get("anteriores", {}) or {}).items()}
    for g in datos.get("generadores", []):
        clave = g["clave"]
        gen = est.generadores.setdefault(clave, Generador(clave))
        for i, r in enumerate(g.get("renglones", []), start=1):
            gen.renglones.append(renglon_desde_dict(r, f"{clave} renglón {i}"))
    return est


def leer_csv_generadores(ruta: str | Path, est: Estimacion) -> None:
    """Agrega renglones desde un CSV con columnas ``clave`` y las de un renglón."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for n, fila in enumerate(csv.DictReader(f), start=2):
            fila = {k.strip().lower(): (v or "").strip() for k, v in fila.items() if k}
            clave = fila.pop("clave", "")
            if not clave:
                raise ErrorGenerador(f"{ruta} línea {n}: falta la clave del concepto")
            fila = {k: v for k, v in fila.items() if v != ""}
            gen = est.generadores.setdefault(clave, Generador(clave))
            gen.renglones.append(renglon_desde_dict(fila, f"{ruta} línea {n}"))


def desde_takeoff_mx(datos: dict[str, Any], precios: dict[str, float] | None = None) -> Estimacion:
    """Convierte la salida ``takeoff-mx.generadores.v1`` en una estimación de cuantificación.

    Cada concepto entra al catálogo con su cantidad neta (sin desperdicio) y los
    renglones medidos en el plano como generador. El desperdicio de takeoff-mx se
    conserva solo como dato informativo: en un presupuesto el desperdicio va en la
    matriz del precio unitario, no en la cantidad. ``precios`` permite asignar el
    precio unitario por clave.
    """
    if datos.get("schema") != "takeoff-mx.generadores.v1":
        raise ErrorGenerador("El archivo no es una salida takeoff-mx.generadores.v1")
    precios = precios or {}
    est = Estimacion(obra=datos.get("proyecto", ""), periodo_al=str(datos.get("fecha", "")), iva=0.16)
    for c in datos.get("conceptos", []):
        clave = c["clave"]
        est.catalogo[clave] = ConceptoCatalogo(
            clave=clave,
            descripcion=c.get("descripcion", ""),
            unidad=c.get("unidad", ""),
            cantidad=0.0,  # se fija abajo con la suma neta de los renglones
            precio_unitario=float(precios.get(clave, 0)),
            partida=c.get("partida", ""),
        )
        gen = Generador(
            clave, desperdicio=float(c.get("desperdicio_pct", 0)) / 100, validar_dimensiones=False
        )
        for r in c.get("renglones", []):
            origen = r.get("origen", "")
            if r.get("revisado") is False:
                origen = f"{origen} (sin revisar)".strip()
            # takeoff-mx mide el área o la longitud directa en Dim1 y usa 1 en las
            # dimensiones que no aplican; se conservan tal cual.
            dims = [r.get("dim1"), r.get("dim2"), r.get("dim3")]
            gen.renglones.append(
                Renglon(
                    cant=float(r.get("cant", 1)),
                    largo=dims[0],
                    ancho=dims[1],
                    alto=dims[2],
                    nota=r.get("descripcion", ""),
                    referencia=r.get("referencia", ""),
                    croquis=r.get("id_medicion", ""),
                    origen=origen,
                )
            )
        est.generadores[clave] = gen
        est.catalogo[clave].cantidad = gen.subtotal
    return est


def cargar(ruta: str | Path) -> Estimacion:
    ruta = Path(ruta)
    texto = ruta.read_text(encoding="utf-8")
    if ruta.suffix.lower() == ".json":
        datos = json.loads(texto)
        if datos.get("schema") == "takeoff-mx.generadores.v1":
            return desde_takeoff_mx(datos)
        return estimacion_desde_dict(datos)
    import yaml

    datos = yaml.safe_load(texto) or {}
    est = estimacion_desde_dict(datos)
    for csv_rel in datos.get("generadores_csv", []) or []:
        leer_csv_generadores(ruta.parent / csv_rel, est)
    return est
