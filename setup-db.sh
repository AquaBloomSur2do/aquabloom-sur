#!/bin/bash
echo "Vaciando base de pruebas y preparando esquemas..."
docker compose exec -T db psql -U postgres -d aquabloom -c "DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA public; CREATE SCHEMA auth; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;"

echo "Construyendo tablas..."
for file in database/migrations/*.sql; do 
    if [ -f "$file" ]; then
        echo "Ejecutando: $file"
        docker compose exec -T db psql -U postgres -d aquabloom -f - < "$file"
    fi
done

echo "Sembrando roles y lagos..."
docker compose exec -T db psql -U postgres -d aquabloom -f - < "database/seeds/00_roles.sql"
docker compose exec -T db psql -U postgres -d aquabloom -f - < "database/seeds/01_lakes.sql"

echo "¡Base de datos local lista y sembrada!"
