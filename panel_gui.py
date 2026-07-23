"""
Interfaz gráfica del lector de asistencia.

Reemplaza el uso de consola de leer_qr.py por una ventana con:
  1. Pantalla de PIN (teclado numérico) para desbloquear el lector.
  2. Panel principal: cámara en grande, panel de control, tarjeta del
     último escaneo, y una barra de resumen del día.

La lógica de negocio (entrada/salida/tardanza, límites de horario,
bloqueo anti-doble-escaneo) no cambia respecto a leer_qr.py -- solo
cambia cómo se muestra al operador.
"""

import threading
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import font as tkfont

import cv2
from PIL import Image, ImageTk
from pyzbar.pyzbar import decode

import auth
import config
import data_access

COLOR_FONDO = "#f4f3ee"
COLOR_TARJETA = "#ffffff"
COLOR_TEXTO = "#2c2c2a"
COLOR_TEXTO_SEC = "#5f5e5a"

NIVEL_ESTILOS = {
    "exito": {"fondo": "#eaf3de", "texto": "#27500a"},
    "aviso": {"fondo": "#faeeda", "texto": "#633806"},
    "error": {"fondo": "#fcebeb", "texto": "#791f1f"},
    "neutral": {"fondo": "#ffffff", "texto": COLOR_TEXTO_SEC},
}

BLOQUEO_SEGUNDOS = config.SEGUNDOS_BLOQUEO_QR


def _reproducir_tono(frecuencia_hz, duracion_ms):
    def _sonar():
        try:
            import winsound
            winsound.Beep(frecuencia_hz, duracion_ms)
        except Exception:
            pass
    threading.Thread(target=_sonar, daemon=True).start()


class PantallaPin(tk.Frame):
    """Pantalla de bloqueo con teclado numérico."""

    def __init__(self, master, al_desbloquear):
        super().__init__(master, bg=COLOR_FONDO)
        self.al_desbloquear = al_desbloquear
        self.pin_actual = ""
        self.intentos_restantes = config.INTENTOS_MAXIMOS

        data_access.purgar_accesos_antiguos(config.DIAS_RETENCION_ACCESOS)

        contenedor = tk.Frame(self, bg=COLOR_TARJETA, highlightbackground="#d3d1c7",
                               highlightthickness=1)
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        pad = tk.Frame(contenedor, bg=COLOR_TARJETA)
        pad.pack(padx=32, pady=28)

        fuente_titulo = tkfont.Font(size=15, weight="normal")
        fuente_sub = tkfont.Font(size=11)

        tk.Label(pad, text="Desbloquear lector", font=fuente_titulo,
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO).pack(pady=(0, 2))
        tk.Label(pad, text="Ingresa el PIN para iniciar el turno", font=fuente_sub,
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SEC).pack(pady=(0, 16))

        self.lbl_puntos = tk.Label(pad, text="", font=tkfont.Font(size=18),
                                    bg=COLOR_TARJETA, fg=COLOR_TEXTO)
        self.lbl_puntos.pack(pady=(0, 16))

        teclado = tk.Frame(pad, bg=COLOR_TARJETA)
        teclado.pack()

        botones = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "<-"]
        for i, etiqueta in enumerate(botones):
            fila, col = divmod(i, 3)
            if etiqueta == "":
                continue
            comando = self._borrar if etiqueta == "<-" else (lambda e=etiqueta: self._agregar_digito(e))
            btn = tk.Button(teclado, text=etiqueta, width=5, height=2,
                             font=tkfont.Font(size=13), command=comando,
                             relief="flat", bg="#f1efe8", activebackground="#e4e2d8")
            btn.grid(row=fila, column=col, padx=4, pady=4)

        self.lbl_estado = tk.Label(pad, text=f"{self.intentos_restantes} intentos disponibles",
                                    font=fuente_sub, bg=COLOR_TARJETA, fg=COLOR_TEXTO_SEC)
        self.lbl_estado.pack(pady=(14, 0))

        self.bind_all("<Key>", self._tecla_presionada)

    def _tecla_presionada(self, evento):
        if evento.char.isdigit():
            self._agregar_digito(evento.char)
        elif evento.keysym == "BackSpace":
            self._borrar()
        elif evento.keysym == "Return":
            self._verificar()

    def _agregar_digito(self, digito):
        if len(self.pin_actual) >= 8:
            return
        self.pin_actual += digito
        self._actualizar_puntos()
        if len(self.pin_actual) >= 4:
            self.after(150, self._verificar)

    def _borrar(self):
        self.pin_actual = self.pin_actual[:-1]
        self._actualizar_puntos()

    def _actualizar_puntos(self):
        self.lbl_puntos.config(text=" ".join("•" for _ in self.pin_actual) or " ")

    def _verificar(self):
        if not self.pin_actual:
            return
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if auth.verificar_pin(self.pin_actual):
            data_access.registrar_acceso(ahora_str, "EXITOSO")
            self.al_desbloquear()
            return

        data_access.registrar_acceso(ahora_str, "FALLIDO")
        self.intentos_restantes -= 1
        self.pin_actual = ""
        self._actualizar_puntos()

        if self.intentos_restantes <= 0:
            self.lbl_estado.config(text="Demasiados intentos. Cerrando.", fg="#791f1f")
            self.after(1500, self.master.destroy)
        else:
            self.lbl_estado.config(text=f"PIN incorrecto — {self.intentos_restantes} intentos disponibles",
                                    fg="#791f1f")


