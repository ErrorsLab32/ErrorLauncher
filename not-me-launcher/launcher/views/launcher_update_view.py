from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from launcher.installation_preferences import format_size


class LauncherUpdateView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(90, 70, 90, 70)
        root.addStretch()

        title = QLabel("ОБНОВЛЕНИЕ ЛАУНЧЕРА")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label = QLabel("Подготовка обновления")
        self.status_label.setObjectName("progressLabel")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("progressDetail")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        root.addWidget(title)
        root.addSpacing(24)
        root.addWidget(self.status_label)
        root.addWidget(self.detail_label)
        root.addSpacing(8)
        root.addWidget(self.progress)
        root.addStretch()

    def show_download_progress(
        self,
        percent: int,
        downloaded: int,
        total: int,
    ) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(percent)
        self.status_label.setText(f"Загрузка — {percent}%")
        self.detail_label.setText(
            f"{format_size(downloaded)} из {format_size(total)}"
        )

    def show_preparing(self) -> None:
        self.progress.setRange(0, 0)
        self.status_label.setText("Подготовка обновления")
        self.detail_label.clear()

    def show_restarting(self) -> None:
        self.progress.setRange(0, 0)
        self.status_label.setText("Лаунчер будет перезапущен")
        self.detail_label.clear()
