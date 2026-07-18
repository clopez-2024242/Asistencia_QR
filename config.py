"""
Configuración centralizada del sistema. Lee config.ini desde la carpeta
donde se ejecuta el programa. Si no existe, lo crea con valores por
defecto para que el proyecto funcione "out of the box" y luego se
ajuste editando el archivo, sin tocar código fuente.
"""

import configparser
import os

CONFIG_PATH = "config.ini"

_VALORES_POR_DEFECTO = {
    "rutas": {
        "archivo_basicos": "SIRE BASICOS 2026 PARA CARNET.xlsx",
        "archivo_diversificado": "SIRE DIVER 2026 para carnet.xlsx",
        "carpeta_qr": "qr",
        "base_datos": "asistencia.db",
        "carpeta_asistencia": "asistencia",
    },
    "horarios": {
        "hora_limite_entrada": "13:00:00",
        "hora_limite_salida": "18:30:00",
        "minutos_espera_salida": "30",
        "segundos_bloqueo_qr": "15",
    },
    "alertas": {
        "segundos_en_pantalla": "3",
        "tono_error_hz": "1000",
        "tono_error_ms": "350",
        "tono_exito_hz": "1500",
        "tono_exito_ms": "150",
    },
}


def _crear_config_por_defecto():
    parser = configparser.ConfigParser()
    parser.read_dict(_VALORES_POR_DEFECTO)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        parser.write(f)


def cargar_config():
    if not os.path.exists(CONFIG_PATH):
        _crear_config_por_defecto()
        print(f"Se creó {CONFIG_PATH} con valores por defecto. Revísalo y ajústalo si es necesario.")

    parser = configparser.ConfigParser()
    parser.read(CONFIG_PATH, encoding="utf-8")

    # Aplica valores por defecto para cualquier clave faltante (ej. config.ini viejo)
    for seccion, claves in _VALORES_POR_DEFECTO.items():
        if seccion not in parser:
            parser[seccion] = {}
        for clave, valor in claves.items():
            if clave not in parser[seccion]:
                parser[seccion][clave] = valor

    return parser


CONFIG = cargar_config()

ARCHIVO_BASICOS = CONFIG["rutas"]["archivo_basicos"]
ARCHIVO_DIVERSIFICADO = CONFIG["rutas"]["archivo_diversificado"]
CARPETA_QR = CONFIG["rutas"]["carpeta_qr"]
BASE_DATOS = CONFIG["rutas"]["base_datos"]
CARPETA_ASISTENCIA = CONFIG["rutas"]["carpeta_asistencia"]

HORA_LIMITE_ENTRADA = CONFIG["horarios"]["hora_limite_entrada"]
HORA_LIMITE_SALIDA = CONFIG["horarios"]["hora_limite_salida"]
MINUTOS_ESPERA_SALIDA = CONFIG.getint("horarios", "minutos_espera_salida")
SEGUNDOS_BLOQUEO_QR = CONFIG.getint("horarios", "segundos_bloqueo_qr")

SEGUNDOS_ALERTA_EN_PANTALLA = CONFIG.getint("alertas", "segundos_en_pantalla")
TONO_ERROR_HZ = CONFIG.getint("alertas", "tono_error_hz")
TONO_ERROR_MS = CONFIG.getint("alertas", "tono_error_ms")
TONO_EXITO_HZ = CONFIG.getint("alertas", "tono_exito_hz")
TONO_EXITO_MS = CONFIG.getint("alertas", "tono_exito_ms")
