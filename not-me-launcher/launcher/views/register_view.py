from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RegisterView(QWidget):
    registration_requested = Signal()
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")

        title = QLabel("Создание аккаунта")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Заполните данные для регистрации")
        subtitle.setObjectName("mutedLabel")

        fields = [
            ("Логин", QLineEdit.EchoMode.Normal),
            ("Пароль", QLineEdit.EchoMode.Password),
            ("Повторите пароль", QLineEdit.EchoMode.Password),
            ("Код приглашения", QLineEdit.EchoMode.Normal),
        ]

        form = QFrame()
        form.setObjectName("authForm")
        form.setMinimumWidth(350)
        form.setMaximumWidth(410)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        form_layout.addWidget(title)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(20)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Отображаемое имя")
        self._inputs: list[QLineEdit] = []
        for index, (placeholder, echo_mode) in enumerate(fields):
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setEchoMode(echo_mode)
            self._inputs.append(field)
            form_layout.addWidget(field)
            if index == 0:
                form_layout.addWidget(self.display_name_input)

        (
            self.login_input,
            self.password_input,
            self.password_confirmation_input,
            self.invite_code_input,
        ) = self._inputs

        register_button = QPushButton("Зарегистрироваться")
        self.register_button = register_button
        self.register_button.setObjectName("primaryButton")
        register_button.clicked.connect(self.registration_requested)
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.back_requested)
        form_layout.addSpacing(4)
        self.error_label = QLabel()
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        form_layout.addWidget(register_button)
        form_layout.addWidget(self.error_label)
        form_layout.addWidget(back_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()
        layout.addWidget(form, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def set_registration_in_progress(self, in_progress: bool) -> None:
        self.register_button.setEnabled(not in_progress)

    def show_registration_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def clear_registration_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()
