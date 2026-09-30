# documentation-mcp

Servidor MCP local, de solo lectura, para gestionar y consultar documentación técnica en archivos `.md` y `.txt` dentro de una carpeta permitida.

## Requisitos

- Python 3.11+

## Crear entorno virtual

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Instalar dependencias

```bash
pip install -r requirements.txt
```

`requirements.txt` incluye `mcp[cli]`, que habilita el comando `mcp` para usar `mcp dev`.

## Configurar carpeta de documentación

La variable opcional `DOCUMENTATION_ROOT` define la carpeta raíz permitida. Si no existe, se usa por defecto `./documentacion` relativa al proyecto.

### PowerShell

```powershell
$env:DOCUMENTATION_ROOT="C:\Users\Jonathan\documentacion"
```

### Bash

```bash
export DOCUMENTATION_ROOT="$HOME/documentacion"
```

## Ejecutar localmente

Puedes ejecutar el servidor directamente:

```bash
python server.py
```

## Probar con MCP Inspector

Con el SDK MCP actual, usa:

```bash
mcp dev server.py
```

Si el comando no está disponible en tu entorno, asegúrate de tener activo el entorno virtual y reinstalar `mcp`:

```bash
pip install -r requirements.txt
```

## Herramientas MCP incluidas

- `list_projects()`
- `list_documents(project: str)`
- `read_document(project: str, document: str)`
- `search_documentation(project: str, query: str)`

## Seguridad

- Todo acceso usa validación estricta de path.
- Se bloquea acceso fuera de `DOCUMENTATION_ROOT`.
- Se bloquean intentos de path traversal (`../`, rutas absolutas externas, etc.).
- Solo se aceptan extensiones `.md` y `.txt`.
- Límite de lectura por documento: 2 MB (configurable por `MAX_DOCUMENT_BYTES`).

## Ejecutar pruebas

```bash
pytest -q
```
