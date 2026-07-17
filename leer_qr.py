import cv2
from pyzbar.pyzbar import decode
import pandas as pd
from datetime import datetime, timedelta, time
import os

os.makedirs("asistencia", exist_ok=True)

#Horas Limite
HORA_LIMITE_ENTRADA = time(13, 0, 0)   # 01:00 PM
HORA_LIMITE_SALIDA = time(18, 30, 0)   # 06:00 PM

#Creacion de archivos
archivo_estudiantes_diversificado = ""
archivo_estudiantes_basicos = ""

#Datos del QR
df_basicos = pd.read_excel(archivo_estudiantes_basicos)
df_basicos.columns = df_basicos.columns.str.strip()
df_basicos = df_basicos[[
    "Código Personal",
    "Nombres",
    "Apellidos",
    "GRADO"
]]

df_diversificado = pd.read_excel(archivo_estudiantes_diversificado)
df_diversificado.columns = df_diversificado.columns.str.strip()
df_diversificado = df_diversificado[[
    "Código Personal",
    "Nombres",
    "Apellidos",
    "CARRERA"
]]

df_diversificado = df_diversificado.rename(columns={"CARRERA": "GRADO"})

df_estudiantes = pd.concat([df_basicos, df_diversificado], ignore_index=True)

archivo_asistencia = f"asistencia/asistencia_{datetime.now().strftime('%Y_%m_%d')}.xlsx"

if os.path.exists(archivo_asistencia):
    df_asistencia = pd.read_excel(archivo_asistencia)
    df_asistencia["hora_entrada"] = df_asistencia["hora_entrada"].astype("object")
    df_asistencia["hora_salida"] = df_asistencia["hora_salida"].astype("object")
else:
    df_asistencia = pd.DataFrame(columns=[
        "Código Personal",
        "Nombres",
        "Apellidos",
        "GRADO",
        "fecha",
        "hora_entrada",
        "hora_salida",
        "estado",
        "justificado"
    ])
    df_asistencia.to_excel(archivo_asistencia, index=False)
    
fecha_hoy = datetime.now().strftime("%Y-%m-%d")
for _, fila in df_estudiantes.iterrows():

    codigo = str(fila["Código Personal"]).strip()
    nombre = fila["Nombres"]
    apellido = fila["Apellidos"]
    grado = fila["GRADO"]

    registro = df_asistencia[
        (df_asistencia["Código Personal"].astype(str) == codigo) &
        (df_asistencia["fecha"] == fecha_hoy)
    ]
    
    if registro.empty:
        nuevo = pd.DataFrame([[
            codigo,
            nombre,
            apellido,
            grado,
            fecha_hoy,
            None,
            None,
            "AUSENTE",
            "NO"
        ]], columns=df_asistencia.columns)

        df_asistencia = pd.concat([df_asistencia, nuevo], ignore_index=True)

# Guardar
df_asistencia.to_excel(archivo_asistencia, index=False)

#Evitar Leer QR durante 15 segundos
bloqueo_qr = {}
BLOQUEO_SEGUNDOS = 15

#Visuales
mensaje = ""
color_mensaje = (255, 255, 255)
mensaje_hasta = datetime.min

#Iniciar Camara
print("Iniciando cámara. Preciones ESC para salir.")
cap = cv2.VideoCapture(0)

