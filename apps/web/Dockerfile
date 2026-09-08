# Etapa 1: Construcción de la aplicación con Vite y pnpm
FROM node:20-alpine AS builder
WORKDIR /app

# Habilitar corepack para usar pnpm de forma nativa en Node 20
RUN corepack enable

# Copiar archivos de configuración y dependencias
COPY package.json pnpm-lock.yaml ./

# Instalar dependencias con pnpm
RUN pnpm install

# Copiar el resto del código y empaquetar
COPY . .
RUN pnpm build

# Etapa 2: Servidor web de producción
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
