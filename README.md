# AquaBloom Sur

Plataforma científica colaborativa para apoyar el estudio de lagos del sur de Chile. AquaBloom Sur reúne una interfaz web, una API y un catálogo de lagos y estaciones para organizar información y flujos de trabajo relacionados con la estimación de clorofila-a mediante teledetección (Sentinel-2) y modelos de aprendizaje automático.

Este repositorio es un monorepo: el frontend y el backend se desarrollan y ejecutan desde sus propias carpetas, y comparten los contratos de la API y la configuración de los servicios de Supabase.

## Stack Tecnológico

| Área | Tecnologías |
| --- | --- |
| Frontend | React 19, TypeScript 6, Vite 8, React Router, pnpm |
| Autenticación | Supabase Auth y `@supabase/supabase-js` |
| Backend | Python 3.11+, FastAPI, Pydantic Settings, Uvicorn |
| Pruebas y calidad | pytest, Ruff, ESLint, TypeScript |
| Datos | Supabase y PostgreSQL; migraciones SQL en `database/migrations/` |
| Contenedores | Docker y Docker Compose (configuración en `compose.yaml`) |

## Requisitos Previos

- Git para clonar el repositorio y trabajar con ramas.
- Node.js 20 o superior y npm. Vite necesita una versión reciente de Node 20; se recomienda mantener Node actualizado dentro de una versión LTS compatible.
- pnpm. Se puede instalar con `npm install --global pnpm` o habilitar con Corepack si está disponible en la instalación de Node.
- Python 3.11 o superior y `pip`. La imagen de la API también está basada en Python 3.11.
- Un proyecto de Supabase con URL y claves de API válidas. El navegador usa la clave anon/publicable; la API requiere una clave de servidor secreta.
- Docker Desktop o Docker Engine con el plugin `docker compose` únicamente si se va a trabajar con contenedores.

Verifica las herramientas antes de comenzar:

```powershell
git --version
node --version
npm --version
pnpm --version
py --version
```

En macOS o Linux, usa `python3 --version` para comprobar Python.

## Instalación y Ejecución Local

Los ejemplos para Windows usan PowerShell. Para macOS/Linux se indican los equivalentes cuando cambia la activación del entorno virtual o la copia de plantillas. Ejecuta los comandos desde la raíz del repositorio, salvo que el bloque indique que ya se cambió de directorio.

### Backend

1. Entra en el backend y crea un entorno virtual:

	```powershell
	cd apps/api
	py -3.11 -m venv .venv
	.\.venv\Scripts\Activate.ps1
	```

	En macOS/Linux, crea y activa el entorno con:

	```bash
	cd apps/api
	python3 -m venv .venv
	source .venv/bin/activate
	```

2. Instala dependencias de ejecución y herramientas de desarrollo. `pytest` y `ruff` se instalan aparte porque no están incluidos en `requirements.txt`:

	```bash
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt
	python -m pip install pytest ruff
	```

3. Crea el archivo de entorno local a partir de la plantilla:

	```powershell
	Copy-Item .env.example .env
	```

	En macOS/Linux:

	```bash
	cp .env.example .env
	```

	Completa `apps/api/.env` con los valores de tu proyecto Supabase:

	| Variable | Uso |
	| --- | --- |
	| `ENVIRONMENT` | Nombre del entorno; por defecto, `development`. |
	| `CORS_ORIGINS` | Orígenes web permitidos, separados por comas. Para Vite local, usa `http://localhost:5173`. |
	| `SUPABASE_URL` | URL del proyecto Supabase. |
	| `SUPABASE_KEY` | Clave de servidor requerida por la API. Mantenla secreta y nunca la incluyas en el frontend. |

	La API lee este archivo desde su directorio de trabajo. Por eso, ejecuta Uvicorn y pytest desde `apps/api`.

4. Inicia la API en modo de desarrollo:

	```bash
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
	```

	La raíz responde en `http://localhost:8000/`, el estado del servicio está en `http://localhost:8000/api/v1/health` y la documentación OpenAPI de FastAPI en `http://localhost:8000/docs`.

5. En otra terminal, desde `apps/api`, valida pruebas y estilo:

	```bash
	pytest
	ruff check .
	```

### Frontend

1. Abre otra terminal en la raíz del repositorio y entra en la aplicación web:

	```powershell
	cd apps/web
	```

