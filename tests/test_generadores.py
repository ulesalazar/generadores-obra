import json
import shutil
import subprocess
from pathlib import Path

import pytest

from generadores_obra import (
    ErrorGenerador,
    Renglon,
    cargar,
    desde_takeoff_mx,
    estimacion_desde_dict,
)
from generadores_obra.cli import main

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"
YAML = EJEMPLOS / "estimacion-02.yaml"
TAKEOFF = EJEMPLOS / "desde-takeoff-mx.json"


def estimacion_basica(**extra):
    datos = {
        "obra": "Prueba",
        "anticipo": 0.30,
        "iva": 0.16,
        "retenciones": {"inspeccion_vigilancia": 0.005},
        "catalogo": [
            {"clave": "MURO", "descripcion": "Muro", "unidad": "m2", "cantidad": 100, "pu": 600},
            {"clave": "PZA", "descripcion": "Salida", "unidad": "sal", "cantidad": 10, "pu": 1000},
        ],
        "anteriores": {"MURO": 40},
        "generadores": [
            {
                "clave": "MURO",
                "renglones": [
                    {"eje": "A", "tramo": "1-2", "largo": 10, "alto": 3},
                    {"eje": "A", "tramo": "1-2", "cant": -2, "largo": 1, "alto": 2.5, "nota": "vanos"},
                ],
            },
            {"clave": "PZA", "renglones": [{"nivel": "PB", "cant": 4}]},
        ],
    }
    datos.update(extra)
    return estimacion_desde_dict(datos)


def test_parcial_y_deducciones():
    assert Renglon(cant=2, largo=3, alto=2.5).parcial == pytest.approx(15)
    assert Renglon(cant=-1, largo=0.9, alto=2.1).parcial == pytest.approx(-1.89)
    assert Renglon(cant=5).parcial == 5
    est = estimacion_basica()
    assert est.generadores["MURO"].subtotal == pytest.approx(30 - 5)


def test_acumulados_y_avance():
    est = estimacion_basica()
    muro = [x for x in est.lineas() if x.concepto.clave == "MURO"][0]
    assert muro.anterior == 40
    assert muro.esta == pytest.approx(25)
    assert muro.acumulado == pytest.approx(65)
    assert muro.por_ejecutar == pytest.approx(35)
    assert muro.avance == pytest.approx(0.65)
    assert muro.importe == pytest.approx(25 * 600)


def test_caratula():
    car = estimacion_basica().caratula()
    importe = 25 * 600 + 4 * 1000
    assert car.importe == pytest.approx(importe)
    assert car.amortizacion_anticipo == pytest.approx(importe * 0.30)
    assert car.subtotal == pytest.approx(importe * 0.70)
    assert car.iva == pytest.approx(importe * 0.70 * 0.16)
    assert car.retenciones["inspeccion_vigilancia"] == pytest.approx(importe * 0.005)
    assert car.liquido == pytest.approx(importe * 0.70 * 1.16 - importe * 0.005)


def test_advertencias():
    est = estimacion_basica(anteriores={"MURO": 90, "FANTASMA": 1})
    est.generadores["PZA"].renglones.append(Renglon(cant=1, largo=2, nivel="PB"))
    avisos = " | ".join(est.advertencias())
    assert "rebasa lo contratado" in avisos  # 90 + 25 > 100
    assert "FANTASMA" in avisos
    assert "dimensión" in avisos  # salida con largo
    sin_ubicacion = estimacion_basica(generadores=[{"clave": "PZA", "renglones": [{"cant": 2}]}])
    assert any("no indica eje" in a for a in sin_ubicacion.advertencias())
    assert estimacion_basica().advertencias() == []


