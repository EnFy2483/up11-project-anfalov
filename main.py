"""Главное окно приложения «Мир фитнеса»: каталог товаров."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database import Database

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"
IMAGES_DIR = RESOURCES_DIR / "Images"

COLOR_TEXT = "#000000"
COLOR_BACKGROUND = "#FFFFFF"
COLOR_SECONDARY = "#D2F6E7"
COLOR_ACCENT = "#70B2AF"
COLOR_LOW_STOCK = "#ff8080"
LOW_STOCK_LIMIT = 3

BUTTON_STYLE = (
    "QPushButton {"
    f" background-color: {COLOR_ACCENT}; color: {COLOR_TEXT};"
    " font-family: Calibri; border-radius: 4px; padding: 6px 10px;"
    "}"
    "QPushButton:disabled { background-color: #b9b9b9; }"
)


def format_money(value):
    """Сумма с двумя знаками и обозначением рубля."""
    return f"{float(value):.2f} ₽"


def create_card(product, on_add):
    """Карточка модели каталога с выбором варианта исполнения."""
    (
        product_id,
        name,
        category,
        subcategory,
        manufacturer,
        description,
        composition,
        base_price,
        image_path,
        total_quantity,
    ) = product

    card = QFrame()
    background = COLOR_LOW_STOCK if total_quantity <= LOW_STOCK_LIMIT else COLOR_SECONDARY
    card.setStyleSheet(
        "QFrame {"
        f" background-color: {background}; border-radius: 8px; margin-bottom: 6px;"
        f" font-family: Calibri; color: {COLOR_TEXT};"
        "}"
    )

    layout = QHBoxLayout(card)

    image_label = QLabel()
    image_label.setFixedSize(110, 110)
    pixmap = QPixmap(str(IMAGES_DIR / image_path)) if image_path else QPixmap()
    if pixmap.isNull():
        pixmap = QPixmap(str(RESOURCES_DIR / "picture.png"))
    image_label.setPixmap(
        pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    )
    layout.addWidget(image_label)

    text_layout = QVBoxLayout()
    title = QLabel(f"{manufacturer} | {name}")
    title.setStyleSheet("font-size: 16px; font-weight: bold;")
    text_layout.addWidget(title)

    type_text = category
    if subcategory:
        type_text = f"{category} / {subcategory}"
    category_label = QLabel(f"Категория: {type_text}")
    text_layout.addWidget(category_label)

    description_label = QLabel(description or "")
    description_label.setWordWrap(True)
    description_label.setMaximumWidth(420)
    text_layout.addWidget(description_label)

    if composition:
        composition_label = QLabel(f"Состав: {composition}")
        composition_label.setWordWrap(True)
        composition_label.setMaximumWidth(420)
        text_layout.addWidget(composition_label)

    quantity_label = QLabel(f"Всего в наличии: {total_quantity} шт.")
    text_layout.addWidget(quantity_label)
    layout.addLayout(text_layout, 1)

    price_layout = QVBoxLayout()
    price_label = QLabel(f"от {format_money(base_price)}")
    price_label.setStyleSheet("font-size: 18px; font-weight: bold;")
    price_layout.addWidget(price_label)

    variant_combo = QComboBox()
    variants = on_add["variants"](product_id)
    for variant_id, variant_value, quantity, price in variants:
        title_text = f"{variant_value} — {format_money(price)}"
        if quantity <= 0:
            title_text += " (нет в наличии)"
        variant_combo.addItem(title_text, (variant_id, quantity, float(price)))
    price_layout.addWidget(variant_combo)

    variant_label = QLabel()
    variant_label.setWordWrap(True)
    variant_label.setMaximumWidth(230)
    price_layout.addWidget(variant_label)

    add_button = QPushButton("Добавить в корзину")
    add_button.setStyleSheet(BUTTON_STYLE)
    price_layout.addWidget(add_button)
    layout.addLayout(price_layout)

    def update_variant_label():
        data = variant_combo.currentData()
        if data is None:
            variant_label.setText("Нет доступных вариантов")
            add_button.setEnabled(False)
            return
        variant_id, quantity, price = data
        if quantity <= 0:
            variant_label.setText("Недоступно для заказа")
            add_button.setEnabled(False)
        else:
            variant_label.setText(f"Цена: {format_money(price)} · В наличии: {quantity} шт.")
            add_button.setEnabled(True)

    def handle_add():
        data = variant_combo.currentData()
        if data is None:
            return
        variant_id, quantity, price = data
        variant_text = variant_combo.currentText().split(" — ")[0]
        if quantity <= 0:
            QMessageBox.warning(card, "Недоступно", "Этот вариант недоступен для заказа.")
            return
        on_add["add"](product_id, variant_id, name, manufacturer, variant_text, price, quantity)

    variant_combo.currentIndexChanged.connect(update_variant_label)
    add_button.clicked.connect(handle_add)
    update_variant_label()

    return card


class MainWindow(QMainWindow):
    """Каталог с поиском, фильтром, сортировкой и корзиной."""

    def __init__(self, db, user_id=None, role_id=None, full_name=None):
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.role_id = role_id
        self.full_name = full_name
        self.cart = {}

        self.setWindowTitle("Мир фитнеса — Каталог")
        self.resize(1000, 700)
        self.setWindowIcon(QIcon(str(RESOURCES_DIR / "icon.ico")))
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {COLOR_BACKGROUND}; }}"
            f" QLabel {{ color: {COLOR_TEXT}; font-family: Calibri; }}"
        )

        self.setup_ui()
        self.setup_role_interface()
        self.load_products()

    def setup_ui(self):
        container = QWidget()
        main_layout = QVBoxLayout()

        header = QWidget()
        header.setStyleSheet(f"QWidget {{ background-color: {COLOR_SECONDARY}; }}")
        header_layout = QHBoxLayout(header)

        logo = QLabel()
        logo_pixmap = QPixmap(str(RESOURCES_DIR / "logo.png"))
        if not logo_pixmap.isNull():
            logo.setPixmap(
                logo_pixmap.scaled(120, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        header_layout.addWidget(logo)

        title = QLabel("Мир фитнеса")
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLOR_ACCENT};")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.user_label = QLabel(self.full_name or "Гость")
        self.user_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self.user_label)

        self.cart_button = QPushButton("Корзина: 0")
        self.cart_button.setStyleSheet(BUTTON_STYLE)
        self.cart_button.clicked.connect(self.open_cart)
        header_layout.addWidget(self.cart_button)

        self.orders_button = QPushButton("Заказы")
        self.orders_button.setStyleSheet(BUTTON_STYLE)
        self.orders_button.clicked.connect(self.open_orders)
        header_layout.addWidget(self.orders_button)

        self.logout_button = QPushButton("Выход")
        self.logout_button.setStyleSheet(BUTTON_STYLE)
        self.logout_button.clicked.connect(self.logout)
        header_layout.addWidget(self.logout_button)

        main_layout.addWidget(header)

        filters = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию")
        self.search_input.textChanged.connect(self.load_products)
        filters.addWidget(self.search_input, 2)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Все категории")
        self.filter_combo.addItems(self.db.get_categories())
        self.filter_combo.currentIndexChanged.connect(self.load_products)
        filters.addWidget(self.filter_combo, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Цена: по возрастанию", "Цена: по убыванию"])
        self.sort_combo.currentIndexChanged.connect(self.load_products)
        filters.addWidget(self.sort_combo, 1)

        main_layout.addLayout(filters)

        self.products_container = QWidget()
        self.products_layout = QVBoxLayout()
        self.products_container.setLayout(self.products_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.products_container)
        main_layout.addWidget(scroll, 1)

        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_role_interface(self):
        """Гость видит только каталог, заказы доступны менеджеру и администратору."""
        is_authorized = self.role_id is not None
        self.cart_button.setVisible(is_authorized)
        self.orders_button.setVisible(self.role_id in (1, 2))

    def load_products(self):
        while self.products_layout.count():
            item = self.products_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        search_text = self.search_input.text().strip()
        category = self.filter_combo.currentText()
        sort_order = "DESC" if self.sort_combo.currentIndex() == 1 else "ASC"

        handlers = {"variants": self.db.get_variants, "add": self.add_to_cart}
        for product in self.db.get_products(search_text, category, sort_order):
            self.products_layout.addWidget(create_card(product, handlers))
        self.products_layout.addStretch()

    def add_to_cart(self, product_id, variant_id, name, manufacturer, variant, price, available):
        """Добавление позиции в корзину, повторное добавление увеличивает количество."""
        key = (product_id, variant_id)
        if key in self.cart:
            if self.cart[key]["quantity"] < available:
                self.cart[key]["quantity"] += 1
            else:
                QMessageBox.information(self, "Остаток", f"Доступно только {available} шт.")
        else:
            self.cart[key] = {
                "name": name,
                "manufacturer": manufacturer,
                "variant": variant,
                "price": price,
                "available": available,
                "quantity": 1,
            }
        self.update_cart_button()

    def update_cart_button(self):
        total = sum(item["quantity"] for item in self.cart.values())
        self.cart_button.setText(f"Корзина: {total}")

    def open_cart(self):
        from cart_dialog import CartDialog

        dialog = CartDialog(self.db, self.user_id, self.cart, self)
        dialog.exec()
        self.update_cart_button()
        self.load_products()

    def open_orders(self):
        from orders_dialog import OrdersDialog

        OrdersDialog(self.db, self.role_id, self).exec()
        self.load_products()

    def logout(self):
        reply = QMessageBox.question(
            self,
            "Выход",
            "Выйти из учётной записи?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from login_window import LoginWindow

            self.login_window = LoginWindow(self.db)
            self.login_window.show()
            self.close()


def main():
    from login_window import LoginWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Calibri", 12))

    db = Database()
    window = LoginWindow(db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
