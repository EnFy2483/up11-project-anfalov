"""Работа с базой данных PostgreSQL «Мир фитнеса»."""

import os

import psycopg2
from psycopg2 import pool, extras


DB_CONFIG = {
    "host": os.environ.get("FITNESS_DB_HOST", "localhost"),
    "port": os.environ.get("FITNESS_DB_PORT", "5432"),
    "dbname": os.environ.get("FITNESS_DB_NAME", "fitness_db"),
    "user": os.environ.get("FITNESS_DB_USER", "postgres"),
    "password": os.environ.get("FITNESS_DB_PASSWORD", "123"),
}


class Database:
    """Пул соединений и запросы приложения."""

    def __init__(self):
        self.pool = None
        try:
            self.pool = pool.SimpleConnectionPool(1, 5, **DB_CONFIG)
            print("Пул соединений создан")
        except Exception as error:
            print(f"Ошибка подключения к БД: {error}")

    def get_connection(self):
        if self.pool is None:
            return None
        return self.pool.getconn()

    def release_connection(self, connection):
        if self.pool is not None and connection is not None:
            self.pool.putconn(connection)

    def close_all(self):
        if self.pool is not None:
            self.pool.closeall()

    def get_categories(self):
        """Список категорий для фильтра."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM categories ORDER BY name")
                return [row[0] for row in cursor.fetchall()]
        except Exception as error:
            print(f"Ошибка запроса категорий: {error}")
            return []
        finally:
            self.release_connection(connection)

    def get_products(self, search_text="", category_name="Все категории", sort_order="ASC"):
        """Модели каталога с суммарным остатком и минимальной ценой варианта."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                query = """
                    SELECT
                        p.product_id,
                        p.name,
                        c.name AS category,
                        sc.name AS subcategory,
                        p.manufacturer,
                        p.description,
                        p.composition,
                        p.price,
                        p.image_path,
                        COALESCE(SUM(si.quantity), 0) AS total_quantity
                    FROM products p
                    JOIN categories c ON c.category_id = p.category_id
                    LEFT JOIN subcategories sc ON sc.subcategory_id = p.subcategory_id
                    LEFT JOIN stock_items si ON si.product_id = p.product_id
                    WHERE p.name ILIKE %s
                """
                params = [f"%{search_text}%"]
                if category_name and category_name != "Все категории":
                    query += " AND c.name = %s"
                    params.append(category_name)
                direction = "DESC" if sort_order == "DESC" else "ASC"
                query += f"""
                    GROUP BY p.product_id, c.name, sc.name
                    ORDER BY p.price {direction}, p.name
                """
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as error:
            print(f"Ошибка запроса товаров: {error}")
            return []
        finally:
            self.release_connection(connection)

    def get_variants(self, product_id):
        """Варианты исполнения модели: id, название, остаток, цена."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT si.variant_id, v.value, si.quantity, si.price
                    FROM stock_items si
                    JOIN variants v ON v.variant_id = si.variant_id
                    WHERE si.product_id = %s
                    ORDER BY si.price
                    """,
                    (product_id,),
                )
                return cursor.fetchall()
        except Exception as error:
            print(f"Ошибка запроса вариантов: {error}")
            return []
        finally:
            self.release_connection(connection)

    def get_user_by_login(self, login):
        """Пользователь по логину: id, role_id, ФИО."""
        connection = self.get_connection()
        if connection is None:
            return None
        try:
            with connection.cursor(cursor_factory=extras.DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, role_id, last_name, first_name, middle_name
                    FROM users
                    WHERE login = %s
                    """,
                    (login,),
                )
                return cursor.fetchone()
        except Exception as error:
            print(f"Ошибка запроса пользователя: {error}")
            return None
        finally:
            self.release_connection(connection)

    def create_order(self, user_id, items):
        """Оформление заказа: проверка остатков, списание и сохранение атомарно."""
        connection = self.get_connection()
        if connection is None:
            raise RuntimeError("Нет подключения к базе данных")
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO orders (order_date, user_id) VALUES (CURRENT_DATE, %s) RETURNING order_id",
                        (user_id,),
                    )
                    order_id = cursor.fetchone()[0]
                    for product_id, variant_id, quantity in items:
                        cursor.execute(
                            """
                            SELECT quantity, price
                            FROM stock_items
                            WHERE product_id = %s AND variant_id = %s
                            FOR UPDATE
                            """,
                            (product_id, variant_id),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise ValueError("Позиция не найдена в остатках")
                        available, price = row
                        if quantity > available:
                            raise ValueError(f"Недостаточно остатка: доступно {available} шт.")
                        cursor.execute(
                            """
                            INSERT INTO order_items (order_id, product_id, variant_id, quantity, price)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (order_id, product_id, variant_id, quantity, price),
                        )
                        cursor.execute(
                            """
                            UPDATE stock_items
                            SET quantity = quantity - %s
                            WHERE product_id = %s AND variant_id = %s
                            """,
                            (quantity, product_id, variant_id),
                        )
                    return order_id
        finally:
            self.release_connection(connection)

    def get_orders(self):
        """Список заказов: номер, дата, клиент, число позиций, итог."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        o.order_id,
                        o.order_date,
                        u.last_name || ' ' || u.first_name ||
                            COALESCE(' ' || u.middle_name, '') AS client,
                        COUNT(oi.order_item_id) AS items_count,
                        COALESCE(SUM(oi.quantity * oi.price), 0) AS total
                    FROM orders o
                    JOIN users u ON u.user_id = o.user_id
                    LEFT JOIN order_items oi ON oi.order_id = o.order_id
                    GROUP BY o.order_id, o.order_date, u.last_name, u.first_name, u.middle_name
                    ORDER BY o.order_id
                    """
                )
                return cursor.fetchall()
        except Exception as error:
            print(f"Ошибка запроса заказов: {error}")
            return []
        finally:
            self.release_connection(connection)

    def get_order_items(self, order_id):
        """Состав заказа с историческими ценами."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        oi.order_item_id,
                        p.name,
                        p.manufacturer,
                        v.value,
                        oi.quantity,
                        oi.price,
                        oi.quantity * oi.price AS line_total
                    FROM order_items oi
                    JOIN products p ON p.product_id = oi.product_id
                    JOIN variants v ON v.variant_id = oi.variant_id
                    WHERE oi.order_id = %s
                    ORDER BY oi.order_item_id
                    """,
                    (order_id,),
                )
                return cursor.fetchall()
        except Exception as error:
            print(f"Ошибка запроса состава заказа: {error}")
            return []
        finally:
            self.release_connection(connection)

    def delete_order(self, order_id):
        """Удаление заказа с возвратом остатков."""
        connection = self.get_connection()
        if connection is None:
            raise RuntimeError("Нет подключения к базе данных")
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT product_id, variant_id, quantity FROM order_items WHERE order_id = %s",
                        (order_id,),
                    )
                    for product_id, variant_id, quantity in cursor.fetchall():
                        cursor.execute(
                            """
                            UPDATE stock_items
                            SET quantity = quantity + %s
                            WHERE product_id = %s AND variant_id = %s
                            """,
                            (quantity, product_id, variant_id),
                        )
                    cursor.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
                    cursor.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        finally:
            self.release_connection(connection)

    def delete_order_item(self, order_item_id):
        """Удаление строки заказа с возвратом остатка."""
        connection = self.get_connection()
        if connection is None:
            raise RuntimeError("Нет подключения к базе данных")
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT order_id, product_id, variant_id, quantity
                        FROM order_items
                        WHERE order_item_id = %s
                        """,
                        (order_item_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        return None, 0
                    order_id, product_id, variant_id, quantity = row
                    cursor.execute(
                        """
                        UPDATE stock_items
                        SET quantity = quantity + %s
                        WHERE product_id = %s AND variant_id = %s
                        """,
                        (quantity, product_id, variant_id),
                    )
                    cursor.execute("DELETE FROM order_items WHERE order_item_id = %s", (order_item_id,))
                    cursor.execute(
                        "SELECT COUNT(*) FROM order_items WHERE order_id = %s",
                        (order_id,),
                    )
                    return order_id, cursor.fetchone()[0]
        finally:
            self.release_connection(connection)

    def update_order_date(self, order_id, order_date):
        """Изменение даты заказа (только администратор)."""
        connection = self.get_connection()
        if connection is None:
            raise RuntimeError("Нет подключения к базе данных")
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE orders SET order_date = %s WHERE order_id = %s",
                        (order_date, order_id),
                    )
        finally:
            self.release_connection(connection)

    def get_clients(self):
        """Список клиентов для создания заказа менеджером."""
        connection = self.get_connection()
        if connection is None:
            return []
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, last_name || ' ' || first_name ||
                           COALESCE(' ' || middle_name, '') AS client
                    FROM users
                    WHERE role_id = 3
                    ORDER BY last_name, first_name
                    """
                )
                return cursor.fetchall()
        except Exception as error:
            print(f"Ошибка запроса клиентов: {error}")
            return []
        finally:
            self.release_connection(connection)