2. Instala las dependencias usando el lockfile de pnpm:

	```bash
	pnpm install --frozen-lockfile
	```

3. Crea el archivo de entorno local:

	```powershell
	Copy-Item .env.example .env
	```

	En macOS/Linux:

	```bash
	cp .env.example .env
	```

	Completa `apps/web/.env` con estas variables:

	| Variable | Uso |
	| --- | --- |
	| `VITE_SUPABASE_URL` | URL del mismo proyecto Supabase configurado para la API. |
	| `VITE_SUPABASE_ANON_KEY` | Clave anon/publicable de Supabase, apta para el cliente según las políticas RLS del proyecto. Nunca pongas aquí una clave de servicio. |
	| `VITE_API_URL` | URL base de la API. Para el arranque local descrito aquí: `http://localhost:8000/api/v1`. Si se omite, el cliente web usa esa misma URL por defecto. |

	Las variables con prefijo `VITE_` se incorporan al bundle del navegador; no guardes secretos en ellas. Configura también en Supabase los proveedores de autenticación y las URL de redirección que use el entorno de desarrollo.

4. Inicia Vite:

	```bash
	pnpm dev
	```

	Abre la URL que muestra Vite, normalmente `http://localhost:5173`. Mantén la API ejecutándose en la otra terminal para que funcionen las solicitudes al backend.

5. Desde `apps/web`, ejecuta las comprobaciones de frontend:

	```bash
	pnpm lint
	pnpm build
	```

### Lista de Verificación de Ejecución

- [ ] Node.js, pnpm, Python y Git están instalados; sus comandos de versión terminan correctamente.
- [ ] Existe `apps/api/.venv` y el entorno virtual está activo en la terminal del backend.
- [ ] Las dependencias de `apps/api/requirements.txt`, pytest y Ruff están instaladas.
- [ ] `apps/api/.env` contiene `SUPABASE_URL` y `SUPABASE_KEY` válidos, además de `CORS_ORIGINS=http://localhost:5173`.
- [ ] `pytest` y `ruff check .` terminan correctamente ejecutados desde `apps/api`.
- [ ] Uvicorn está escuchando en `http://localhost:8000` y `/api/v1/health` devuelve una respuesta.
- [ ] `apps/web/.env` contiene las credenciales de cliente `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`.
- [ ] `VITE_API_URL` apunta a `http://localhost:8000/api/v1` (o se deja sin definir para usar el valor predeterminado del cliente).
- [ ] `pnpm install --frozen-lockfile`, `pnpm lint` y `pnpm build` terminan correctamente ejecutados desde `apps/web`.
- [ ] Vite sirve la aplicación en `http://localhost:5173` y puede comunicarse con la API y Supabase.
- [ ] No se han añadido archivos `.env`, claves, tokens ni otros secretos al control de versiones.

## Scripts y Comandos Disponibles

Los comandos deben ejecutarse desde el directorio de la aplicación correspondiente. El monorepo no define scripts en la raíz.

### Frontend (`apps/web`)

| Comando | Descripción |
| --- | --- |
| `pnpm dev` | Inicia el servidor de desarrollo de Vite con recarga en caliente. |
| `pnpm lint` | Ejecuta ESLint sobre la aplicación web. |
| `pnpm build` | Comprueba los proyectos TypeScript y genera la versión de producción en `dist/`. |
| `pnpm preview` | Sirve localmente el último build; ejecuta antes `pnpm build`. |
| `pnpm format` | Formatea archivos de `src/` con Prettier y modifica esos archivos. |

### Backend (`apps/api`)

| Comando | Descripción |
| --- | --- |
| `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` | Inicia FastAPI en modo de desarrollo. |
| `pytest` | Descubre y ejecuta las pruebas en `tests/`. |
| `ruff check .` | Busca problemas de estilo y errores detectables por Ruff en la API y sus pruebas. |

`pytest` y `ruff` son dependencias de desarrollo y deben instalarse explícitamente en el entorno virtual. No existe actualmente un archivo `pyproject.toml` que declare scripts o configuración compartida de Ruff.

## Estructura del Proyecto

