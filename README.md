# talentKru-server



## Running postgreSql on docker.

``\> docker run -d \
  --name local-vector-db \
  -e POSTGRES_PASSWORD=<pg_admin_password> \
  -e POSTGRES_DB=krudb \
  -p 5432:5432 \
  -v krudb_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg17

### stop docker
/> docker stop local-vector-db

### remove docker image
/> docker rm local-vector-db

# Running pgadmin utility
 ``\> docker run -p 8080:80 \
-e 'PGADMIN_DEFAULT_EMAIL=snair33@gmail.com' \
-e 'PGADMIN_DEFAULT_PASSWORD=<pg_admin_password>' \
-d dpage/pgadmin4``

### Adding local postgres database to pgadmin
Connection params
 * Host name/address: localhost (or host.docker.internal if pgAdmin is also running in Docker)
* Port: 5432
* Maintenance database: postgres
* Username: postgres
* Password: <admin_password>
* Service: (Leave blank)


## Connecting to Postgres from your Terminal (Docker)
If you don't have a GUI open and just want to do this quickly from your Mac terminal, you can jump directly into your running container and execute the SQL commands.

1. Enter the PostgreSQL command line inside your container:


  ```bash
   docker exec -it local-vector-db psql -U postgres -d krudb
  (Your terminal prompt will change to krudb=#) 
  ```

2. Run the creation commands:

```SQL
  CREATE USER kru_server WITH PASSWORD 'kru2026';
  GRANT ALL PRIVILEGES ON DATABASE krudb TO kru_server;
  GRANT ALL PRIVILEGES ON SCHEMA public TO kru_server;
  ```

3. Exit the database prompt:
```
SQL
\q
```