import pandas as pd
import qrcode
import os
import re

os.makedirs("qr", exist_ok=True)

df_basicos = pd.read_excel("")
df_basicos.columns = df_basicos.columns.str.strip()
df_basicos.columns = df_basicos.columns.str.strip()

df_diversificado = pd.read_excel("")
df_diversificado.columns = df_diversificado.columns.str.strip()
df_diversificado = df_diversificado[["Código Personal","Nombres","Apellidos","CARRERA"]]

df_diversificado = df_diversificado.rename(columns={"CARRERA": "GRADO"})

df = pd.concat([df_basicos, df_diversificado], ignore_index=True)

codigos_generados = set()
registro_qr = []

for _, fila in df.iterrows():

    codigo_raw = fila["Código Personal"]

    if pd.isna(codigo_raw):
        continue

    codigo = str(codigo_raw).strip()

    if codigo in codigos_generados:
        print(f"Código duplicado ignorado: {codigo}")
        continue

    codigos_generados.add(codigo)

    nombre = str(fila["Nombres"]).strip().replace(" ", "_")
    apellido = str(fila["Apellidos"]).strip().replace(" ", "_")
    grado = str(fila["GRADO"]).strip()
    grado = re.sub(r'[<>:"/\\|?*]', '', grado)
    grado = grado.replace(" ", "_")

    carpeta_grado = f"qr/{grado}"
    os.makedirs(carpeta_grado, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(codigo)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    archivo_qr = f"{codigo}_{apellido}_{nombre}.jpg"
    img.save(f"{carpeta_grado}/{archivo_qr}", "JPEG")

    print(f"QR generado para {codigo} ({grado})")

    registro_qr.append({
        "Código Personal": codigo,
        "Nombre": nombre,
        "Apellido": apellido,
        "GRADO": grado,
        "Archivo QR": archivo_qr
    })

pd.DataFrame(registro_qr).to_excel("registro_qr.xlsx", index=False)

print("Todos los QR han sido generados.")