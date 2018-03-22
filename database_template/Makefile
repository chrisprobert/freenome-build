SHELL = /bin/bash
IMAGE_NAME = skeleton
PORT = 3333
CONTAINER_NAME = $(IMAGE_NAME)_$(PORT)

.PHONY: start-test-db build stop-db start-db setup-db run-migrations connect

start-test-db: build start-db setup-db run-migrations
	@echo $(IMAGE_NAME) is available via: psql -U postgres -h localhost -p $(PORT)

build:
	docker build --rm -t $(IMAGE_NAME):latest .

stop-db:
	-docker kill $(CONTAINER_NAME)
	-docker rm -f $(CONTAINER_NAME)

start-db:
	docker run -d -p $(PORT):5432 --name $(CONTAINER_NAME) $(IMAGE_NAME):latest
	docker exec $(CONTAINER_NAME) /bin/bash -c "for i in {1..10}; do if su postgres -c '/usr/lib/postgresql/9.6/bin/pg_ctl status'; then break; else sleep 2; fi; done"
	for i in {1..10}; do if psql -U postgres -p $(PORT) -h localhost -c "select 1;"; then break; else sleep 2; fi; done

setup-db:
	psql -h localhost -p $(PORT) -U postgres < setup_new_db.sql

run-migrations:
	cd sqitch && sqitch deploy db:pg://postgres@localhost:$(PORT)/$(IMAGE_NAME)

connect:
	psql -h localhost -p $(PORT) -U postgres $(IMAGE_NAME)

reset-db:
	psql -h localhost -p $(PORT) -U postgres < drop.sql