def test_errores_de_captura():
    with pytest.raises(ErrorGenerador, match="no es un número"):
        estimacion_basica(generadores=[{"clave": "MURO", "renglones": [{"largo": "diez"}]}])
    with pytest.raises(ErrorGenerador, match="no reconocidos"):
        estimacion_basica(generadores=[{"clave": "MURO", "renglones": [{"lago": 3}]}])
    with pytest.raises(ErrorGenerador, match="duplicada"):
        estimacion_basica(
            catalogo=[{"clave": "X", "unidad": "m", "cantidad": 1, "pu": 1}] * 2,
            generadores=[],
            anteriores={},
        )


def test_ejemplo_yaml_con_csv():
    est = cargar(YAML)
    assert est.generadores["ALB-020"].subtotal == pytest.approx(2 * 9 * 2.8 + 2 * 7.2 * 2.8 - 2.1 - 3 * 2.16)
    assert est.generadores["ACA-030"].subtotal == pytest.approx(77.76)
    assert est.generadores["INE-002"].subtotal == 8
    assert est.advertencias() == []
    assert est.caratula().liquido == pytest.approx(92_954.52, abs=0.01)


def test_importa_takeoff_mx_con_cantidades_netas():
    datos = json.loads(TAKEOFF.read_text(encoding="utf-8"))
    est = desde_takeoff_mx(datos, precios={"ACA-001": 500})
    for c in datos["conceptos"]:
        assert est.generadores[c["clave"]].subtotal == pytest.approx(c["subtotal"], abs=1e-3)
        assert est.catalogo[c["clave"]].cantidad == pytest.approx(c["subtotal"], abs=1e-3)
    assert est.generadores["ACA-001"].desperdicio == pytest.approx(0.05)
    assert est.caratula().importe == pytest.approx(500 * datos["conceptos"][0]["subtotal"], abs=1e-6)
    # Las mediciones de agente sin revisar quedan marcadas.
    assert all("sin revisar" in r.origen for r in est.generadores["ACA-001"].renglones)
    # Las dimensiones de takeoff no generan advertencias de unidad.
    assert not any("dimensión" in a for a in est.advertencias())
    with pytest.raises(ErrorGenerador):
        desde_takeoff_mx({"schema": "otro"})


def test_cli(capsys, tmp_path):
    assert main(["revisar", str(YAML)]) == 0
    assert "Líquido a pagar" in capsys.readouterr().out
    assert main(["excel", str(YAML), str(tmp_path / "e.xlsx")]) == 0
    assert main(["apu-mx", str(TAKEOFF)]) == 0
    assert "{clave: ACA-001, cantidad: 22.814}" in capsys.readouterr().out
    malo = tmp_path / "malo.yaml"
    malo.write_text(
        "catalogo: [{clave: A, unidad: m, cantidad: 1, pu: 1}]\nanteriores: {A: 5}\n", encoding="utf-8"
    )
    assert main(["revisar", str(malo), "--estricto"]) == 1


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice no está instalado")
@pytest.mark.parametrize("fuente", [YAML, TAKEOFF])
def test_excel_recalcula_igual_que_python(tmp_path, fuente):
    openpyxl = pytest.importorskip("openpyxl")
    from generadores_obra.excel import exportar_excel

    est = cargar(fuente)
    original = exportar_excel(est, tmp_path / "libro.xlsx")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--calc",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(tmp_path / "r"),
            str(original),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    wb = openpyxl.load_workbook(tmp_path / "r" / "libro.xlsx", data_only=True)
    lineas = {x.concepto.clave: x for x in est.lineas()}
    for fila in wb["Resumen"].iter_rows(values_only=True):
        if fila[1] in lineas:
            assert fila[7] == pytest.approx(lineas[fila[1]].esta, abs=1e-9)
            assert fila[8] == pytest.approx(lineas[fila[1]].acumulado, abs=1e-9)
    liquido = [r[2] for r in wb["Carátula"].iter_rows(values_only=True) if r[0] == "Líquido a pagar"][0]
    assert liquido == pytest.approx(est.caratula().liquido, abs=1e-6)
