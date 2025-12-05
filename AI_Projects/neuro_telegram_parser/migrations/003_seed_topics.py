"""
Сид начальных тем (topics) для онбординга и классификации.
Запуск: python -m telegram_parser.migrations.003_seed_topics
"""

import psycopg2
from telegram_parser.config_utils import get_config


TOPICS = [
    {
        'name': 'IT',
        'synonyms': ['технологии', 'разработка', 'программирование', 'software', 'ai', 'ml'],
        'description': 'Информационные технологии, разработка ПО, искусственный интеллект',
        'color': '#45B7D1',
    },
    {
        'name': 'Экономика',
        'synonyms': ['рынок', 'инфляция', 'курс', 'биржа', 'инвестиции'],
        'description': 'Финансы, рынки, макроэкономика и инвестиции',
        'color': '#4ECDC4',
    },
    {
        'name': 'Политика',
        'synonyms': ['выборы', 'санкции', 'правительство', 'власти', 'партия'],
        'description': 'Политические события и решения',
        'color': '#FF6B6B',
    },
    {
        'name': 'Наука',
        'synonyms': ['исследования', 'космос', 'биология', 'физика', 'математика'],
        'description': 'Научные открытия и исследования',
        'color': '#DDA0DD',
    },
    {
        'name': 'Спорт',
        'synonyms': ['матч', 'турнир', 'спортсмен', 'гол', 'чемпионат'],
        'description': 'Спортивные события и результаты',
        'color': '#FFEAA7',
    },
    {
        'name': 'Искусство',
        'synonyms': ['кино', 'музыка', 'выставка', 'театр', 'литература'],
        'description': 'Культура, искусство и медиа',
        'color': '#96CEB4',
    },
    {
        'name': 'Общество',
        'synonyms': ['соцсети', 'общество', 'образование', 'здоровье', 'медицина'],
        'description': 'Социальные темы, здоровье, образование',
        'color': '#98D8C8',
    },
    {
        'name': 'Криминал',
        'synonyms': ['полиция', 'суд', 'уголовное дело', 'расследование'],
        'description': 'Происшествия и криминальные новости',
        'color': '#F7DC6F',
    },
    {
        'name': 'Международные отношения',
        'synonyms': ['дипломатия', 'международный', 'внешняя политика', 'конфликт'],
        'description': 'Внешняя политика и мировые события',
        'color': '#BB8FCE',
    },
    {
        'name': 'Экология',
        'synonyms': ['климат', 'природа', 'углерод', 'выбросы', 'зелёная энергетика'],
        'description': 'Экология, климат и устойчивое развитие',
        'color': '#85C1E9',
    },
]


def run_migration():
    config = get_config()
    dsn = config['postgresql']['dsn'] if 'postgresql' in config and 'dsn' in config['postgresql'] else None
    if not dsn:
        raise RuntimeError('PostgreSQL DSN is not configured')

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    for t in TOPICS:
        cur.execute(
            """
            INSERT INTO topics (name, synonyms, description, color)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                synonyms = EXCLUDED.synonyms,
                description = EXCLUDED.description,
                color = EXCLUDED.color,
                updated_at = NOW()
            """,
            (t['name'], t['synonyms'], t['description'], t['color'])
        )

    conn.commit()
    cur.close()
    conn.close()


if __name__ == '__main__':
    run_migration()


