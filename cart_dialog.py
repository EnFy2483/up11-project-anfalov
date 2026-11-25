"""Корзина: изменение количества и оформление заказа."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from main import BUTTON_STYLE, format_money


class CartDialog(QDialog):
    """Просмотр корзины и подтверждение заказа."""

    def __init__(self, db, user_id, cart, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.cart = cart

        self.setWindowTitle("Корзина")
        self.resize(700, 450)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; font-family: Calibri; }")

        layout = QVBoxLayout(self)

        title = QLabel("Корзина")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Товар", "Вариант", "Цена", "Количество", "Сумма"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.total_label = QLabel("Итого: 0.00 ₽")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.total_label)

        buttons = QHBoxLayout()

        clear_button = QPushButton("Очистить корзину")
        clear_button.setStyleSheet(BUTTON_STYLE)
        clear_button.clicked.connect(self.clear_cart)
        buttons.addWidget(clear_button)

        buttons.addStretch()

        close_button = QPushButton("Продолжить покупки")
        close_button.setStyleSheet(BUTTON_STYLE)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(close_button)

        self.order_button = QPushButton("Оформить заказ")
        self.order_button.setStyleSheet(BUTTON_STYLE)
        self.order_button.clicked.connect(self.confirm_order)
        buttons.addWidget(self.order_button)

        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        """Перерисовка таблицы и итоговой суммы."""
        keys = list(self.cart.keys())
        self.table.setRowCount(len(keys))

        for row, key in enumerate(keys):
            item = self.cart[key]
            self.table.setItem(row, 0, QTableWidgetItem(f"{item['manufacturer']} | {item['name']}"))
            self.table.setItem(row, 1, QTableWidgetItem(item["variant"]))
            self.table.setItem(row, 2, QTableWidgetItem(format_money(item["price"])))

            spin = QSpinBox()
            spin.setRange(1, max(1, item["available"]))
            spin.setValue(item["quantity"])
            spin.valueChanged.connect(lambda value, k=key: self.change_quantity(k, value))
            self.table.setCellWidget(row, 3, spin)

            line_total = item["price"] * item["quantity"]
            self.table.setItem(row, 4, QTableWidgetItem(format_money(line_total)))

        total = sum(item["price"] * item["quantity"] for item in self.cart.values())
        self.total_label.setText(f"Итого: {format_money(total)}")
        self.order_button.setEnabled(bool(self.cart))

    def change_quantity(self, key, value):
        if key in self.cart:
            self.cart[key]["quantity"] = value
            self.refresh()

    def clear_cart(self):
        self.cart.clear()
        self.refresh()

    def confirm_order(self):
        """Сохранение заказа: остатки и цены повторно проверяются в базе."""
        if not self.cart:
            return
        items = [
            (product_id, variant_id, item["quantity"])
            for (product_id, variant_id), item in self.cart.items()
        ]
        try:
            order_id = self.db.create_order(self.user_id, items)
        except ValueError as error:
            QMessageBox.warning(self, "Ошибка", str(error))
            return
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось оформить заказ: {error}")
            return

        QMessageBox.information(self, "Заказ оформлен", f"Заказ № {order_id} успешно сохранён.")
        self.cart.clear()
        self.accept()
