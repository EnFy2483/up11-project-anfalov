"""Импорт моделей каталога из Products_import.csv (часть 1 импорта)."""

from pathlib import Path

import pandas as pd
import psycopg2

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "resources" / "Products_import.csv"

connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="fitness_db",
    user="postgres",
    password="123",
)
connection.autocommit = False
cursor = connection.cursor()

products = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

cursor.execute("SELECT name, category_id FROM categories")
category_ids = {row[0]: row[1] for row in cursor.fetchall()}

cursor.execute("SELECT name, subcategory_id FROM subcategories")
subcategory_ids = {row[0]: row[1] for row in cursor.fetchall()}

imported = 0
for _, row in products.iterrows():
    image = row["Изображение"] if pd.notna(row["Изображение"]) else None
    cursor.execute(
        """
        INSERT INTO products (category_id, subcategory_id, name, manufacturer,
                              description, composition, price, image_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (name, manufacturer) DO NOTHING
        """,
        (
            category_ids[row["Категория"]],
            subcategory_ids[row["Подкатегория"]],
            row["Наименование товара"],
            row["Производство"],
            row["Описание"],
            row["Состав"],
            float(row["Цена"]),
            image,
        ),
    )
    imported += cursor.rowcount

connection.commit()
print(f"Импортировано товаров: {imported} из {len(products)}")

cursor.close()
connection.close()
