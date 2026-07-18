"""
Importa/actualiza los estudiantes en la base de datos a partir de los
Excel de origen del colegio (SIRE). Correr este script cada vez que
cambien esos archivos (ej. inicio de ciclo escolar, altas y bajas).

No genera QR ni toca asistencia -- solo sincroniza la tabla `estudiantes`.
"""

import pandas as pd
import config
import data_access


def cargar_estudiantes():
    df_basicos = pd.read_excel(config.ARCHIVO_BASICOS)
    df_basicos.columns = df_basicos.columns.str.strip()

    df_diversificado = pd.read_excel(config.ARCHIVO_DIVERSIFICADO)
    df_diversificado.columns = df_diversificado.columns.str.strip()
    df_diversificado = df_diversificado[["Código Personal", "Nombres", "Apellidos", "CARRERA"]]
    df_diversificado = df_diversificado.rename(columns={"CARRERA": "GRADO"})

    df = pd.concat([df_basicos, df_diversificado], ignore_index=True)

    estudiantes = []
    codigos_vistos = set()

    for _, fila in df.iterrows():
        codigo_raw = fila["Código Personal"]
        if pd.isna(codigo_raw):
            continue

        codigo = str(codigo_raw).strip()
        if codigo in codigos_vistos:
            print(f"Código duplicado ignorado: {codigo}")
            continue
        codigos_vistos.add(codigo)

        estudiantes.append({
            "codigo_personal": codigo,
            "nombres": str(fila["Nombres"]).strip(),
            "apellidos": str(fila["Apellidos"]).strip(),
            "grado": str(fila["GRADO"]).strip(),
        })

    return estudiantes


if __name__ == "__main__":
    data_access.inicializar_db()
    estudiantes = cargar_estudiantes()
    data_access.importar_estudiantes(estudiantes)
    print(f"{len(estudiantes)} estudiantes importados/actualizados en {data_access.DB_PATH}")
