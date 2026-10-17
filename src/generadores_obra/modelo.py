"""Modelo de números generadores y de la estimación que los cobra.

Un renglón de generador ubica lo medido (eje, tramo, nivel, croquis) y lo
cuantifica como ``parcial = cant × largo × ancho × alto``. Las dimensiones que
no aplican valen 1; ``cant`` negativa representa una deducción (un vano, por
ejemplo).

La estimación compara lo generado en el periodo contra lo contratado y lo
estimado antes, y obtiene el importe, la amortización del anticipo, el IVA, las
retenciones y el líquido a pagar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Dimensiones esperadas por unidad. Sirven para advertir, no para impedir.
DIMENSIONES_POR_UNIDAD = {
    "m3": 3,
    "m2": 2,
    "m": 1,
    "ml": 1,
    "kg": 0,
    "ton": 0,
    "pza": 0,
    "sal": 0,
    "lote": 0,
    "jgo": 0,
    "lt": 0,
}


def normalizar_unidad(unidad: str) -> str:
    u = unidad.strip().lower().replace("²", "2").replace("³", "3").rstrip(".")
    return {"m.l": "ml", "pieza": "pza", "pzas": "pza", "salida": "sal", "kgs": "kg"}.get(u, u)


class ErrorGenerador(ValueError):
    """Error de captura en generadores o en la estimación."""


@dataclass
class Renglon:
    cant: float = 1.0
    largo: float | None = None
    ancho: float | None = None
    alto: float | None = None
    eje: str = ""
    tramo: str = ""
    nivel: str = ""
    croquis: str = ""
    nota: str = ""
    referencia: str = ""
    origen: str = ""

    @property
    def dimensiones(self) -> int:
        return sum(d is not None for d in (self.largo, self.ancho, self.alto))

    @property
    def parcial(self) -> float:
        valor = self.cant
        for d in (self.largo, self.ancho, self.alto):
            if d is not None:
                valor *= d
        return valor

    @property
    def ubicacion(self) -> str:
        partes = []
        if self.nivel:
            partes.append(f"Nivel {self.nivel}")
        if self.eje:
            partes.append(f"Eje {self.eje}")
        if self.tramo:
            partes.append(f"Tramo {self.tramo}")
        return ", ".join(partes)


@dataclass
class ConceptoCatalogo:
    clave: str
    descripcion: str
    unidad: str
    cantidad: float
    precio_unitario: float
    partida: str = ""


@dataclass
class Generador:
    clave: str
    renglones: list[Renglon] = field(default_factory=list)
    desperdicio: float = 0.0  # solo para generadores de cuantificación, no de estimación
    validar_dimensiones: bool = True

    @property
    def subtotal(self) -> float:
        return sum(r.parcial for r in self.renglones)

    @property
    def total(self) -> float:
        return self.subtotal * (1 + self.desperdicio)


@dataclass(frozen=True)
class LineaEstimacion:
    concepto: ConceptoCatalogo
    anterior: float
    esta: float

    @property
    def acumulado(self) -> float:
        return self.anterior + self.esta

    @property
    def por_ejecutar(self) -> float:
        return self.concepto.cantidad - self.acumulado

    @property
    def avance(self) -> float:
        return self.acumulado / self.concepto.cantidad if self.concepto.cantidad else 0.0

    @property
    def importe(self) -> float:
        return self.esta * self.concepto.precio_unitario

    @property
    def importe_acumulado(self) -> float:
        return self.acumulado * self.concepto.precio_unitario


@dataclass(frozen=True)
class Caratula:
    importe: float
    amortizacion_anticipo: float
    subtotal: float
    iva: float
    total: float
    retenciones: dict[str, float]
    liquido: float


@dataclass
class Estimacion:
    obra: str = ""
    contrato: str = ""
    contratista: str = ""
    dependencia: str = ""
    numero: int | str = 1
    periodo_del: str = ""
    periodo_al: str = ""
    iva: float = 0.16
    anticipo: float = 0.0
    retenciones: dict[str, float] = field(default_factory=dict)
    firmas: dict[str, str] = field(default_factory=dict)
    catalogo: dict[str, ConceptoCatalogo] = field(default_factory=dict)
    anteriores: dict[str, float] = field(default_factory=dict)
    generadores: dict[str, Generador] = field(default_factory=dict)

    # --- validación -----------------------------------------------------
    def advertencias(self) -> list[str]:
        avisos: list[str] = []
        for clave, gen in self.generadores.items():
            if clave not in self.catalogo:
                avisos.append(f"{clave}: el generador no corresponde a un concepto del catálogo.")
                continue
            unidad = normalizar_unidad(self.catalogo[clave].unidad)
            esperadas = DIMENSIONES_POR_UNIDAD.get(unidad)
            for i, r in enumerate(gen.renglones, start=1):
                if gen.validar_dimensiones and esperadas is not None and r.dimensiones != esperadas:
                    avisos.append(
                        f"{clave} renglón {i}: la unidad {self.catalogo[clave].unidad} suele llevar "
                        f"{esperadas} dimensión(es) y se capturaron {r.dimensiones}."
                    )
                if not (r.eje or r.tramo or r.nivel or r.referencia or r.croquis):
                    avisos.append(f"{clave} renglón {i}: no indica eje, tramo, nivel, croquis ni referencia.")
            if gen.subtotal < 0:
                avisos.append(f"{clave}: la cantidad del periodo resulta negativa.")
        for linea in self.lineas():
            if linea.acumulado > linea.concepto.cantidad + 1e-9:
                exceso = linea.acumulado - linea.concepto.cantidad
                avisos.append(
                    f"{linea.concepto.clave}: el acumulado rebasa lo contratado por "
                    f"{exceso:,.3f} {linea.concepto.unidad}; requiere volumen excedente o convenio."
                )
        for clave in self.anteriores:
            if clave not in self.catalogo:
                avisos.append(f"{clave}: tiene estimado anterior pero no está en el catálogo.")
        return avisos

    # --- cálculo ----------------------------------------------------------
    def cantidad_periodo(self, clave: str) -> float:
        gen = self.generadores.get(clave)
        return gen.subtotal if gen else 0.0

    def lineas(self) -> list[LineaEstimacion]:
        return [
            LineaEstimacion(c, self.anteriores.get(c.clave, 0.0), self.cantidad_periodo(c.clave))
            for c in self.catalogo.values()
        ]

    def caratula(self) -> Caratula:
        importe = sum(linea.importe for linea in self.lineas())
        amortizacion = importe * self.anticipo
        subtotal = importe - amortizacion
        iva = subtotal * self.iva
        total = subtotal + iva
        retenciones = {nombre: importe * tasa for nombre, tasa in self.retenciones.items()}
        liquido = total - sum(retenciones.values())
        return Caratula(importe, amortizacion, subtotal, iva, total, retenciones, liquido)
