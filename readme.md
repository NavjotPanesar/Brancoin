# Setup
- rename `env.txt.sample` to `env.txt`, and fill in the values
- `docker-compose up --build` from the root folder to spin up the project
- `docker-compose run bot alembic head upgrade` to generate the DB schema

# Migrations
- Create: `docker-compose run migrate revision --autogenerate -m "added tag to league user"`
- Run: `docker-compose run migrate upgrade head`
