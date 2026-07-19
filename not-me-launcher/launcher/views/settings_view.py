import random
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from launcher.installation_preferences import (
    InstallationPathError,
    InstallationPreferences,
)


class SettingsView(QWidget):
    back_requested = Signal()
    logout_requested = Signal()

    def __init__(self, preferences: InstallationPreferences) -> None:
        super().__init__()
        self.setObjectName("page")
        self._preferences = preferences

        root = QVBoxLayout(self)
        root.setContentsMargins(42, 28, 42, 34)
        root.setSpacing(0)

        header = QHBoxLayout()
        brand = QLabel("ERRORLABS PLAYTEST")
        brand.setObjectName("brandTitle")
        back_button = QPushButton("НАЗАД")
        back_button.setObjectName("headerButton")
        back_button.clicked.connect(self.back_requested)
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(back_button)
        root.addLayout(header)
        root.addSpacing(16)
        root.addWidget(self._separator())

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 30, 12, 20)
        content_layout.setSpacing(0)

        title = QLabel("Настройки аккаунта")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Локальные параметры лаунчера")
        subtitle.setObjectName("mutedLabel")
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addSpacing(30)

        form = QFrame()
        form.setObjectName("settingsForm")
        form.setMaximumWidth(680)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        path_caption = QLabel("ПАПКА УСТАНОВКИ")
        path_caption.setObjectName("sectionCaption")
        self.install_path_label = QLabel()
        self.install_path_label.setObjectName("pathValue")
        self.install_path_label.setWordWrap(True)
        path_actions = QHBoxLayout()
        self.change_path_button = QPushButton("ИЗМЕНИТЬ")
        self.change_path_button.clicked.connect(self._choose_install_path)
        self.open_path_button = QPushButton("ОТКРЫТЬ ПАПКУ")
        self.open_path_button.clicked.connect(self._open_install_path)
        path_actions.addWidget(self.change_path_button)
        path_actions.addWidget(self.open_path_button)
        path_actions.addStretch()

        login_caption = QLabel("ЛОГИН ПОЛЬЗОВАТЕЛЯ")
        login_caption.setObjectName("sectionCaption")
        login_value = QLabel("player_demo")
        login_value.setObjectName("sectionTitle")
        change_password_button = QPushButton("Сменить пароль")
        change_password_button.clicked.connect(self._show_password_message)

        code_caption = QLabel("КОД ВОССТАНОВЛЕНИЯ")
        code_caption.setObjectName("sectionCaption")
        code_description = QLabel(
            "Сохраните этот код в надёжном месте. В прототипе он не хранится."
        )
        code_description.setWordWrap(True)
        code_description.setObjectName("mutedLabel")
        self.code_label = QLabel("482739")
        self.code_label.setObjectName("recoveryCode")
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        new_code_button = QPushButton("Создать новый код")
        new_code_button.clicked.connect(self._create_code)

        logout_button = QPushButton("Выйти из аккаунта")
        logout_button.setObjectName("dangerTextButton")
        logout_button.clicked.connect(self.logout_requested)

        form_layout.addWidget(path_caption)
        form_layout.addWidget(self.install_path_label)
        form_layout.addLayout(path_actions)
        form_layout.addSpacing(20)
        form_layout.addWidget(self._separator())
        form_layout.addSpacing(18)
        form_layout.addWidget(login_caption)
        form_layout.addWidget(login_value)
        form_layout.addWidget(change_password_button)
        form_layout.addSpacing(20)
        form_layout.addWidget(self._separator())
        form_layout.addSpacing(18)
        form_layout.addWidget(code_caption)
        form_layout.addWidget(code_description)
        form_layout.addWidget(self.code_label)
        form_layout.addWidget(new_code_button)
        form_layout.addSpacing(22)
        form_layout.addWidget(logout_button, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(form, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        preferences.install_path_changed.connect(self._on_install_path_changed)
        preferences.download_active_changed.connect(self._on_download_active_changed)
        self._refresh_install_path()
        self._on_download_active_changed(preferences.download_active)

    def _choose_install_path(self) -> None:
        if self._preferences.download_active:
            return
        start = self._preferences.install_path or Path.home()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку установки Not Me",
            str(start),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        try:
            self._preferences.validate_and_set_install_path(Path(selected))
        except InstallationPathError as error:
            QMessageBox.warning(self, "ErrorLabs Playtest", str(error))

    def _open_install_path(self) -> None:
        path = self._preferences.install_path
        if path is not None and path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot(object)
    def _on_install_path_changed(self, _path: object) -> None:
        self._refresh_install_path()

    @Slot(bool)
    def _on_download_active_changed(self, active: bool) -> None:
        self.change_path_button.setEnabled(not active)

    def _refresh_install_path(self) -> None:
        path = self._preferences.install_path
        self.install_path_label.setText(str(path) if path is not None else "Не выбрана")
        self.open_path_button.setEnabled(path is not None and path.is_dir())

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator

    def _create_code(self) -> None:
        self.code_label.setText(f"{random.randint(0, 999999):06d}")

    def _show_password_message(self) -> None:
        QMessageBox.information(
            self,
            "Смена пароля",
            "В прототипе смена пароля не выполняется.",
        )
