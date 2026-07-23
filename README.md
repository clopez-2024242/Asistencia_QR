# Asistencia QR

Sistema de control de asistencia escolar mediante códigos QR, con lectura por cámara, persistencia en base de datos, y una interfaz gráfica de escritorio para el operador.

## Problema que resuelve

El control de asistencia en el colegio se hacía de forma manual. Este sistema genera un QR único por estudiante (a partir de su código personal) y permite registrar entradas y salidas escaneándolo con una cámara, aplicando automáticamente las reglas del colegio: tolerancia de tardanza, tiempo mínimo entre entrada y salida, y hora límite para marcar salida.

## Características

- **Generación de QR** por estudiante, organizados en carpetas por grado.
- **Lectura por cámara** con reconocimiento en tiempo real (OpenCV + pyzbar).
- **Persistencia en SQLite** en vez de Excel: evita la corrupción de datos por reescritura completa del archivo en cada escaneo.
- **Capa de acceso a datos separada** (`data_access.py`): toda la lógica de base de datos vive en un solo lugar, pensada para poder migrar en el futuro a una arquitectura cliente-servidor sin reescribir el resto del sistema.
- **Manejo de errores**: un escaneo problemático no interrumpe el funcionamiento del lector.
- **Registro de intentos de QR no reconocido**, con su propia hoja en el reporte exportado.
- **Control de acceso por PIN** (hash SHA-256, nunca en texto plano), con registro de accesos y purga automática de ese registro después de un tiempo configurable.
- **Configuración externa** (`config.ini`): rutas, horarios, tonos de alerta y parámetros de seguridad, todo editable sin tocar código.
- **Interfaz gráfica** (`panel_gui.py`): pantalla de PIN + panel con cámara, controles, tarjeta del último escaneo (con color según el resultado) y resumen del día en vivo.
- **Exportación a Excel bajo demanda**, con una hoja por grado, en el mismo formato que se entrega al colegio.

## Cómo correrlo

1. Instalar dependencias:
   ```
   pip install pandas openpyxl qrcode opencv-python pyzbar Pillow
   ```
2. Sincronizar estudiantes desde los Excel de origen del colegio:
   ```
   python importar_estudiantes.py
   ```
3. Generar los QR (uno por estudiante, en `qr/<grado>/`):
   ```
   python generar_qr.py
   ```
4. Abrir la aplicación:
   ```
   python panel_gui.py
   ```
5. Exportar la asistencia del día cuando se necesite:
   ```
   python exportar_asistencia.py [fecha opcional, formato YYYY-MM-DD]
   ```

En el primer arranque se crea automáticamente `config.ini` con valores por defecto (ver `config.ini.example` como referencia).

## ⚠️ Antes de usarlo en producción

- El **PIN por defecto es `1234`**. Cámbialo de inmediato con:
  ```
  python cambiar_pin.py
  ```
- Los archivos `SIRE*.xlsx`, `asistencia.db`, la carpeta `qr/` y la carpeta `asistencia/` contienen datos reales de estudiantes y están excluidos del repositorio vía `.gitignore` — no los subas manualmente.

## Compilar a ejecutable (Windows)

```
pyinstaller panel_gui.spec
```

El `.exe` resultante (`dist/AsistenciaQR.exe`) queda sin ventana de consola, ya que el PIN se ingresa desde la propia interfaz.

## Estructura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `config.py` | Carga/crea `config.ini`, expone rutas, horarios y parámetros de seguridad |
| `data_access.py` | Única capa que toca la base de datos (SQLite) |
| `auth.py` | Verificación de PIN |
| `importar_estudiantes.py` | Sincroniza estudiantes desde los Excel de origen |
| `generar_qr.py` | Genera las imágenes QR desde la base de datos |
| `panel_gui.py` | Interfaz gráfica (pantalla de PIN + panel principal) |
| `leer_qr.py` | Versión de consola del lector (alternativa a `panel_gui.py`) |
| `cambiar_pin.py` | Cambia el PIN de acceso |
| `exportar_asistencia.py` | Exporta la asistencia del día a Excel |

## Próximos pasos posibles

- Arquitectura cliente-servidor si se necesita correr en varias máquinas a la vez.
- Panel de administración más completo (búsqueda de estudiante, historial).
- Preparación para multi-colegio si el proyecto se convierte en producto.
