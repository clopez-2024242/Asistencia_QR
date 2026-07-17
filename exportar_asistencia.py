"""
Exporta la asistencia de una fecha a un archivo Excel, con una hoja
por grado -- igual que el formato anterior. Se corre a mano cuando
se necesite entregar el reporte, no automáticamente en cada escaneo.

Uso:
    python exportar_asistencia.py              (exporta el día de hoy)
    python exportar_asistencia.py 2026-03-15    (exporta una fecha específica)
"""

import sys
import os
import pandas as pd
from datetime import datetime

import config
import data_access


def exportar(fecha):
    filas = data_access.obtener_asistencia_por_fecha(fecha)
    if not filas:
        print(f"No hay registros de asistencia para la fecha {fecha}.")
        return

    df = pd.DataFrame(filas)
    df = df.rename(columns={
        "codigo_personal": "Código Personal",
        "nombres": "Nombres",
        "apellidos": "Apellidos",
        "grado": "GRADO",
        "fecha": "fecha",
        "hora_entrada": "hora_entrada",
        "hora_salida": "hora_salida",
        "estado": "estado",
        "justificado": "justificado",
    })

    os.makedirs(config.CARPETA_ASISTENCIA, exist_ok=True)
    archivo_salida = f"{config.CARPETA_ASISTENCIA}/asistencia_{fecha.replace('-', '_')}.xlsx"

    with pd.ExcelWriter(archivo_salida, engine="openpyxl") as writer:
        for grado in df["GRADO"].unique():
            df_grado = df[df["GRADO"] == grado]
            df_grado.to_excel(writer, sheet_name=str(grado)[:31], index=False)

    print(f"Exportado: {archivo_salida}")


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    exportar(fecha)