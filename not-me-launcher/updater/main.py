import argparse
import os
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, QObject, QStandardPaths, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from updater.update_engine import UpdateEngine, UpdateEngineError, UpdateRequest


class UpdateWorker(QObject):
    status_changed = Signal(str, bool)
    succeeded = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, engine: UpdateEngine) -> None:
        super().__init__()
        self.engine = engine

    @Slot()
    def run(self) -> None:
        try:
            self.engine.apply(self.status_changed.emit)
            self.succeeded.emit()
        except UpdateEngineError as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class UpdaterWindow(QMainWindow):
    def __init__(self, engine: UpdateEngine) -> None:
        super().__init__()
        self.setWindowTitle("ErrorLabs Updater")
        self.setFixedSize(460, 170)
        self._critical = True

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)
        title = QLabel("ОБНОВЛЕНИЕ ЛАУНЧЕРА")
        title.setObjectName("title")
        self.status = QLabel("Ожидание завершения лаунчера")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        hint = QLabel("Лаунчер автоматически перезапустится")
        hint.setObjectName("hint")
        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(hint)
        self.setCentralWidget(content)

        self.setStyleSheet(
            "QMainWindow, QWidget { background: #0b0b0c; color: #e5e3de; "
            "font-family: 'Segoe UI'; font-size: 13px; }"
            "QLabel#title { color: #f2f0ea; font-size: 15px; font-weight: 700; "
            "letter-spacing: 1px; }"
            "QLabel#hint { color: #777772; font-size: 11px; }"
            "QProgressBar { min-height: 4px; max-height: 4px; background: #242423; "
            "border: none; }"
            "QProgressBar::chunk { background: #b9a073; }"
        )

        self.thread = QThread(self)
        self.worker = UpdateWorker(engine)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status_changed.connect(self._set_status)
        self.worker.succeeded.connect(self._on_succeeded)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

    def start(self) -> None:
        self.thread.start()

    @Slot(str, bool)
    def _set_status(self, text: str, indeterminate: bool) -> None:
        self.status.setText(text)
        if indeterminate:
            self.progress.setRange(0, 0)

    @Slot()
    def _on_succeeded(self) -> None:
        self._critical = False
        self.close()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._critical = False
        QMessageBox.critical(self, "ErrorLabs Updater", message)
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._critical:
            event.ignore()
        else:
            event.accept()


def parse_arguments(arguments: list[str]) -> UpdateRequest:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--version", required=True)
    values = parser.parse_args(arguments)
    return UpdateRequest(
        Path(values.package),
        Path(values.target),
        Path(values.entrypoint),
        values.pid,
        values.version,
    )


def run(arguments: list[str] | None = None) -> int:
    QCoreApplication.setOrganizationName("ErrorLabs")
    QCoreApplication.setApplicationName("ErrorLabs Playtest")
    app = QApplication(sys.argv if arguments is None else [sys.argv[0], *arguments])
    request = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    local_data = os.getenv("ERRORLABS_LOCAL_DATA_DIR", "").strip() or QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    if not local_data:
        return 1
    engine = UpdateEngine(request, Path(local_data))
    window = UpdaterWindow(engine)
    window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
