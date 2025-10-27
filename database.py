#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VKinder - модуль для работы с базой данных PostgreSQL
Содержит все функции для работы с пользователями, избранными и черным списком
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных"""

    def __init__(self, host, port, database, user, password):
        """Инициализация подключения к БД"""
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }

        self.connection = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Подключение к базе данных"""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.connection.autocommit = True
            logger.info("Успешное подключение к базе данных")
        except psycopg2.Error as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    def create_tables(self):
        """Создание таблиц в базе данных"""
        try:
            with self.connection.cursor() as cursor:
                # Таблица пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(100) NOT NULL,
                        last_name VARCHAR(100) NOT NULL,
                        age INTEGER,
                        city VARCHAR(100),
                        country VARCHAR(100),
                        sex INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Таблица избранных
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        candidate_id BIGINT NOT NULL,
                        first_name VARCHAR(100) NOT NULL,
                        last_name VARCHAR(100) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, candidate_id)
                    );
                """)

                # Таблица черного списка
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS blacklist (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        candidate_id BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, candidate_id)
                    );
                """)

                # Таблица истории просмотренных профилей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS viewed_profiles (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        candidate_id BIGINT NOT NULL,
                        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, candidate_id)
                    );
                """)

                # Индексы для оптимизации
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
                    CREATE INDEX IF NOT EXISTS idx_blacklist_user_id ON blacklist(user_id);
                    CREATE INDEX IF NOT EXISTS idx_viewed_profiles_user_id ON viewed_profiles(user_id);
                """)

                logger.info("Таблицы базы данных созданы успешно")

        except psycopg2.Error as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    def add_user(self, user_info: Dict) -> bool:
        """Добавление пользователя в базу данных"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (user_id, first_name, last_name, age, city, country, sex)
                    VALUES (%(id)s, %(first_name)s, %(last_name)s, %(age)s, %(city)s, %(country)s, %(sex)s)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        age = EXCLUDED.age,
                        city = EXCLUDED.city,
                        country = EXCLUDED.country,
                        sex = EXCLUDED.sex,
                        updated_at = CURRENT_TIMESTAMP;
                """, user_info)

                logger.info(f"Пользователь {user_info['id']} добавлен/обновлен в БД")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка добавления пользователя {user_info.get('id')}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM users WHERE user_id = %s;
                """, (user_id,))

                result = cursor.fetchone()
                return dict(result) if result else None

        except psycopg2.Error as e:
            logger.error(f"Ошибка получения пользователя {user_id}: {e}")
            return None

    def add_to_favorites(self, user_id: int, candidate_id: int, first_name: str = '', last_name: str = '') -> bool:
        """Добавление кандидата в избранное"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO favorites (user_id, candidate_id, first_name, last_name)
                    VALUES (%s, %s, %s, %s);
                """, (user_id, candidate_id, first_name, last_name))

                logger.info(f"Кандидат {candidate_id} добавлен в избранное пользователя {user_id}")
                return True

        except psycopg2.IntegrityError:
            logger.info(f"Кандидат {candidate_id} уже в избранном у пользователя {user_id}")
            return False
        except psycopg2.Error as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            return False

    def add_to_blacklist(self, user_id: int, candidate_id: int) -> bool:
        """Добавление кандидата в черный список"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO blacklist (user_id, candidate_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, candidate_id) DO NOTHING;
                """, (user_id, candidate_id))

                logger.info(f"Кандидат {candidate_id} добавлен в черный список пользователя {user_id}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка добавления в черный список: {e}")
            return False

    def add_to_viewed(self, user_id: int, candidate_id: int) -> bool:
        """Добавление кандидата в просмотренные"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO viewed_profiles (user_id, candidate_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, candidate_id) DO NOTHING;
                """, (user_id, candidate_id))

                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка добавления в просмотренные: {e}")
            return False

    def get_favorites(self, user_id: int) -> List[Dict]:
        """Получение списка избранных"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT candidate_id, first_name, last_name, created_at
                    FROM favorites 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC;
                """, (user_id,))

                return [dict(row) for row in cursor.fetchall()]

        except psycopg2.Error as e:
            logger.error(f"Ошибка получения избранных для пользователя {user_id}: {e}")
            return []

    def get_blacklist(self, user_id: int) -> List[int]:
        """Получение списка ID из черного списка"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT candidate_id FROM blacklist WHERE user_id = %s;
                """, (user_id,))

                return [row[0] for row in cursor.fetchall()]

        except psycopg2.Error as e:
            logger.error(f"Ошибка получения черного списка для пользователя {user_id}: {e}")
            return []

    def get_viewed_profiles(self, user_id: int) -> List[int]:
        """Получение списка просмотренных профилей"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT candidate_id FROM viewed_profiles WHERE user_id = %s;
                """, (user_id,))

                return [row[0] for row in cursor.fetchall()]

        except psycopg2.Error as e:
            logger.error(f"Ошибка получения просмотренных профилей для пользователя {user_id}: {e}")
            return []

    def clear_favorites(self, user_id: int) -> bool:
        """Очистка списка избранных"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM favorites WHERE user_id = %s;
                """, (user_id,))

                logger.info(f"Избранные очищены для пользователя {user_id}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка очистки избранных для пользователя {user_id}: {e}")
            return False

    def remove_from_favorites(self, user_id: int, candidate_id: int) -> bool:
        """Удаление из избранного"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM favorites WHERE user_id = %s AND candidate_id = %s;
                """, (user_id, candidate_id))

                logger.info(f"Кандидат {candidate_id} удален из избранного пользователя {user_id}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            return False

    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        try:
            with self.connection.cursor() as cursor:
                # Количество избранных
                cursor.execute("""
                    SELECT COUNT(*) FROM favorites WHERE user_id = %s;
                """, (user_id,))
                favorites_count = cursor.fetchone()[0]

                # Количество в черном списке
                cursor.execute("""
                    SELECT COUNT(*) FROM blacklist WHERE user_id = %s;
                """, (user_id,))
                blacklist_count = cursor.fetchone()[0]

                # Количество просмотренных
                cursor.execute("""
                    SELECT COUNT(*) FROM viewed_profiles WHERE user_id = %s;
                """, (user_id,))
                viewed_count = cursor.fetchone()[0]

                return {
                    'favorites_count': favorites_count,
                    'blacklist_count': blacklist_count,
                    'viewed_count': viewed_count
                }

        except psycopg2.Error as e:
            logger.error(f"Ошибка получения статистики для пользователя {user_id}: {e}")
            return {
                'favorites_count': 0,
                'blacklist_count': 0,
                'viewed_count': 0
            }

    def cleanup_old_viewed(self, days: int = 30):
        """Очистка старых просмотренных профилей"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM viewed_profiles 
                    WHERE viewed_at < NOW() - INTERVAL '%s days';
                """, (days,))

                deleted_count = cursor.rowcount
                logger.info(f"Удалено {deleted_count} старых записей просмотренных профилей")
                return deleted_count

        except psycopg2.Error as e:
            logger.error(f"Ошибка очистки старых просмотренных профилей: {e}")
            return 0

    def is_in_blacklist(self, user_id: int, candidate_id: int) -> bool:
        """Проверка, находится ли кандидат в черном списке"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM blacklist 
                    WHERE user_id = %s AND candidate_id = %s;
                """, (user_id, candidate_id))

                return cursor.fetchone() is not None

        except psycopg2.Error as e:
            logger.error(f"Ошибка проверки черного списка: {e}")
            return False

    def is_in_favorites(self, user_id: int, candidate_id: int) -> bool:
        """Проверка, находится ли кандидат в избранном"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM favorites 
                    WHERE user_id = %s AND candidate_id = %s;
                """, (user_id, candidate_id))

                return cursor.fetchone() is not None

        except psycopg2.Error as e:
            logger.error(f"Ошибка проверки избранного: {e}")
            return False

    def update_user_sex(self, user_id: int, sex: int) -> bool:
        """Обновление пола пользователя"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET sex = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (sex, user_id))

                logger.info(f"Пол пользователя {user_id} обновлён на {sex}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка обновления пола: {e}")
            return False

    def update_user_age(self, user_id: int, age: int) -> bool:
        """Обновление возраста пользователя"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET age = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (age, user_id))

                logger.info(f"Возраст пользователя {user_id} обновлён на {age}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка обновления возраста: {e}")
            return False

    def update_user_city(self, user_id: int, city: str) -> bool:
        """Обновление города пользователя"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET city = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (city, user_id))

                logger.info(f"Город пользователя {user_id} обновлён на {city}")
                return True

        except psycopg2.Error as e:
            logger.error(f"Ошибка обновления города: {e}")
            return False

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()
            logger.info("Соединение с базой данных закрыто")