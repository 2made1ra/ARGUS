.PHONY: help infra-up infra-down infra-logs infra-ps app-up app-down docker-clean docker-fresh dev worker migrate demo-seed install-ocr uninstall-ocr

help:
	@echo "Хранилища (postgres, redis, qdrant):"
	@echo "  make infra-up      — запустить хранилища"
	@echo "  make infra-down    — остановить хранилища"
	@echo "  make infra-logs    — логи хранилищ"
	@echo "  make infra-ps      — статус контейнеров"
	@echo ""
	@echo "Локальная разработка (бэкенд запускается отдельно):"
	@echo "  make dev           — uvicorn (hot-reload)"
	@echo "  make worker        — celery worker"
	@echo "  make migrate       — применить миграции Alembic"
	@echo "  make demo-seed     — импортировать demo catalog CSV"
	@echo ""
	@echo "Полный стек (docker, профиль app):"
	@echo "  make app-up        — поднять api + celery-worker в docker"
	@echo "  make app-down      — остановить api + celery-worker"
	@echo "  make docker-clean  — удалить контейнеры, volumes и локально собранные образы"
	@echo "  make docker-fresh  — очистить docker-состояние и поднять полный стек заново"
	@echo ""
	@echo "OCR (local Tesseract for the Celery worker):"
	@echo "  make install-ocr   — install Tesseract + rus/eng language data via Homebrew"
	@echo "  make uninstall-ocr — remove Tesseract and language data"

# --- Хранилища ---

infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

infra-ps:
	docker compose ps

# --- Полный стек (docker) ---

app-up:
	docker compose --profile app up -d --build

app-down:
	docker compose --profile app down

docker-clean:
	docker compose --profile app down -v --rmi local --remove-orphans

docker-fresh: docker-clean
	docker compose --profile app up -d --build

# --- Локальная разработка ---

dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && uv run celery -A app.celery_app worker --loglevel=info

migrate:
	cd backend && uv run alembic upgrade head

demo-seed:
	uv run --project backend python -m app.entrypoints.cli.seed_demo_catalog

# --- OCR deps (macOS / Homebrew) ---

TESSDATA_DIR := $(shell brew --prefix)/share/tessdata
TESSDATA_BASE := https://github.com/tesseract-ocr/tessdata_fast/raw/main

install-ocr:
	brew install tesseract
	curl -L $(TESSDATA_BASE)/rus.traineddata -o $(TESSDATA_DIR)/rus.traineddata
	curl -L $(TESSDATA_BASE)/eng.traineddata -o $(TESSDATA_DIR)/eng.traineddata

uninstall-ocr:
	rm -f $(TESSDATA_DIR)/rus.traineddata $(TESSDATA_DIR)/eng.traineddata
	brew uninstall tesseract
