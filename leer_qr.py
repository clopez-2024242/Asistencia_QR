import cv2
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta

import config
import data_access

# Evitar leer el mismo QR varias veces seguidas
bloqueo_qr = {}
BLOQUEO_SEGUNDOS = config.SEGUNDOS_BLOQUEO_QR

# Visuales
mensaje = ""
color_mensaje = (255, 255, 255)
mensaje_hasta = datetime.min


def procesar_codigo(codigo, ahora):
    global mensaje, color_mensaje, mensaje_hasta

    estudiante = data_access.obtener_estudiante(codigo)
    if estudiante is None:
        print(f"QR no reconocido: {codigo}")
        mensaje = "QR no reconocido"
        color_mensaje = (0, 0, 255)
        mensaje_hasta = ahora + timedelta(seconds=2)
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
        return

    # --------- Entrada ---------
    if registro["hora_entrada"] is None:
        estado = "TARDE" if hora_actual > data_access.HORA_LIMITE_ENTRADA else "PRESENTE"
        data_access.registrar_entrada(codigo, fecha, hora, estado)

        print(f"Entrada registrada: {nombre} - {estado}")
        mensaje = f"{nombre} - {estado}"
        color_mensaje = (0, 255, 0)
        mensaje_hasta = ahora + timedelta(seconds=2)
        return

    # --------- Salida ---------
    if registro["hora_salida"] is not None:
        mensaje = f"{nombre} - ya tiene entrada y salida hoy"
        color_mensaje = (0, 255, 255)
        mensaje_hasta = ahora + timedelta(seconds=2)
        return

    if hora_actual > data_access.HORA_LIMITE_SALIDA:
        print(f"{nombre} no puede marcar salida después de las 6:30 PM")
        mensaje = f"{nombre} - no puede marcar salida después de las 6:30 PM"
        color_mensaje = (0, 0, 255)
        mensaje_hasta = ahora + timedelta(seconds=2)
        return

    hora_entrada_dt = datetime.combine(
        ahora.date(),
        datetime.strptime(registro["hora_entrada"], "%H:%M:%S").time()
    )
    if (ahora - hora_entrada_dt) < timedelta(minutes=30):
        print(f"{nombre} debe esperar 30 minutos para marcar salida")
        mensaje = f"{nombre} - debe esperar 30 min para marcar salida"
        color_mensaje = (0, 255, 255)
        mensaje_hasta = ahora + timedelta(seconds=2)
        return

    data_access.registrar_salida(codigo, fecha, hora)
    print(f"Salida registrada: {nombre}")
    mensaje = f"{nombre} - SALIDA REGISTRADA"
    color_mensaje = (0, 255, 0)
    mensaje_hasta = ahora + timedelta(seconds=2)


def main():
    data_access.inicializar_db()

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

            if datetime.now() < mensaje_hasta:
                cv2.putText(frame, mensaje, (10, 50), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, color_mensaje, 2)

            cv2.imshow("Escaneo QR", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()