class PantallaPrincipal(tk.Frame):
    """Panel de 3 zonas: cámara, control, tarjeta de último escaneo + resumen."""

    def __init__(self, master):
        super().__init__(master, bg=COLOR_FONDO)

        self.captura = None
        self.corriendo = False
        self.bloqueo_qr = {}

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        data_access.asegurar_registros_del_dia(fecha_hoy)

        # --- Layout raíz: fila superior (cámara + panel) y barra inferior ---
        fila_superior = tk.Frame(self, bg=COLOR_FONDO)
        fila_superior.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        self.barra_resumen = tk.Frame(self, bg=COLOR_TARJETA, highlightbackground="#d3d1c7",
                                       highlightthickness=1)
        self.barra_resumen.pack(fill="x", padx=16, pady=(0, 16))

        # --- Zona cámara ---
        marco_camara = tk.Frame(fila_superior, bg="#e4e2d8")
        marco_camara.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.lbl_camara = tk.Label(marco_camara, bg="#e4e2d8")
        self.lbl_camara.pack(fill="both", expand=True)

        # --- Zona panel derecho ---
        panel_derecho = tk.Frame(fila_superior, bg=COLOR_FONDO, width=260)
        panel_derecho.pack(side="right", fill="y")
        panel_derecho.pack_propagate(False)

        marco_control = tk.Frame(panel_derecho, bg=COLOR_TARJETA, highlightbackground="#d3d1c7",
                                  highlightthickness=1)
        marco_control.pack(fill="x", pady=(0, 8))
        tk.Label(marco_control, text="Control", font=tkfont.Font(size=10),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SEC).pack(anchor="w", padx=12, pady=(10, 6))
        self.btn_toggle = tk.Button(marco_control, text="Iniciar lector", relief="flat",
                                     bg="#f1efe8", command=self._alternar_lector)
        self.btn_toggle.pack(fill="x", padx=12, pady=(0, 8))
        tk.Button(marco_control, text="Exportar Excel", relief="flat", bg="#f1efe8",
                  command=self._exportar).pack(fill="x", padx=12, pady=(0, 12))

        self.marco_tarjeta = tk.Frame(panel_derecho, bg=COLOR_TARJETA, highlightbackground="#d3d1c7",
                                       highlightthickness=1)
        self.marco_tarjeta.pack(fill="both", expand=True)
        self._construir_tarjeta_vacia()

        # --- Barra de resumen ---
        self.etiquetas_resumen = {}
        for clave, texto in [("presentes", "Presentes"), ("tardanzas", "Tardanzas"),
                              ("ausentes", "Ausentes"), ("salidas", "Salidas")]:
            bloque = tk.Frame(self.barra_resumen, bg=COLOR_TARJETA)
            bloque.pack(side="left", expand=True, pady=10)
            lbl_num = tk.Label(bloque, text="0", font=tkfont.Font(size=16, weight="bold"),
                                bg=COLOR_TARJETA, fg=COLOR_TEXTO)
            lbl_num.pack()
            tk.Label(bloque, text=texto, font=tkfont.Font(size=9),
                     bg=COLOR_TARJETA, fg=COLOR_TEXTO_SEC).pack()
            self.etiquetas_resumen[clave] = lbl_num

        self._actualizar_resumen()

    # --- Tarjeta de último escaneo ---

    def _construir_tarjeta_vacia(self):
        for hijo in self.marco_tarjeta.winfo_children():
            hijo.destroy()
        tk.Label(self.marco_tarjeta, text="Esperando el primer escaneo",
                 font=tkfont.Font(size=10), bg=COLOR_TARJETA, fg=COLOR_TEXTO_SEC,
                 wraplength=200, justify="center").place(relx=0.5, rely=0.5, anchor="center")

    def _actualizar_tarjeta(self, nombre, subtitulo1, subtitulo2, estado_texto, hora, nivel):
        estilo = NIVEL_ESTILOS.get(nivel, NIVEL_ESTILOS["neutral"])
        for hijo in self.marco_tarjeta.winfo_children():
            hijo.destroy()
        self.marco_tarjeta.config(bg=estilo["fondo"])

        contenido = tk.Frame(self.marco_tarjeta, bg=estilo["fondo"])
        contenido.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(contenido, text="Último escaneo", font=tkfont.Font(size=9),
                 bg=estilo["fondo"], fg=estilo["texto"]).pack(anchor="w")
        tk.Label(contenido, text=nombre, font=tkfont.Font(size=13, weight="bold"),
                 bg=estilo["fondo"], fg=estilo["texto"], wraplength=210, justify="left"
                 ).pack(anchor="w", pady=(8, 0))
        if subtitulo1:
            tk.Label(contenido, text=subtitulo1, font=tkfont.Font(size=10),
                     bg=estilo["fondo"], fg=estilo["texto"]).pack(anchor="w", pady=(4, 0))
        if subtitulo2:
            tk.Label(contenido, text=subtitulo2, font=tkfont.Font(size=10),
                     bg=estilo["fondo"], fg=estilo["texto"]).pack(anchor="w")

        separador = tk.Frame(contenido, bg=estilo["texto"], height=1)
        separador.pack(fill="x", pady=12)

        tk.Label(contenido, text=estado_texto, font=tkfont.Font(size=13, weight="bold"),
                 bg=estilo["fondo"], fg=estilo["texto"]).pack(anchor="w")
        tk.Label(contenido, text=hora, font=tkfont.Font(size=10),
                 bg=estilo["fondo"], fg=estilo["texto"]).pack(anchor="w", pady=(2, 0))

    def _actualizar_resumen(self):
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        resumen = data_access.obtener_resumen_dia(fecha_hoy)
        for clave, lbl in self.etiquetas_resumen.items():
            lbl.config(text=str(resumen.get(clave, 0)))

    # --- Control del lector ---

    def _alternar_lector(self):
        if self.corriendo:
            self._detener_lector()
        else:
            self._iniciar_lector()

    def _iniciar_lector(self):
        self.captura = cv2.VideoCapture(0)
        self.corriendo = True
        self.btn_toggle.config(text="Detener lector")
        self._actualizar_frame()

    def _detener_lector(self):
        self.corriendo = False
        if self.captura is not None:
            self.captura.release()
            self.captura = None
        self.btn_toggle.config(text="Iniciar lector")
        self.lbl_camara.config(image="")

    def _exportar(self):
        import exportar_asistencia
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        exportar_asistencia.exportar(fecha_hoy)

    # --- Bucle de cámara (no bloqueante, vía tkinter .after) ---

    def _actualizar_frame(self):
        if not self.corriendo or self.captura is None:
            return

        ret, frame = self.captura.read()
        if ret:
            frame = cv2.flip(frame, 1)
            ahora = datetime.now()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            for qr in decode(gray):
                codigo = qr.data.decode("utf-8").strip()
                if codigo in self.bloqueo_qr:
                    if (ahora - self.bloqueo_qr[codigo]).total_seconds() < BLOQUEO_SEGUNDOS:
                        continue
                self.bloqueo_qr[codigo] = ahora
                try:
                    self._procesar_codigo(codigo, ahora)
                except Exception as e:
                    print(f"Error procesando código {codigo}: {e}")

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            ancho = self.lbl_camara.winfo_width() or 640
            alto = self.lbl_camara.winfo_height() or 480
            img = img.resize((max(ancho, 1), max(alto, 1)))
            imagen_tk = ImageTk.PhotoImage(image=img)
            self.lbl_camara.imgtk = imagen_tk
            self.lbl_camara.config(image=imagen_tk)

        self.after(30, self._actualizar_frame)

    # --- Lógica de negocio (idéntica a leer_qr.py) ---

    def _procesar_codigo(self, codigo, ahora):
        estudiante = data_access.obtener_estudiante(codigo)
        if estudiante is None:
            fecha = ahora.strftime("%Y-%m-%d")
            hora = ahora.strftime("%H:%M:%S")
            data_access.registrar_intento_desconocido(codigo, fecha, hora)
            self._actualizar_tarjeta("QR no reconocido", "", "", "No reconocido", hora, "error")
            _reproducir_tono(config.TONO_ERROR_HZ, config.TONO_ERROR_MS)
            return

        nombre = estudiante["nombres"]
        grado = estudiante["grado"]
        codigo_personal = estudiante["codigo_personal"]
        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")
        hora_actual = ahora.time()

        registro = data_access.obtener_registro(codigo, fecha)
        if registro is None:
            self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                      "Error de registro", hora, "error")
            _reproducir_tono(config.TONO_ERROR_HZ, config.TONO_ERROR_MS)
            return

        if registro["hora_entrada"] is None:
            estado = "TARDE" if hora_actual > data_access.HORA_LIMITE_ENTRADA else "PRESENTE"
            data_access.registrar_entrada(codigo, fecha, hora, estado)
            nivel = "aviso" if estado == "TARDE" else "exito"
            self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                      estado.capitalize(), hora, nivel)
            if nivel == "exito":
                _reproducir_tono(config.TONO_EXITO_HZ, config.TONO_EXITO_MS)
            else:
                _reproducir_tono(config.TONO_ERROR_HZ, config.TONO_ERROR_MS)
            self._actualizar_resumen()
            return

        if registro["hora_salida"] is not None:
            self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                      "Ya tiene entrada y salida", hora, "aviso")
            return

        if hora_actual > data_access.HORA_LIMITE_SALIDA:
            self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                      "No puede marcar salida", hora, "error")
            _reproducir_tono(config.TONO_ERROR_HZ, config.TONO_ERROR_MS)
            return

        hora_entrada_dt = datetime.combine(
            ahora.date(),
            datetime.strptime(registro["hora_entrada"], "%H:%M:%S").time()
        )
        if (ahora - hora_entrada_dt) < timedelta(minutes=config.MINUTOS_ESPERA_SALIDA):
            self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                      f"Esperar {config.MINUTOS_ESPERA_SALIDA} min", hora, "aviso")
            return

        data_access.registrar_salida(codigo, fecha, hora)
        self._actualizar_tarjeta(nombre, grado, f"Código {codigo_personal}",
                                  "Salida registrada", hora, "exito")
        _reproducir_tono(config.TONO_EXITO_HZ, config.TONO_EXITO_MS)
        self._actualizar_resumen()


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Asistencia QR")
        self.geometry("980x640")
        self.configure(bg=COLOR_FONDO)
        self._mostrar_pantalla_pin()

    def _mostrar_pantalla_pin(self):
        for hijo in self.winfo_children():
            hijo.destroy()
        pantalla = PantallaPin(self, al_desbloquear=self._mostrar_pantalla_principal)
        pantalla.pack(fill="both", expand=True)

    def _mostrar_pantalla_principal(self):
        for hijo in self.winfo_children():
            hijo.destroy()
        pantalla = PantallaPrincipal(self)
        pantalla.pack(fill="both", expand=True)


def main():
    data_access.inicializar_db()
    app = Aplicacion()
    app.mainloop()


if __name__ == "__main__":
    main()
