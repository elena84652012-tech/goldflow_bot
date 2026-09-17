"""
GoldFlow — модуль распознавания суммы и категории из свободного текста.
Пример: "500 продукты" -> (500, "Еда", расход)
        "+5000 зарплата" -> (5000, "Зарплата", доход)
"""

import re

# Ключевые слова -> категория (можно расширять)
CATEGORY_KEYWORDS = {
    "Еда": ["продукт", "еда", "кафе", "ресторан", "кофе", "обед", "ужин",
            "завтрак", "супермаркет", "магазин", "food", "grocery"],
    "Транспорт": ["такси", "метро", "автобус", "бензин", "транспорт", "grab",
                  "uber", "парковка", "taxi"],
    "Жильё": ["аренда", "квартир", "коммунал", "жкх", "rent", "интернет", "wifi"],
    "Развлечения": ["кино", "игра", "развлечен", "концерт", "бар", "клуб",
                     "netflix", "spotify", "подписка"],
    "Здоровье": ["аптека", "врач", "лекарств", "клиника", "спорт", "зал", "gym"],
    "Одежда": ["одежда", "обувь", "шоппинг", "shopping"],
    "Зарплата": ["зарплата", "salary", "аванс", "доход", "стипенд"],
    "Другое": [],
}

# Слова/символы, которые сигнализируют о доходе
INCOME_MARKERS = ["+", "зарплата", "доход", "стипенд", "salary", "income"]


def detect_category(text: str) -> str:
    """Ищет ключевые слова в тексте и возвращает подходящую категорию."""
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return None  # категория не распознана — спросим у пользователя


def parse_transaction(text: str):
    """
    Разбирает текст вида "500 продукты" или "+5000 зарплата".
    Возвращает dict {amount, category, is_income} или None, если не удалось распознать сумму.
    """
    text = text.strip()

    # Ищем число (с точкой/запятой, с необязательным + в начале)
    match = re.search(r"([+-]?\d+[.,]?\d*)", text)
    if not match:
        return None

    amount_str = match.group(1).replace(",", ".")
    is_income = amount_str.startswith("+") or any(
        marker in text.lower() for marker in INCOME_MARKERS if marker != "+"
    )
    amount = abs(float(amount_str))

    if amount <= 0:
        return None

    category = detect_category(text)

    return {
        "amount": amount,
        "category": category,  # может быть None — тогда бот спросит кнопками
        "is_income": is_income,
    }


def get_all_categories(include_income=False):
    """Возвращает список всех категорий расходов (для кнопок выбора)."""
    categories = [c for c in CATEGORY_KEYWORDS.keys() if c != "Зарплата"]
    if include_income:
        categories.append("Зарплата")
    return categories
