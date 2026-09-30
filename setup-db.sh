#!/bin/bash
echo "Vaciando base de pruebas y preparando esquemas..."
docker compose exec -T db psql -U postgres -d aquabloom -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public; CREATE SCHEMA IF NOT EXISTS auth;"

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
