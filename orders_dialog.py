"""Список заказов и просмотр состава (менеджер и администратор)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from main import BUTTON_STYLE, format_money


def format_date(value):
    """Дата в формате ДД.ММ.ГГГГ."""
    return value.strftime("%d.%m.%Y")


class OrdersDialog(QDialog):
    """Список всех заказов с просмотром и удалением."""

    def __init__(self, db, role_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.role_id = role_id

        self.setWindowTitle("Заказы")
        self.resize(820, 480)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; font-family: Calibri; }")

        layout = QVBoxLayout(self)

        title = QLabel("Список заказов")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Номер", "Дата", "Клиент", "Позиций", "Итог"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.show_items)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        refresh_button = QPushButton("Обновить")
        refresh_button.setStyleSheet(BUTTON_STYLE)
        refresh_button.clicked.connect(self.load_orders)
        buttons.addWidget(refresh_button)

        items_button = QPushButton("Состав заказа")
        items_button.setStyleSheet(BUTTON_STYLE)
        items_button.clicked.connect(self.show_items)
        buttons.addWidget(items_button)

        buttons.addStretch()

        self.date_button = QPushButton("Изменить дату")
        self.date_button.setStyleSheet(BUTTON_STYLE)
        self.date_button.clicked.connect(self.change_date)
        self.date_button.setVisible(self.role_id == 1)
        buttons.addWidget(self.date_button)

        self.delete_button = QPushButton("Удалить заказ")
        self.delete_button.setStyleSheet(BUTTON_STYLE)
        self.delete_button.clicked.connect(self.delete_order)
        buttons.addWidget(self.delete_button)

        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet(BUTTON_STYLE)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)

        layout.addLayout(buttons)
        self.load_orders()

    def load_orders(self):
        orders = self.db.get_orders()
        self.table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            order_id, order_date, client, items_count, total = order
            self.table.setItem(row, 0, QTableWidgetItem(str(order_id)))
            self.table.setItem(row, 1, QTableWidgetItem(format_date(order_date)))
            self.table.setItem(row, 2, QTableWidgetItem(client))
            self.table.setItem(row, 3, QTableWidgetItem(str(items_count)))
            self.table.setItem(row, 4, QTableWidgetItem(format_money(total)))

    def current_order_id(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Заказ", "Выберите заказ в списке.")
            return None
        return int(self.table.item(row, 0).text())

    def show_items(self):
        order_id = self.current_order_id()
        if order_id is None:
            return
        dialog = OrderItemsDialog(self.db, order_id, self.role_id, self)
        dialog.exec()
        self.load_orders()

    def delete_order(self):
        order_id = self.current_order_id()
        if order_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Удаление заказа",
            f"Удалить заказ № {order_id}? Остатки вернутся в каталог.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_order(order_id)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return
        QMessageBox.information(self, "Готово", f"Заказ № {order_id} удалён.")
        self.load_orders()

    def change_date(self):
        order_id = self.current_order_id()
        if order_id is None:
            return
        current = self.table.item(self.table.currentRow(), 1).text()
        date_text, ok = QInputDialog.getText(
            self,
            "Дата заказа",
            "Введите дату в формате ДД.ММ.ГГГГ:",
            text=current,
        )
        if not ok or not date_text.strip():
            return
        try:
            day, month, year = date_text.strip().split(".")
            order_date = f"{year}-{month}-{day}"
            self.db.update_order_date(order_id, order_date)
        except Exception as error:
            QMessageBox.warning(self, "Ошибка", f"Некорректная дата: {error}")
            return
        self.load_orders()


class OrderItemsDialog(QDialog):
    """Состав заказа; администратор может удалить отдельную строку."""

    def __init__(self, db, order_id, role_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.order_id = order_id
        self.role_id = role_id

        self.setWindowTitle(f"Состав заказа № {order_id}")
        self.resize(760, 420)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; font-family: Calibri; }")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Состав заказа № {order_id}"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Товар", "Производство", "Вариант", "Количество", "Цена", "Сумма"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.total_label = QLabel("Итого: 0.00 ₽")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.total_label)

        buttons = QHBoxLayout()
        buttons.addStretch()

        if role_id == 1:
            self.delete_row_button = QPushButton("Удалить строку")
            self.delete_row_button.setStyleSheet(BUTTON_STYLE)
            self.delete_row_button.clicked.connect(self.delete_row)
            buttons.addWidget(self.delete_row_button)

        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet(BUTTON_STYLE)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)

        layout.addLayout(buttons)
        self.load_items()

    def load_items(self):
        items = self.db.get_order_items(self.order_id)
        self.table.setRowCount(len(items))
        total = 0.0
        for row, item in enumerate(items):
            order_item_id, name, manufacturer, variant, quantity, price, line_total = item
            total += float(line_total)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(manufacturer))
            self.table.setItem(row, 2, QTableWidgetItem(variant))
            self.table.setItem(row, 3, QTableWidgetItem(str(quantity)))
            self.table.setItem(row, 4, QTableWidgetItem(format_money(price)))
            self.table.setItem(row, 5, QTableWidgetItem(format_money(line_total)))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, order_item_id)
        self.total_label.setText(f"Итого: {format_money(total)}")

    def delete_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Строка", "Выберите строку заказа.")
            return
        reply = QMessageBox.question(
            self,
            "Удаление строки",
            "Удалить выбранную строку? Остаток вернётся в каталог.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        order_item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            order_id, rest = self.db.delete_order_item(order_item_id)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return
        if rest == 0:
            reply = QMessageBox.question(
                self,
                "Пустой заказ",
                "Это была последняя строка. Удалить заказ полностью?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.db.delete_order(order_id)
                except Exception as error:
                    QMessageBox.critical(self, "Ошибка", str(error))
                self.accept()
                return
        self.load_items()
