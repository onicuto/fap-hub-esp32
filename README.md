# FAP Hub ESP32 — Репозиторий и CI/CD приложений Flipper Zero для ESP32

Автоматизированный каталог и сборочный пайплайн для компиляции приложений Flipper Zero (`.fap`) под архитектуру ESP32-S3 (Xtensa, прошивка [Sor3nt/Flipper-Zero-ESP32-Port](https://github.com/Sor3nt/Flipper-Zero-ESP32-Port)).

---

## 🚀 Возможности

1. **GitHub Actions CI/CD**:
   - Автоматическая компиляция приложений из `apps.yaml` при пуше или ручном запуске.
   - Подтягивание toolchain `xtensa-esp32s3-elf-gcc` (v12.2.0) и заголовочных файлов FreeRTOS / ESP-IDF.
   - Валидация неразрешенных символов (`check_fap_symbols.py`) против таблицы экспорта `firmware_api.c`.
   - Автоматическая публикация собранных `.fap` и `catalog.json` на **GitHub Pages** и в GitHub Releases.

2. **Совместимость с iOS приложением (`qMobile`)**:
   - Предоставляет REST API (`/0/category`, `/1/application`, `/0/application/version/.../build/compatible`), полностью совместимое с официальным Flipper Catalog API.
   - Позволяет устанавливать приложения прямо из вкладки **Hub -> Apps** в `qMobile`.

3. **Локальный FastAPI бэкенд**:
   - Готовый Docker / Docker Compose контейнер для самостоятельного хостинга.

---

## 📁 Структура проекта

```text
fap-hub-esp32/
├── .github/workflows/
│   └── build_apps.yml         # GitHub Actions для компиляции и деплоя на Pages
├── apps.yaml                  # Манифест со списком приложений и репозиториев
├── apps.json                  # JSON-версия манифеста
├── scripts/
│   └── build_apps.py          # Скрипт сборки FAP для ESP32 и генерации каталога
├── tools/
│   ├── fap.ld                 # Скрипт линковщика для ESP32 FAP ELF
│   ├── fap_manifest.py        # Генератор бинарного манифеста .fapmeta (target 32)
│   ├── fap_zeroed_heap.h      # Обнуление кучи furi
│   ├── check_fap_symbols.py   # Проверка совпадения символов с firmware_api.c
│   └── compat/
│       └── strtol.c           # Совместимость со стандартными функциями
├── server/
│   ├── app/
│   │   └── main.py            # FastAPI REST сервер каталога
│   └── requirements.txt
├── dist/                      # Скомпилированные артефакты (fap, icons, catalog.json)
├── Dockerfile
└── docker-compose.yml
```

---

## ➕ Как добавить новое приложение

Откройте `apps.yaml` (или `apps.json`) и добавьте описание вашего приложения:

```yaml
apps:
  - id: my_cool_app
    name: "My Cool App"
    category: tools
    author: mynick
    description: "Описание приложения"
    version: "1.0"
    repository: "https://github.com/author/flipper-app"
    subpath: ""                # подкаталог, если исходники не в корне
    entry_point: "my_cool_app" # имя функции точки входа
    stack_size: 16384          # размер стека
    icon: "icon.png"           # путь к 10x10 или 14x14 иконке
    sources:                   # список C файлов (если не указан, берет все *.c)
      - "main.c"
      - "helpers.c"
    compat_shims:
      - "strtol"               # опциональные шимы совместимости
```

После коммита и пуша в ветку `main`, GitHub Actions автоматически:
1. Склонирует репозиторий приложения.
2. Скомпилирует объектные файлы под Xtensa ESP32-S3 (`target: 32`).
3. Слинкует `app.elf` с таблицей символов прошивки.
4. Внедрит секцию `.fapmeta` с манифестом и иконкой.
5. Проверит отсутствие неразрешенных символов.
6. Выгрузит готовый `my_cool_app.fap` в каталог!

---

## 🛠 Локальная сборка

```bash
# 1. Запуск сборщика FAP приложений
python3 scripts/build_apps.py

# Сборка только одного конкретного приложения:
python3 scripts/build_apps.py --app kota
```

---

## 🐳 Запуск сервера каталога через Docker

```bash
# Собрать и запустить сервер
docker-compose up -d --build

# Проверить статус
curl http://localhost:8000/0/category
```

Сервер будет доступен по адресу `http://<IP_сервера>:8000`.

---

## 📱 Подключение к qMobile (iOS)

В приложении `qMobile` каталог запрашивает данные через REST API (включая `POST /1/application`), поэтому для работы в приложении используется запущенный бэкенд FastAPI:

1. Запустите бэкенд (локально, на VPS или через Docker/Fly.io/Render).
2. В приложении `qMobile` перейдите в **Options -> Catalog Source** (или Custom Catalog URL).
3. Укажите адрес вашего сервера:
   - Например: `http://192.168.1.100:8000` или `https://api.yourdomain.com`
4. Откройте вкладку **Hub -> Apps** — приложение отобразит доступные программы и позволит устанавливать их на ESP32 одним нажатием!

> **Примечание по GitHub Pages:** GitHub Pages используется как бесплатный статический хостинг собранных `.fap` файлов и `catalog.json` (доступен по адресу `https://<username>.github.io/fap-hub-esp32/`). Статический хостинг не обрабатывает `POST`-запросы приложения, поэтому для интерактивного каталога в мобильном приложении используется FastAPI бэкенд.
