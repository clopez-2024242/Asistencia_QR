"""
Capa de acceso a datos del sistema de asistencia.

Regla de oro: ningún otro archivo del proyecto debe importar `sqlite3`
ni tocar la base de datos directamente. Todo pasa por las funciones
de este módulo.

Por qué: el día que el sistema deba correr en varias máquinas al mismo
tiempo, estas mismas funciones pueden reimplementarse para hablarle a
un servidor por HTTP en vez de tocar el archivo .db local. El código
que las llama (leer_qr.py, generar_qr.py, exportar_asistencia.py) no
se entera del cambio.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

DB_PATH = config.BASE_DATOS

HORA_LIMITE_ENTRADA = datetime.strptime(config.HORA_LIMITE_ENTRADA, "%H:%M:%S").time()
HORA_LIMITE_SALIDA = datetime.strptime(config.HORA_LIMITE_SALIDA, "%H:%M:%S").time()


@contextmanager
def _conexion():
    """
    Abre una conexión SQLite con configuración segura para escrituras
    concurrentes locales (modo WAL) y la cierra siempre al salir,
    incluso si hay una excepción.
    """
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar_db():
    """Crea las tablas si no existen. Seguro de llamar varias veces."""
    with _conexion() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS estudiantes (
                codigo_personal TEXT PRIMARY KEY,
                nombres TEXT NOT NULL,
                apellidos TEXT NOT NULL,
                grado TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS asistencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_personal TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora_entrada TEXT,
                hora_salida TEXT,
                estado TEXT NOT NULL DEFAULT 'AUSENTE',
                justificado TEXT NOT NULL DEFAULT 'NO',
                FOREIGN KEY (codigo_personal) REFERENCES estudiantes(codigo_personal),
                UNIQUE (codigo_personal, fecha)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS intentos_desconocidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_leido TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS accesos_lector (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT NOT NULL,
                resultado TEXT NOT NULL
            )
        """)


def importar_estudiantes(lista_estudiantes):
    """
    lista_estudiantes: lista de dicts con claves
    codigo_personal, nombres, apellidos, grado.
    Hace upsert: si el código ya existe, actualiza sus datos.
    """
    with _conexion() as con:
        con.executemany("""
            INSERT INTO estudiantes (codigo_personal, nombres, apellidos, grado)
            VALUES (:codigo_personal, :nombres, :apellidos, :grado)
            ON CONFLICT(codigo_personal) DO UPDATE SET
                nombres=excluded.nombres,
                apellidos=excluded.apellidos,
                grado=excluded.grado
        """, lista_estudiantes)


def obtener_estudiante(codigo_personal):
    """Devuelve un dict con los datos del estudiante, o None si no existe."""
    with _conexion() as con:
        con.row_factory = sqlite3.Row
        fila = con.execute(
            "SELECT * FROM estudiantes WHERE codigo_personal = ?",
            (codigo_personal,)
        ).fetchone()
        return dict(fila) if fila else None


def asegurar_registros_del_dia(fecha):
    """
    Crea un registro AUSENTE para cada estudiante que aún no tenga
    registro en la fecha dada. Se llama una vez al iniciar el lector.
    """
    with _conexion() as con:
        con.execute("""
            INSERT OR IGNORE INTO asistencia (codigo_personal, fecha, estado, justificado)
            SELECT codigo_personal, ?, 'AUSENTE', 'NO' FROM estudiantes
        """, (fecha,))


def obtener_registro(codigo_personal, fecha):
    with _conexion() as con:
        con.row_factory = sqlite3.Row
        fila = con.execute(
            "SELECT * FROM asistencia WHERE codigo_personal = ? AND fecha = ?",
            (codigo_personal, fecha)
        ).fetchone()
        return dict(fila) if fila else None


def registrar_entrada(codigo_personal, fecha, hora, estado):
    """
    Actualiza únicamente la fila de este estudiante/fecha.
    No toca ninguna otra fila de la tabla.
    """
    with _conexion() as con:
        con.execute("""
            UPDATE asistencia
            SET hora_entrada = ?, estado = ?
            WHERE codigo_personal = ? AND fecha = ?
        """, (hora, estado, codigo_personal, fecha))


def registrar_salida(codigo_personal, fecha, hora):
    with _conexion() as con:
        con.execute("""
            UPDATE asistencia
            SET hora_salida = ?
            WHERE codigo_personal = ? AND fecha = ?
        """, (hora, codigo_personal, fecha))


def registrar_intento_desconocido(codigo_leido, fecha, hora):
    with _conexion() as con:
        con.execute("""
            INSERT INTO intentos_desconocidos (codigo_leido, fecha, hora)
            VALUES (?, ?, ?)
        """, (codigo_leido, fecha, hora))


def obtener_intentos_desconocidos(fecha):
    with _conexion() as con:
        con.row_factory = sqlite3.Row
        filas = con.execute("""
            SELECT codigo_leido, fecha, hora
            FROM intentos_desconocidos
            WHERE fecha = ?
            ORDER BY hora
        """, (fecha,)).fetchall()
        return [dict(f) for f in filas]


def registrar_acceso(fecha_hora, resultado):
    """resultado: 'EXITOSO' o 'FALLIDO'"""
    with _conexion() as con:
        con.execute(
            "INSERT INTO accesos_lector (fecha_hora, resultado) VALUES (?, ?)",
            (fecha_hora, resultado)
        )


def purgar_accesos_antiguos(dias_retencion):
    """
    Borra los registros de acceso más viejos que `dias_retencion` días.
    Se llama automáticamente al iniciar el lector, así el registro
    nunca crece indefinidamente sin necesidad de mantenimiento manual.
    """
    with _conexion() as con:
        con.execute("""
            DELETE FROM accesos_lector
            WHERE fecha_hora < datetime('now', ?)
        """, (f"-{dias_retencion} days",))


def obtener_asistencia_por_fecha(fecha):
    """Para exportar a Excel: todas las filas de asistencia de una fecha, con datos del estudiante."""
    with _conexion() as con:
        con.row_factory = sqlite3.Row
        filas = con.execute("""
            SELECT a.codigo_personal, e.nombres, e.apellidos, e.grado,
                   a.fecha, a.hora_entrada, a.hora_salida, a.estado, a.justificado
            FROM asistencia a
            JOIN estudiantes e ON e.codigo_personal = a.codigo_personal
            WHERE a.fecha = ?
            ORDER BY e.grado, e.apellidos, e.nombres
        """, (fecha,)).fetchall()
        return [dict(f) for f in filas]
