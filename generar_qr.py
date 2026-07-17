"""
Genera las imágenes QR para todos los estudiantes que ya estén
sincronizados en la base de datos (correr primero importar_estudiantes.py
si hay estudiantes nuevos o cambios).

La carpeta de salida y demás rutas se controlan desde config.ini,
no están fijas en el código.
"""

import os
import re
import sqlite3

import qrcode

import config
import data_access


def _nombre_archivo_seguro(texto):
    """Limpia caracteres no válidos para nombres de archivo/carpeta."""
    texto = re.sub(r'[<>:"/\\|?*]', '', texto)
    return texto.strip().replace(" ", "_")


def obtener_todos_los_estudiantes():
    with sqlite3.connect(data_access.DB_PATH) as con:
        con.row_factory = sqlite3.Row
        filas = con.execute("SELECT * FROM estudiantes").fetchall()
        return [dict(f) for f in filas]


def generar_qr_para_estudiante(estudiante):
    codigo = estudiante["codigo_personal"]
    nombre = _nombre_archivo_seguro(estudiante["nombres"])
    apellido = _nombre_archivo_seguro(estudiante["apellidos"])
    grado = _nombre_archivo_seguro(estudiante["grado"])

    carpeta_grado = os.path.join(config.CARPETA_QR, grado)
    os.makedirs(carpeta_grado, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(codigo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    archivo_qr = f"{codigo}_{apellido}_{nombre}.jpg"
    img.save(os.path.join(carpeta_grado, archivo_qr), "JPEG")
    return archivo_qr


def main():
    data_access.inicializar_db()
    estudiantes = obtener_todos_los_estudiantes()

    if not estudiantes:
        print("No hay estudiantes en la base de datos. "
              "Corre primero importar_estudiantes.py.")
        return

    for estudiante in estudiantes:
        archivo = generar_qr_para_estudiante(estudiante)
        print(f"QR generado para {estudiante['codigo_personal']} ({estudiante['grado']}) -> {archivo}")

    print(f"Listo: {len(estudiantes)} QR generados en '{config.CARPETA_QR}/'.")


if __name__ == "__main__":
    main()