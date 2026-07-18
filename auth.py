"""
Autenticación simple por PIN para desbloquear el lector.

No es un sistema multiusuario -- es un candado compartido para evitar
que cualquiera con acceso físico a la máquina abra el lector sin
autorización. El PIN se guarda como hash SHA-256 en config.ini, nunca
en texto plano.
"""

import hashlib

import config


def generar_hash(pin):
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verificar_pin(pin):
    return generar_hash(pin) == config.PIN_HASH
