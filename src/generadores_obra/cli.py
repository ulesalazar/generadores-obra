"""Línea de comandos: ``generadores-obra revisar | excel | apu-mx``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .cargar import cargar
from .modelo import ErrorGenerador


def _cmd_revisar(args: argparse.Namespace) -> int:
    est = cargar(args.archivo)
    print(f"{est.obra}  ·  estimación {est.numero}")
    print(
        f"{'Clave':<12}{'Unidad':>7}{'Contratado':>13}{'Anterior':>12}{'Esta':>12}{'Acumulado':>12}{'Avance':>9}"
    )
    for linea in est.lineas():
        c = linea.concepto
        print(
            f"{c.clave:<12}{c.unidad:>7}{c.cantidad:>13,.3f}{linea.anterior:>12,.3f}"
            f"{linea.esta:>12,.3f}{linea.acumulado:>12,.3f}{linea.avance:>9.1%}"
        )
    car = est.caratula()
    print()
    renglones = [
        ("Importe de la estimación", car.importe),
        ("Amortización del anticipo", -car.amortizacion_anticipo + 0.0),
        ("IVA", car.iva),
        *((f"Retención {n.replace('_', ' ')}", -v + 0.0) for n, v in car.retenciones.items()),
        ("Líquido a pagar", car.liquido),
    ]
    ancho = max(len(t) for t, _ in renglones) + 2
    for texto, valor in renglones:
        print(f"{texto:<{ancho}}{valor:>16,.2f}")
    avisos = est.advertencias()
    if avisos:
        print(f"\n{len(avisos)} advertencia(s):", file=sys.stderr)
        for a in avisos:
            print(f"  - {a}", file=sys.stderr)
    return 1 if (avisos and args.estricto) else 0


def _cmd_excel(args: argparse.Namespace) -> int:
    from .excel import exportar_excel

    salida = exportar_excel(cargar(args.archivo), args.salida)
    print(f"Libro guardado en {salida}")
    return 0


def _cmd_apu(args: argparse.Namespace) -> int:
    """Escribe la sección ``presupuesto:`` para un proyecto de apu-mx."""
    est = cargar(args.archivo)
    lineas = ["presupuesto:"]
    for clave, gen in est.generadores.items():
        # Cantidad neta: apu-mx aplica el desperdicio en cada matriz.
        lineas.append(f"  - {{clave: {clave}, cantidad: {round(gen.subtotal, 4)}}}")
    texto = "\n".join(lineas) + "\n"
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
        print(f"Cantidades guardadas en {args.salida}")
    else:
        print(texto, end="")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generadores-obra", description="Números generadores y estimaciones de obra"
    )
    p.add_argument("--version", action="version", version=f"generadores-obra {__version__}")
    sub = p.add_subparsers(dest="comando", required=True)

    r = sub.add_parser("revisar", help="Resumen de la estimación y advertencias")
    r.add_argument("archivo", help="YAML de la estimación o JSON de takeoff-mx")
    r.add_argument("--estricto", action="store_true", help="termina con error si hay advertencias")
    r.set_defaults(func=_cmd_revisar)

    e = sub.add_parser("excel", help="Libro de Excel con carátula, resumen y generadores")
    e.add_argument("archivo")
    e.add_argument("salida")
    e.set_defaults(func=_cmd_excel)

    a = sub.add_parser("apu-mx", help="Cantidades en formato de presupuesto de apu-mx")
    a.add_argument("archivo")
    a.add_argument("salida", nargs="?")
    a.set_defaults(func=_cmd_apu)
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ErrorGenerador, ValueError, KeyError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