cv2.namedWindow("Escaneo QR", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Escaneo QR", 1280, 720)

#Leer Excel
df_asistencia = pd.read_excel(archivo_asistencia)
df_asistencia["hora_entrada"] = df_asistencia["hora_entrada"].astype("object")
df_asistencia["hora_salida"] = df_asistencia["hora_salida"].astype("object")

#Lectura QR Camara
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)

    ahora = datetime.now()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for qr in decode(gray):
        codigo = qr.data.decode("utf-8").strip()

        #QR de estudiante bloqueado
        if codigo in bloqueo_qr:
            if (ahora - bloqueo_qr[codigo]).total_seconds() < BLOQUEO_SEGUNDOS:
                continue
            else:
                del bloqueo_qr[codigo]

        bloqueo_qr[codigo] = ahora

        #Ver si estudiante existe
        fila = df_estudiantes[
            df_estudiantes["Código Personal"].astype(str) == str(codigo)
        ]

        if fila.empty:
            nombre = "DESCONOCIDO"
            apellido = "DESCONOCIDO"
            grado = "SIN_GRADO"
        else:
            nombre = f"{fila['Nombres'].values[0]}"
            apellido = f"{fila['Apellidos'].values[0]}"
            grado = str(fila["GRADO"].values[0]).strip()

        #Estudiante Encontrado
        print(f"Detectado: {nombre} ({codigo})")

        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")
        hora_actual = ahora.time()

        registro_hoy = df_asistencia[
            (df_asistencia["Código Personal"].astype(str) == codigo) &
            (df_asistencia["fecha"] == fecha)
        ]

        #---------------------Area de Entrada---------------------
        if registro_hoy.empty:
            print(f"No se encontró registro para {nombre}")
            continue
        idx = registro_hoy.index[0]
        if pd.isna(df_asistencia.at[idx, "hora_entrada"]):
            if hora_actual > HORA_LIMITE_ENTRADA:
                estado = "TARDE"
                hora_entrada = hora
                justificado = False
            else:
                estado = "PRESENTE"
                hora_entrada = hora
                justificado = False

            df_asistencia.at[idx, "hora_entrada"] = hora
            df_asistencia.at[idx, "estado"] = estado

            with pd.ExcelWriter(archivo_asistencia, engine="openpyxl") as writer:
                for grado_excel in df_asistencia["GRADO"].unique():
                    df_grado = df_asistencia[df_asistencia["GRADO"] == grado_excel]
                    df_grado.to_excel(writer, sheet_name=str(grado_excel)[:31], index=False)

            mensaje = f"{nombre} - {estado}" #Mensaje
            color_mensaje = (0, 255, 0)  #Color
            mensaje_hasta = datetime.now() + timedelta(seconds=2) #Tiempo
        #---------------------Area de Salida---------------------
        else:
            if registro_hoy.empty:
                print(f"No se encontró registro para {nombre}")
                continue

            idx = registro_hoy.index[0]

            if pd.notna(df_asistencia.at[idx, "hora_salida"]):
                mensaje = f"{nombre} - ya tiene entrada y salida hoy" #Mensaje
                color_mensaje = (0, 255, 255)  #Color
                mensaje_hasta = datetime.now() + timedelta(seconds=2) #Tiempo
            else:
                hora_entrada_str = df_asistencia.at[idx, "hora_entrada"]

                # Si fue AUSENTE no puede salir
                if pd.isna(hora_entrada_str):
                    print(f"{nombre} fue marcado AUSENTE")

                else:
                    hora_entrada_dt = datetime.combine(
                        ahora.date(),
                        datetime.strptime(hora_entrada_str, "%H:%M:%S").time()
                    )
                    diferencia = ahora - hora_entrada_dt

                    if hora_actual > HORA_LIMITE_SALIDA:
                        print(f"{nombre} no puede marcar salida después de la 6:30 PM")

                        mensaje = f"{nombre} - no puede marcar salida después de la 6:30 PM" #Mensaje
                        color_mensaje = (0, 0, 255)  #Color
                        mensaje_hasta = datetime.now() + timedelta(seconds=2) #Tiempo

                    elif diferencia >= timedelta(minutes=30):
                        df_asistencia.at[idx, "hora_salida"] = hora
                        with pd.ExcelWriter(archivo_asistencia, engine="openpyxl") as writer:
                            for grado_excel in df_asistencia["GRADO"].unique():
                                df_grado = df_asistencia[df_asistencia["GRADO"] == grado_excel]
                                df_grado.to_excel(writer, sheet_name=str(grado_excel)[:31], index=False)

                        mensaje = f"{nombre} - SALIDA REGISTRADA" #Mensaje
                        color_mensaje = (0, 255, 0)  #Color
                        mensaje_hasta = datetime.now() + timedelta(seconds=2) #Tiempo

                    else:
                        print("Debe esperar 30 minutos para marcar salida")


    if datetime.now() < mensaje_hasta:
        cv2.putText(
            frame,
            mensaje,
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color_mensaje,
            2
        )

    cv2.imshow("Escaneo QR", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()