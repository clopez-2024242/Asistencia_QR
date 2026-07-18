import threading
import getpass

import cv2
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta

import auth
import config
import data_access

# Evitar leer el mismo QR varias veces seguidas
bloqueo_qr = {}
BLOQUEO_SEGUNDOS = config.SEGUNDOS_BLOQUEO_QR

# Estado de la alerta visible en pantalla
mensaje = ""
color_mensaje = (255, 255, 255)
mensaje_hasta = datetime.min


def _reproducir_tono(frecuencia_hz, duracion_ms):
    """
    Reproduce un beep en un hilo aparte para no congelar la vista de la
    cámara mientras suena. Si no hay dispositivo de sonido disponible
    (ej. no estamos en Windows), simplemente no suena -- nunca debe
    tumbar el programa por esto.
    """
    def _sonar():
        try:
            import winsound
            winsound.Beep(frecuencia_hz, duracion_ms)
        except Exception:
            pass

    threading.Thread(target=_sonar, daemon=True).start()


def mostrar_alerta(texto, nivel, ahora):
    """
    nivel: 'error' | 'exito' | 'aviso'
    Actualiza el banner en pantalla y dispara el sonido correspondiente.
    """
    global mensaje, color_mensaje, mensaje_hasta

    colores = {
        "error": (0, 0, 220),      # rojo
        "exito": (0, 160, 0),      # verde
        "aviso": (0, 165, 255),    # naranja
    }

    mensaje = texto
    color_mensaje = colores.get(nivel, (80, 80, 80))
    mensaje_hasta = ahora + timedelta(seconds=config.SEGUNDOS_ALERTA_EN_PANTALLA)

    if nivel == "error":
        _reproducir_tono(config.TONO_ERROR_HZ, config.TONO_ERROR_MS)
    elif nivel == "exito":
        _reproducir_tono(config.TONO_EXITO_HZ, config.TONO_EXITO_MS)


def dibujar_banner(frame):
    """Dibuja un banner de color a todo lo ancho, grande y visible de lejos."""
    if datetime.now() >= mensaje_hasta:
        return

    alto_banner = 100
    ancho = frame.shape[1]

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (ancho, alto_banner), color_mensaje, -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    cv2.putText(frame, mensaje, (20, 65), cv2.FONT_HERSHEY_SIMPLEX,
                1.3, (255, 255, 255), 3, cv2.LINE_AA)


def procesar_codigo(codigo, ahora):
    estudiante = data_access.obtener_estudiante(codigo)
    if estudiante is None:
        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")
        data_access.registrar_intento_desconocido(codigo, fecha, hora)

        print(f"QR no reconocido: {codigo}")
        mostrar_alerta("QR NO RECONOCIDO", "error", ahora)
        return

    nombre = estudiante["nombres"]
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")
    hora_actual = ahora.time()

    registro = data_access.obtener_registro(codigo, fecha)
    if registro is None:
        # No debería pasar si asegurar_registros_del_dia corrió al inicio,
        # pero cubrimos el caso por seguridad.
        print(f"No hay registro del día para {nombre}")
        mostrar_alerta(f"{nombre} - ERROR DE REGISTRO, avisar a administración", "error", ahora)
        return

    # --------- Entrada ---------
    if registro["hora_entrada"] is None:
        estado = "TARDE" if hora_actual > data_access.HORA_LIMITE_ENTRADA else "PRESENTE"
        data_access.registrar_entrada(codigo, fecha, hora, estado)

        print(f"Entrada registrada: {nombre} - {estado}")
        nivel = "aviso" if estado == "TARDE" else "exito"
        mostrar_alerta(f"{nombre} - {estado}", nivel, ahora)
        return

    # --------- Salida ---------
    if registro["hora_salida"] is not None:
        mostrar_alerta(f"{nombre} - YA TIENE ENTRADA Y SALIDA HOY", "aviso", ahora)
        return

    if hora_actual > data_access.HORA_LIMITE_SALIDA:
        print(f"{nombre} no puede marcar salida después de las 6:30 PM")
        mostrar_alerta(f"{nombre} - NO PUEDE MARCAR SALIDA DESPUÉS DE 6:30 PM", "error", ahora)
        return

    hora_entrada_dt = datetime.combine(
        ahora.date(),
        datetime.strptime(registro["hora_entrada"], "%H:%M:%S").time()
    )
    if (ahora - hora_entrada_dt) < timedelta(minutes=config.MINUTOS_ESPERA_SALIDA):
        print(f"{nombre} debe esperar {config.MINUTOS_ESPERA_SALIDA} minutos para marcar salida")
        mostrar_alerta(f"{nombre} - DEBE ESPERAR {config.MINUTOS_ESPERA_SALIDA} MIN PARA SALIR", "aviso", ahora)
        return

    data_access.registrar_salida(codigo, fecha, hora)
    print(f"Salida registrada: {nombre}")
    mostrar_alerta(f"{nombre} - SALIDA REGISTRADA", "exito", ahora)


def desbloquear_con_pin():
    """
    Pide el PIN por consola antes de abrir la cámara. Registra cada
    intento (éxito o fallo) y limita los intentos fallidos seguidos.
    Devuelve True si se desbloqueó, False si se agotaron los intentos.
    """
    data_access.purgar_accesos_antiguos(config.DIAS_RETENCION_ACCESOS)

    for intento in range(1, config.INTENTOS_MAXIMOS + 1):
        pin = getpass.getpass("PIN para desbloquear el lector: ").strip()
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if auth.verificar_pin(pin):
            data_access.registrar_acceso(ahora_str, "EXITOSO")
            return True

        data_access.registrar_acceso(ahora_str, "FALLIDO")
        restantes = config.INTENTOS_MAXIMOS - intento
        if restantes > 0:
            print(f"PIN incorrecto. Intentos restantes: {restantes}")

    print("Demasiados intentos fallidos. Cerrando el programa.")
    return False


def main():
    data_access.inicializar_db()

    if not desbloquear_con_pin():
        return

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    data_access.asegurar_registros_del_dia(fecha_hoy)

    print("Iniciando cámara. Presione ESC para salir.")
    cap = cv2.VideoCapture(0)
    cv2.namedWindow("Escaneo QR", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Escaneo QR", 1280, 720)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("No se pudo leer la cámara.")
                break

            frame = cv2.flip(frame, 1)
            ahora = datetime.now()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            for qr in decode(gray):
                codigo = qr.data.decode("utf-8").strip()

                if codigo in bloqueo_qr:
                    if (ahora - bloqueo_qr[codigo]).total_seconds() < BLOQUEO_SEGUNDOS:
                        continue
                bloqueo_qr[codigo] = ahora

                try:
                    procesar_codigo(codigo, ahora)
                except Exception as e:
                    # Un error en un escaneo no debe tumbar todo el programa
                    print(f"Error procesando código {codigo}: {e}")

            dibujar_banner(frame)

            cv2.imshow("Escaneo QR", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
