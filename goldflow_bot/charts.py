"""
GoldFlow — модуль генерации красивых графиков в золото-зелёной палитре.
Все графики сохраняются как PNG в память (BytesIO), чтобы сразу отправлять в Telegram.
"""

import io
import matplotlib
matplotlib.use("Agg")  # без графического интерфейса — только рендер в файл
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Фирменная палитра GoldFlow: золото + оттенки зелёного
GOLD = "#D4AF37"
DARK_GOLD = "#B8860B"
GREEN_DARK = "#1B4332"
GREEN_MID = "#2D6A4F"
GREEN_LIGHT = "#52B788"
BG_DARK = "#0F1F17"
TEXT_LIGHT = "#F5F0E1"

PALETTE = [GOLD, GREEN_MID, DARK_GOLD, GREEN_LIGHT, "#40916C", "#E9C46A", "#74C69D", "#BC9A3D"]


def _apply_dark_theme(fig, ax):
    """Применяет тёмно-золото-зелёную тему ко всем элементам графика."""
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.tick_params(colors=TEXT_LIGHT)
    ax.xaxis.label.set_color(TEXT_LIGHT)
    ax.yaxis.label.set_color(TEXT_LIGHT)
    ax.title.set_color(GOLD)
    for spine in ax.spines.values():
        spine.set_color(GREEN_MID)


def generate_pie_chart(category_totals: dict, title="Расходы по категориям") -> io.BytesIO:
    """Круговая диаграмма расходов по категориям."""
    fig, ax = plt.subplots(figsize=(7, 7))
    _apply_dark_theme(fig, ax)

    labels = list(category_totals.keys())
    values = list(category_totals.values())
    colors = PALETTE[:len(labels)]

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.0f%%",
        colors=colors,
        startangle=90,
        textprops={"color": TEXT_LIGHT, "fontsize": 11, "weight": "bold"},
        wedgeprops={"edgecolor": BG_DARK, "linewidth": 2},
    )
    for autotext in autotexts:
        autotext.set_color(BG_DARK)
        autotext.set_weight("bold")

    ax.set_title(title, fontsize=16, weight="bold", pad=20)
    ax.axis("equal")

    return _save_to_buffer(fig)


def generate_trend_chart(dates, balances, title="Динамика баланса") -> io.BytesIO:
    """Линейный график изменения баланса по дням."""
    fig, ax = plt.subplots(figsize=(9, 5))
    _apply_dark_theme(fig, ax)

    ax.plot(dates, balances, color=GOLD, linewidth=2.5, marker="o",
            markersize=4, markerfacecolor=GREEN_LIGHT, markeredgecolor=GOLD)
    ax.fill_between(dates, balances, min(balances) if balances else 0,
                     color=GREEN_MID, alpha=0.25)

    ax.set_title(title, fontsize=16, weight="bold", pad=15)
    ax.set_ylabel("Баланс")
    ax.grid(True, color=GREEN_MID, alpha=0.2, linestyle="--")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate()

    return _save_to_buffer(fig)


def generate_budget_bar(budgets: dict, spent: dict, title="Прогресс по бюджету") -> io.BytesIO:
    """Горизонтальные бары прогресса трат по установленным лимитам."""
    fig, ax = plt.subplots(figsize=(8, max(3, len(budgets) * 0.8)))
    _apply_dark_theme(fig, ax)

    categories = list(budgets.keys())
    limits = [budgets[c] for c in categories]
    spent_vals = [spent.get(c, 0) for c in categories]

    y_pos = range(len(categories))

    ax.barh(y_pos, limits, color=GREEN_DARK, height=0.5, label="Лимит")
    bar_colors = [GOLD if s <= l else "#C0392B" for s, l in zip(spent_vals, limits)]
    ax.barh(y_pos, spent_vals, color=bar_colors, height=0.5, label="Потрачено")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, color=TEXT_LIGHT)
    ax.set_title(title, fontsize=15, weight="bold", pad=15)
    ax.legend(facecolor=BG_DARK, edgecolor=GREEN_MID, labelcolor=TEXT_LIGHT)

    return _save_to_buffer(fig)


def _save_to_buffer(fig) -> io.BytesIO:
    """Сохраняет фигуру matplotlib в BytesIO-буфер (готово к отправке в Telegram)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
