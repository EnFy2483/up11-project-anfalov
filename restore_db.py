"""Полный импорт данных «Мир фитнеса» из CSV-файлов приложения 2."""

from pathlib import Path

import pandas as pd
import psycopg2

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "resources"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "fitness_db",
    "user": "postgres",
    "password": "123",
}


def read_csv(name):
    """Чтение CSV с кодировкой UTF-8 BOM."""
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig")


def main():
    products = read_csv("Products_import.csv")
    variants = read_csv("Variants_import.csv")
    stock = read_csv("Stock_Items_import.csv")
    users = read_csv("Users_import.csv")
    orders = read_csv("Orders_import.csv")

    connection = psycopg2.connect(**DB_CONFIG)
    connection.autocommit = False
    cursor = connection.cursor()

    # Очистка таблиц перед повторным импортом
    cursor.execute(
        """
        TRUNCATE order_items, orders, stock_items, products, users, roles,
                 subcategories, variants, categories RESTART IDENTITY CASCADE
        """
    )

    # 1. Категории и подкатегории
    category_ids = {}
    for name in products["Категория"].drop_duplicates():
        cursor.execute(
            "INSERT INTO categories (name) VALUES (%s) RETURNING category_id",
            (name,),
        )
        category_ids[name] = cursor.fetchone()[0]

    subcategory_ids = {}
    for _, row in products.iterrows():
        key = (row["Категория"], row["Подкатегория"])
        if key not in subcategory_ids:
            cursor.execute(
                "INSERT INTO subcategories (category_id, name) VALUES (%s, %s) RETURNING subcategory_id",
                (category_ids[row["Категория"]], row["Подкатегория"]),
            )
            subcategory_ids[key] = cursor.fetchone()[0]

    # 2. Варианты исполнения
    variant_ids = {}
    for value in variants["Вариант исполнения"]:
        cursor.execute("INSERT INTO variants (value) VALUES (%s) RETURNING variant_id", (value,))
        variant_ids[value] = cursor.fetchone()[0]

    # 3. Модели каталога
    product_ids = {}
    for _, row in products.iterrows():
        key = (row["Наименование товара"], row["Производство"])
        image = row["Изображение"] if pd.notna(row["Изображение"]) else None
        cursor.execute(
            """
            INSERT INTO products (category_id, subcategory_id, name, manufacturer,
                                  description, composition, price, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING product_id
            """,
            (
                category_ids[row["Категория"]],
                subcategory_ids[(row["Категория"], row["Подкатегория"])],
                row["Наименование товара"],
                row["Производство"],
                row["Описание"],
                row["Состав"],
                float(row["Цена"]),
                image,
            ),
        )
        product_ids[key] = cursor.fetchone()[0]

    # 4. Остатки и цены вариантов
    for _, row in stock.iterrows():
        key = (row["Наименование товара"], row["Производство"])
        cursor.execute(
            """
            INSERT INTO stock_items (product_id, variant_id, quantity, price)
            VALUES (%s, %s, %s, %s)
            """,
            (
                product_ids[key],
                variant_ids[row["Вариант исполнения"]],
                int(row["Количество доступное для заказа"]),
                float(row["Цена варианта"]),
            ),
        )

    # 5. Роли и пользователи
    role_ids = {}
    for role_name in ("Администратор", "Менеджер", "Авторизованный пользователь"):
        cursor.execute("INSERT INTO roles (name) VALUES (%s) RETURNING role_id", (role_name,))
        role_ids[role_name] = cursor.fetchone()[0]

    user_ids = {}
    for _, row in users.iterrows():
        cursor.execute(
            """
            INSERT INTO users (last_name, first_name, middle_name, login, role_id)
            VALUES (%s, %s, %s, %s, %s) RETURNING user_id
            """,
            (
                row["Фамилия"],
                row["Имя"],
                row["Отчество"],
                row["Логин"],
                role_ids[row["Роль"]],
            ),
        )
        user_ids[row["Логин"]] = cursor.fetchone()[0]

    fio_to_login = {
        f"{row['Фамилия']} {row['Имя']} {row['Отчество']}": row["Логин"] for _, row in users.iterrows()
    }

    # 6. Заказы и состав: остатки не списываем, они уже учитывают заказы
    order_ids = {}
    for number in sorted(orders["Номер заказа"].unique()):
        group = orders[orders["Номер заказа"] == number]
        fio = group["ФИО"].iloc[0]
        order_date = group["Дата заказа"].iloc[0]
        cursor.execute(
            "INSERT INTO orders (order_id, order_date, user_id) VALUES (%s, %s, %s)",
            (int(number), order_date, user_ids[fio_to_login[fio]]),
        )
        order_ids[number] = int(number)

    cursor.execute("SELECT setval('orders_order_id_seq', (SELECT MAX(order_id) FROM orders))")

    for _, row in orders.iterrows():
        key = (row["Наименование товара"], row["Производство"])
        cursor.execute(
            """
            INSERT INTO order_items (order_id, product_id, variant_id, quantity, price)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                order_ids[row["Номер заказа"]],
                product_ids[key],
                variant_ids[row["Вариант исполнения"]],
                int(row["Количество"]),
                float(row["Цена за единицу"]),
            ),
        )

    connection.commit()

    # Контроль количества записей
    for table, expected in (
        ("products", 31),
        ("stock_items", 93),
        ("users", 20),
        ("orders", 15),
        ("order_items", 30),
    ):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        actual = cursor.fetchone()[0]
        print(f"{table}: {actual} (ожидалось {expected})")
        if actual != expected:
            raise ValueError(f"Неверное количество записей в таблице {table}")

    cursor.close()
    connection.close()
    print("Импорт завершён успешно.")


if __name__ == "__main__":
    main()
