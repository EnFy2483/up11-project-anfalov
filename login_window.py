"""Окно авторизации: вход по логину без пароля или режим гостя."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"

BUTTON_STYLE = (
    "QPushButton { background-color: #70B2AF; color: #000000; font-family: Calibri;"
    " border-radius: 4px; padding: 6px 10px; }"
)


class LoginWindow(QDialog):
    """Вход по логину из таблицы users."""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.main_window = None

        self.setWindowTitle("Мир фитнеса — Вход")
        self.resize(360, 260)
        self.setStyleSheet(
            "QDialog { background-color: #FFFFFF; font-family: Calibri; }"
            "QLabel { color: #000000; }"
        )

        layout = QVBoxLayout(self)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(RESOURCES_DIR / "logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(180, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(logo)

        title = QLabel("Мир фитнеса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #70B2AF;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Логин:"))
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Например, admin")
        self.login_input.returnPressed.connect(self.check_login)
        layout.addWidget(self.login_input)

        login_button = QPushButton("Войти")
        login_button.setStyleSheet(BUTTON_STYLE)
        login_button.clicked.connect(self.check_login)
        layout.addWidget(login_button)

        guest_button = QPushButton("Продолжить как гость")
        guest_button.setStyleSheet(BUTTON_STYLE)
        guest_button.clicked.connect(self.login_as_guest)
        layout.addWidget(guest_button)

    def check_login(self):
        login = self.login_input.text().strip()
        if not login:
            QMessageBox.warning(self, "Ошибка", "Введите логин.")
            return

        user = self.db.get_user_by_login(login)
        if user is None:
            QMessageBox.warning(self, "Ошибка", "Пользователь с таким логином не найден.")
            return

        full_name = " ".join(
            part for part in (user["last_name"], user["first_name"], user["middle_name"]) if part
        )
        self.open_main_window(user["user_id"], user["role_id"], full_name)

    def login_as_guest(self):
        self.open_main_window(None, None, None)

    def open_main_window(self, user_id, role_id, full_name):
        from main import MainWindow

        self.main_window = MainWindow(
            self.db,
            user_id=user_id,
            role_id=role_id,
            full_name=full_name,
        )
        self.main_window.show()
        self.close()
