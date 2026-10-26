# documentation-mcp

Servidor MCP local para gestionar y consultar documentación técnica en archivos `.md` y `.txt` dentro de una carpeta permitida.

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
- `search_all_documentation(query: str)`
- `ask_documentation(question: str, project: str | None = None)`
- `create_project(project: str, initial_document: str | None = None, content: str = "", overwrite_document: bool = False)`
- `create_document(project: str, document: str, content: str = "", overwrite: bool = False)`
- `import_document(project: str, source_path: str, document: str | None = None, overwrite: bool = False)`
- `edit_document(project: str, document: str, content: str, mode: "append" | "replace")`
- `delete_document(project: str, document: str)`
- `delete_project(project: str)`

## Operaciones de escritura

Estas herramientas permiten crear, modificar y eliminar contenido desde el MCP sin hacerlo manualmente en el disco:

- `create_project(...)` crea la carpeta del proyecto y, si se indica, crea también un archivo inicial dentro.
- `create_document(...)` crea un archivo nuevo dentro de un proyecto existente.
- `import_document(...)` copia un archivo `.md` o `.txt` ya existente en el equipo al proyecto destino.
- `edit_document(...)` agrega texto al final con `mode="append"` o reemplaza todo el contenido con `mode="replace"`.
- `delete_document(...)` elimina un archivo.
- `delete_project(...)` elimina el proyecto completo junto con su contenido.

Si no indicas extensión al crear un archivo, el servidor usa `.md` por defecto.

## Cargar archivos adjuntos

Si el frontend ya guarda el archivo adjunto en disco, puedes usar `import_document(...)` pasando la ruta local temporal del archivo:

- `project`: proyecto destino dentro de `DOCUMENTATION_ROOT`.
- `source_path`: ruta local del archivo adjunto que subió el usuario.
- `document`: nombre destino opcional dentro del proyecto. Si no se envía, se conserva el nombre original.
- `overwrite`: permite reemplazar un documento existente.

El MCP solo importa archivos `.md` y `.txt` y mantiene las validaciones de tamaño configuradas.

## Preguntas en lenguaje natural

El problema anterior era que `search_documentation(...)` dependía demasiado de coincidencias literales. Ahora el MCP:

- busca por coincidencia exacta y también por términos relevantes de la pregunta
- tolera variaciones simples como `secret` y `secreto`, o `db` y `database`
- resuelve referencias parciales del proyecto, por ejemplo `oneriver` -> `onersiverschool`
- ordena los resultados por relevancia
- puede buscar en todos los proyectos con `search_all_documentation(...)`
- expone `ask_documentation(...)` para preguntas formuladas de forma natural y devuelve una respuesta final basada en la sección más relevante

Ejemplos:

- `ask_documentation("como cambiar el valor de un secret ya creado")`
- `ask_documentation("como darle acceso a la db a una persona en qa")`
- `ask_documentation("que hago despues de rotar un secreto", project="onersiverschool")`

La respuesta de `ask_documentation(...)` incluye:

- `resolved_project`: el proyecto real detectado aunque se haya enviado un alias parcial.
- `answer`: respuesta final lista para mostrar al usuario.
- `sources`: secciones concretas usadas para construir la respuesta.
- `results`: resultados rankeados completos para depuración o trazabilidad.

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