```text
aquabloom-sur/
├── apps/
│   ├── api/                    # FastAPI, configuración y pruebas pytest
│   │   ├── app/                # Rutas, servicios, permisos y acceso a datos
│   │   ├── catalog/            # Esquemas de aplicación del catálogo
│   │   ├── tests/              # Pruebas automatizadas del backend
│   │   ├── requirements.txt    # Dependencias Python de ejecución
│   │   └── Dockerfile
│   └── web/                    # React, Vite y TypeScript
│       ├── src/
│       │   ├── components/     # Componentes compartidos
│       │   ├── layouts/        # Estructuras públicas y privadas
│       │   ├── pages/          # Vistas de la aplicación
│       │   ├── services/       # Clientes de API y Supabase
│       │   └── types/          # Tipos compartidos del frontend
│       ├── package.json        # Scripts y dependencias de la web
│       ├── pnpm-lock.yaml      # Versiones bloqueadas de pnpm
│       └── Dockerfile
├── database/
│   ├── migrations/             # Migraciones SQL numeradas
│   └── seeds/                  # Datos iniciales
├── docs/                       # Documentación del proyecto
├── .env.example                # Variables de ejemplo para Compose
├── compose.yaml                # Servicios de Docker Compose
└── README.md
```

## Configuración de Datos y Supabase

La autenticación del cliente web usa Supabase Auth. La API valida y procesa las solicitudes del servicio y expone rutas de autenticación, organizaciones, lagos y estaciones. La API requiere las variables `SUPABASE_URL` y `SUPABASE_KEY` al iniciar; la clave de servicio solo debe existir en el entorno del backend y no se debe publicar ni enviar al repositorio.

Las migraciones SQL están numeradas en `database/migrations/` y las semillas en `database/seeds/`. Aplícalas al proyecto de base de datos de desarrollo en orden cuando corresponda; no hay en este repositorio un comando automático de migración integrado en el arranque local.

El archivo `compose.yaml` define servicios de API, web y PostGIS. Su configuración de variables todavía no coincide completamente con el backend: Compose entrega `SUPABASE_ANON_KEY`, mientras `apps/api/app/config.py` exige `SUPABASE_KEY`. Por este motivo, usa los pasos locales de esta guía como ruta de desarrollo verificada y no asumas que `docker compose up` iniciará correctamente la API sin ajustar primero esa configuración.

## Guía de Contribución

1. Actualiza `main` y crea una rama por cada tarea. Usa el identificador de ticket y un nombre breve en minúsculas separado por guiones:

	```text
	feat/S2-XXX-nombre-tarea
	```

	Ejemplo: `feat/S2-093-completar-readme`. Para otros tipos de cambio, conserva el mismo formato y usa un prefijo que describa el trabajo, por ejemplo `fix/`, `docs/` o `chore/`.

2. Mantén los cambios enfocados y sigue el estilo del área que modificas. No incluyas archivos `.env`, credenciales ni artefactos generados como `node_modules/`, `.venv/` o `dist/`.

3. Escribe mensajes de commit semánticos con el formato `tipo(área): resumen` y un resumen breve en modo imperativo. Ejemplos:

	```text
	feat(api): agrega filtro por organización
	fix(web): corrige redirección al iniciar sesión
	docs: documenta el arranque local
	test(api): cubre validación de permisos
	```

4. Antes de abrir el Pull Request, ejecuta las comprobaciones relevantes para los archivos modificados:

	```bash
	# Desde apps/api
	pytest
	ruff check .

	# Desde apps/web
	pnpm lint
	pnpm build
	```

5. Abre un Pull Request hacia `main`. Describe el objetivo y los cambios, enlaza el ticket, indica las pruebas ejecutadas y anota cualquier configuración, migración o variable de entorno nueva. Para cambios visuales, añade capturas cuando ayuden a revisar el resultado. Atiende los comentarios de revisión y espera las aprobaciones y verificaciones requeridas antes de integrar.

## Configuración y Ejecución del Entorno Docker (S2-089)

Para levantar el entorno de desarrollo local con Docker Compose y evitar errores de validación o dependencias faltantes (`shapely`, módulos del backend), sigue estos pasos:

### 1. Configuración del archivo `.env`
Asegúrate de que tu archivo `.env` en la raíz contenga todas las variables requeridas (tanto de PostgreSQL como de Supabase):

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu_contrasena_segura_aqui
POSTGRES_DB=aquabloom
VITE_API_URL=http://localhost:5000/api/v1
SUPABASE_URL=http://tu-url-de-supabase
SUPABASE_ANON_KEY=tu_clave_anonima_aqui
SUPABASE_KEY=tu_clave_secreta_aqui
SUPABASE_JWT_SECRET=tu_jwt_secret_aqui
