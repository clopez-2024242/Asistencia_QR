"""
Cambia el PIN de acceso al lector.

Uso: python cambiar_pin.py

Pide el nuevo PIN dos veces (para evitar errores de tecleo) y guarda
su hash en config.ini. No pide el PIN anterior a propósito: si el PIN
se filtró, quien tiene acceso físico a la máquina debe poder
reemplazarlo de inmediato sin depender del PIN comprometido.
"""

import configparser
import getpass

import auth
import config


def main():
    print("Cambio de PIN del lector de asistencia.")
    nuevo_pin = getpass.getpass("Nuevo PIN: ").strip()
    confirmacion = getpass.getpass("Confirma el nuevo PIN: ").strip()

    if not nuevo_pin:
        print("El PIN no puede estar vacío. No se hicieron cambios.")
        return

    if nuevo_pin != confirmacion:
        print("Los PIN no coinciden. No se hicieron cambios.")
        return

    parser = configparser.ConfigParser()
    parser.read(config.CONFIG_PATH, encoding="utf-8")

    if "seguridad" not in parser:
        parser["seguridad"] = {}
    parser["seguridad"]["pin_hash"] = auth.generar_hash(nuevo_pin)

    with open(config.CONFIG_PATH, "w", encoding="utf-8") as f:
        parser.write(f)

    print("PIN actualizado correctamente.")


if __name__ == "__main__":
    main()
