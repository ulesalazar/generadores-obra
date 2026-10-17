# generadores-obra

**Números generadores y estimaciones de obra en México, de un YAML a un Excel listo
para firmar.** Captura lo que se midió (nivel, eje, tramo, croquis y dimensiones) y
obtén los generadores con fórmulas, el resumen contra lo contratado y la carátula con
anticipo, IVA, retenciones y líquido a pagar.

[![CI](https://github.com/ulesalazar/generadores-obra/actions/workflows/ci.yml/badge.svg)](https://github.com/ulesalazar/generadores-obra/actions/workflows/ci.yml)
![Licencia Apache-2.0](https://img.shields.io/badge/licencia-Apache--2.0-blue)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

```
$ generadores-obra revisar ejemplos/estimacion-02.yaml
Clave        Unidad   Contratado    Anterior        Esta   Acumulado   Avance
CIM-010          m2      180.000      95.000      69.600     164.600    91.4%
CIM-030          m3       24.000      24.000       0.000      24.000   100.0%
...

Importe de la estimación               113,862.79
Amortización del anticipo              -34,158.84
IVA                                     12,752.63
Retención inspección vigilancia           -569.31
Líquido a pagar                         91,887.27
```

## Para qué sirve

Toda estimación de obra pública se acompaña de sus números generadores (RLOPSRM,
art. 132). Esta herramienta los arma de forma ordenada y revisable:

- Cada renglón dice **dónde** está lo medido (nivel, eje, tramo, croquis o lámina) y
  **cuánto** mide: `parcial = cant × largo × ancho × alto`. Las deducciones (vanos,
  huecos) van con cantidad negativa.
- Suma el periodo y lo compara con lo **contratado** y lo **estimado antes**: acumulado,
  por ejecutar y porcentaje de avance. Marca en rojo el concepto que rebasa lo
  contratado, porque requiere volumen excedente o convenio.
- Arma la **carátula**: importe, amortización del anticipo, IVA, retenciones (5 al
  millar u otras) y líquido a pagar.
- **Advierte** lo que un supervisor rechazaría: renglones sin ubicación, dimensiones
  que no corresponden a la unidad (un m³ con dos medidas), generadores sin concepto en
  el catálogo.

## Instalación

```bash
pip install git+https://github.com/ulesalazar/generadores-obra.git
```

## Uso

```bash
generadores-obra revisar ejemplos/estimacion-02.yaml             # resumen y advertencias
generadores-obra revisar ejemplos/estimacion-02.yaml --estricto  # falla si hay advertencias
generadores-obra excel   ejemplos/estimacion-02.yaml estimacion-02.xlsx
```

### Captura

```yaml
obra: Construcción de aulas
contrato: OP-2026-014
estimacion: 2
periodo: {del: 2026-09-01, al: 2026-09-30}
iva: 0.16
anticipo: 0.30
retenciones: {inspección_vigilancia: 0.005}
firmas:
  Superintendente de construcción: Nombre
  Residente de obra: Nombre

catalogo:
  - {clave: ALB-020, descripcion: Muro de block 15 cm, unidad: m2, cantidad: 420, pu: 604.21}
anteriores:
  ALB-020: 160.00

generadores:
  - clave: ALB-020
    renglones:
      - {nivel: PB, eje: "A", tramo: "1-3", largo: 9.00, alto: 2.80, croquis: G-02}
      - {nivel: PB, eje: "1", tramo: "A-B", cant: -1, largo: 1.00, alto: 2.10, nota: Vano P-1}

generadores_csv:            # renglones capturados en Excel y guardados como CSV
  - aplanados.csv
```

El CSV lleva las columnas `clave, nivel, eje, tramo, cant, largo, ancho, alto, croquis, nota`.
El ejemplo completo está en [`ejemplos/estimacion-02.yaml`](ejemplos/estimacion-02.yaml).

### El libro de Excel

| Hoja | Contenido |
|---|---|
| Carátula | importe, anticipo, IVA, retenciones y líquido a pagar, con firmas |
| Resumen | contratado, P. U., anterior, esta estimación, acumulado, por ejecutar, avance e importes |
| Generadores | un bloque por concepto con la fórmula de cada parcial y su subtotal |
| Catalogo_Importar | partida, clave, descripción, unidad y cantidad en valores planos para Neodata u OPUS |
| Advertencias | lo que conviene revisar antes de firmar |

Todo está ligado: corregir una dimensión actualiza el subtotal, el resumen y la
carátula. Cada hoja está configurada para imprimirse a lo ancho de una carta. Las
pruebas recalculan el libro en LibreOffice y lo comparan contra Python.

## Con takeoff-mx y apu-mx

```
takeoff-mx  →  generadores-obra  →  apu-mx
(mide en el plano)  (ordena y revisa)  (precio unitario y presupuesto)
```

- **Desde [takeoff-mx](https://github.com/ulesalazar/takeoff-mx):** el JSON de
  generadores que exporta (`takeoff-mx.generadores.v1`) se lee directo.
  Las mediciones de agente sin revisar quedan marcadas en el libro.

  ```bash
  generadores-obra excel ejemplos/desde-takeoff-mx.json cuantificacion.xlsx
  ```

- **Hacia [apu-mx](https://github.com/ulesalazar/apu-mx):** escribe la sección
  `presupuesto:` con cantidades netas.

  ```bash
  generadores-obra apu-mx ejemplos/desde-takeoff-mx.json presupuesto.yaml
  ```

Las cantidades que salen hacia el presupuesto son **netas**. El desperdicio que trae
takeoff-mx se muestra como dato informativo: en un análisis de precio unitario el
desperdicio va en la matriz de cada material, y sumarlo también a la cantidad lo
cobraría dos veces.

## Criterios

- IVA sobre el importe menos la amortización del anticipo.
- Retenciones (5 al millar, 2 al millar u otras) sobre el importe de la estimación
  sin IVA. Si su contrato indica otra base, ajuste la tasa o la fórmula en la carátula.
- Unidades y dimensiones esperadas: m³ = 3, m² = 2, m y ml = 1; piezas, salidas, kg,
  lote = 0. Es una advertencia, no un error: un m² medido como área directa es válido.

## Licencia

Apache-2.0. Ver [LICENSE](LICENSE) y [NOTICE](NOTICE).

Hecho por [Consultoría de Costos · presupuestoai.com](https://presupuestoai.com).
