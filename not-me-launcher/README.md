# ErrorLabs Playtest

Windows-лаунчер закрытого тестирования ErrorLabs. Лаунчер получает сборки игры
Not Me из приватного GitHub Release, устанавливает их через staging и запускает
игру. Сам ErrorLabs Playtest обновляется из публичных Releases репозитория
`ErrorsLab32/ErrorLauncher` через отдельный `ErrorLabsUpdater.exe`.

## Требования

- Windows 10/11
- Python 3.12

## Установка и запуск

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Настройка GitHub

1. Скопируйте `.env.example` в `.env` (локальный `.env` уже создан при разработке).
2. Добавьте в `.env` токен, имеющий доступ только к нужному приватному репозиторию:

```dotenv
GITHUB_REPOSITORY=ErrorsLab32/Not-ME
GITHUB_TOKEN=ваш_токен
```

Токен не хранится в исходном коде и `.env` исключён из Git. Лаунчер всегда
запрашивает `releases/latest`; фиксированный тег не используется. Для загрузки
приватных файлов используются API URL объектов из массива `assets`.

При первой загрузке лаунчер предлагает выбрать существующую папку установки
Not Me. Новые файлы релиза сохраняются в:

```text
<папка установки>/.errorlabs-playtest/downloads/<tag_name>/
```

Выбранный путь хранится в `installation.json` внутри системного каталога данных
приложения (`QStandardPaths.AppDataLocation`) и доступен на экране настроек.
Старый проектный каталог `downloads/` не переносится и не удаляется
автоматически. Установщики 7-Zip и автоматически созданные архивы исходного
кода не скачиваются.

Проверка обновлений самого лаунчера не использует токен игры и выполняется через
публичный GitHub API. Production-релиз лаунчера должен содержать ровно подготовленные
Для первой установки с сайта скачивайте только
`ErrorLabsPlaytestSetup-<version>.exe`. Файлы
`ErrorLabsPlaytest-<version>-win-x64.zip` и `launcher-manifest.json` предназначены
только для автоматического обновления уже установленного лаунчера.

## Проверка импортов

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Публикация обновления лаунчера

1. Отправить готовый код в `main`.
2. Открыть GitHub → Actions.
3. Выбрать **Publish Launcher**.
4. Нажать **Run workflow**.
5. Ввести новую версию, например `0.2.0`.
6. Дождаться зелёного статуса.

Не нужно вручную создавать Setup.exe, ZIP, SHA-256, manifest, tag или Release.
