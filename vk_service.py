#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VKinder - модуль для работы с VK API
Содержит функции для поиска людей, получения информации и фотографий
"""

import vk_api
import logging
import time
import random
from typing import List, Dict, Optional
from config import SEARCH_CONFIG, CITIES, PREFERRED_STATUSES, VK_API_VERSION

logger = logging.getLogger(__name__)


class VKService:
    """Класс для работы с VK API"""

    def __init__(self, vk_session, user_session=None):
        """Инициализация сервиса VK API"""
        self.vk_session = vk_session
        self.vk = vk_session.get_api()

        # Для поиска используем пользовательский токен
        self.user_session = user_session if user_session else vk_session
        self.vk_user = self.user_session.get_api()

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            response = self.vk.users.get(
                user_ids=user_id,
                fields='bdate,city,country,sex',
                v=VK_API_VERSION
            )

            if not response:
                logger.error(f"Пользователь {user_id} не найден")
                return None

            user = response[0]

            # Вычисляем возраст из даты рождения
            age = self._calculate_age(user.get('bdate'))

            user_info = {
                'id': user['id'],
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
                'age': age,
                'city': user.get('city', {}).get('title', '') if user.get('city') else '',
                'country': user.get('country', {}).get('title', '') if user.get('country') else '',
                'sex': user.get('sex', 0)  # 1-женщина, 2-мужчина
            }

            logger.info(f"Получена информация о пользователе {user_id}")
            return user_info

        except vk_api.ApiError as e:
            logger.error(f"Ошибка VK API при получении пользователя {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении пользователя {user_id}: {e}")
            return None

    def search_people(self, user_info: Dict) -> List[Dict]:
        """Поиск людей для знакомства"""
        try:
            # Логируем исходные данные пользователя
            logger.info(
                f"Поиск для пользователя: пол={user_info.get('sex')}, возраст={user_info.get('age')}, город='{user_info.get('city')}'")

            # Определяем параметры поиска
            search_params = self._build_search_params(user_info)

            logger.info(f"Поиск людей с параметрами: {search_params}")

            # Выполняем поиск используя пользовательский токен
            response = self.vk_user.users.search(
                **search_params,
                v=VK_API_VERSION
            )

            if not response or 'items' not in response:
                logger.warning("Пустой результат поиска")
                return []

            candidates = []
            for user in response['items']:
                # Пропускаем заблокированных и удаленных пользователей
                if user.get('deactivated'):
                    continue

                # Проверяем наличие фото профиля
                if not user.get('photo_100') or 'camera' in user.get('photo_100', ''):
                    continue

                candidate = {
                    'id': user['id'],
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'age': self._calculate_age(user.get('bdate')),
                    'city': user.get('city', {}).get('title', '') if user.get('city') else '',
                    'sex': user.get('sex', 0)
                }

                candidates.append(candidate)

            # Перемешиваем результаты для разнообразия
            random.shuffle(candidates)

            logger.info(f"Найдено {len(candidates)} кандидатов")
            return candidates[:50]  # Ограничиваем количество

        except vk_api.ApiError as e:
            logger.error(f"Ошибка VK API при поиске людей: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске людей: {e}")
            return []

    def get_popular_photos(self, user_id: int) -> List[Dict]:
        """Получение популярных фотографий пользователя"""
        try:
            # Получаем фотографии профиля используя пользовательский токен
            response = self.vk_user.photos.get(
                owner_id=user_id,
                album_id='profile',
                extended=1,
                photo_sizes=1,
                count=200,  # Максимальное количество
                v=VK_API_VERSION
            )

            if not response or 'items' not in response:
                logger.warning(f"Нет фотографий у пользователя {user_id}")
                return []

            photos = response['items']

            # Сортируем по популярности (лайки + комментарии)
            photos.sort(key=lambda x: x.get('likes', {}).get('count', 0) +
                                      x.get('comments', {}).get('count', 0),
                        reverse=True)

            # Фильтруем фотографии с минимальным количеством лайков
            min_likes = SEARCH_CONFIG.get('min_photo_likes', 1)
            popular_photos = [
                photo for photo in photos
                if photo.get('likes', {}).get('count', 0) >= min_likes
            ]

            # Если популярных фото мало, берем любые
            if len(popular_photos) < 3 and photos:
                popular_photos = photos

            logger.info(f"Найдено {len(popular_photos)} фотографий для пользователя {user_id}")
            return popular_photos[:SEARCH_CONFIG.get('max_photos', 3)]

        except vk_api.ApiError as e:
            if e.code == 30:  # Профиль приватный
                logger.info(f"Приватный профиль {user_id}")
            else:
                logger.error(f"Ошибка VK API при получении фото {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении фото {user_id}: {e}")
            return []

    def _build_search_params(self, user_info: Dict) -> Dict:
        """Построение параметров поиска"""
        params = {
            'count': SEARCH_CONFIG.get('count', 100),
            'fields': 'bdate,city,photo_100,sex',
            'has_photo': 1,  # Только с фотографией
            'sort': 0,  # По популярности
            'country': 1  # ВАЖНО: 1 = Россия (без этого ищет по всему миру!)
        }

        # Определяем пол для поиска (ищем противоположный)
        user_sex = user_info.get('sex', 0)
        if user_sex == 1:  # Если пользователь женщина, ищем мужчин
            params['sex'] = 2
        elif user_sex == 2:  # Если пользователь мужчина, ищем женщин
            params['sex'] = 1
        # Если пол не указан, ищем всех

        # Возраст
        user_age = user_info.get('age')
        if user_age:
            age_range = SEARCH_CONFIG.get('age_range', 5)
            params['age_from'] = max(18, user_age - age_range)
            params['age_to'] = min(80, user_age + age_range)
        else:
            params['age_from'] = 18
            params['age_to'] = 35

        # ВАЖНО: Город берём из настроек пользователя (из БД)
        city = user_info.get('city', '').lower().strip()

        # Приводим название города к стандартному виду
        city_normalized = city.replace('ё', 'е')  # ёлка -> елка

        # Логируем для отладки
        logger.info(f"Город пользователя: '{city}' (normalized: '{city_normalized}')")
        logger.info(f"Доступные города: {list(CITIES.keys())[:10]}...")  # Показываем первые 10

        # Ищем город в словаре (регистронезависимо)
        city_id = None
        for city_name, cid in CITIES.items():
            if city_normalized == city_name or city == city_name:
                city_id = cid
                logger.info(f"✅ Найден город: {city_name} (ID: {cid})")
                break

        if city_id:
            params['city'] = city_id
            logger.info(f"🔍 Поиск в городе ID: {city_id} (страна: Россия)")
        else:
            # Если город не найден - НЕ указываем city, только country (вся Россия)
            logger.warning(f"⚠️ Город '{city}' не найден в CITIES, ищем по всей России")

        return params

    def _calculate_age(self, bdate: str) -> Optional[int]:
        """Вычисление возраста из даты рождения"""
        if not bdate:
            return None

        try:
            # Формат даты: DD.MM.YYYY или DD.MM
            date_parts = bdate.split('.')
            if len(date_parts) < 3:
                return None

            birth_year = int(date_parts[2])
            current_year = time.localtime().tm_year

            age = current_year - birth_year

            # Проверяем корректность возраста
            if 10 <= age <= 100:
                return age

            return None

        except (ValueError, IndexError):
            return None

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            response = self.vk.users.get(
                user_ids=user_id,
                fields='bdate,city,country,sex',
                v=VK_API_VERSION
            )

            if not response:
                logger.error(f"Пользователь {user_id} не найден")
                return None

            user = response[0]

            # Вычисляем возраст из даты рождения
            age = self._calculate_age(user.get('bdate'))

            user_info = {
                'id': user['id'],
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
                'age': age,
                'city': user.get('city', {}).get('title', '') if user.get('city') else '',
                'country': user.get('country', {}).get('title', '') if user.get('country') else '',
                'sex': user.get('sex', 0)  # 1-женщина, 2-мужчина
            }

            logger.info(f"Получена информация о пользователе {user_id}")
            return user_info

        except vk_api.ApiError as e:
            logger.error(f"Ошибка VK API при получении пользователя {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении пользователя {user_id}: {e}")
            return None

    def search_people(self, user_info: Dict) -> List[Dict]:
        """Поиск людей для знакомства"""
        try:
            # Определяем параметры поиска
            search_params = self._build_search_params(user_info)

            logger.info(f"Поиск людей с параметрами: {search_params}")

            # Выполняем поиск используя пользовательский токен
            response = self.vk_user.users.search(
                **search_params,
                v=VK_API_VERSION
            )

            if not response or 'items' not in response:
                logger.warning("Пустой результат поиска")
                return []

            candidates = []
            for user in response['items']:
                # Пропускаем заблокированных и удаленных пользователей
                if user.get('deactivated'):
                    continue

                # Проверяем наличие фото профиля
                if not user.get('photo_100') or 'camera' in user.get('photo_100', ''):
                    continue

                candidate = {
                    'id': user['id'],
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'age': self._calculate_age(user.get('bdate')),
                    'city': user.get('city', {}).get('title', '') if user.get('city') else '',
                    'sex': user.get('sex', 0)
                }

                candidates.append(candidate)

            # Перемешиваем результаты для разнообразия
            random.shuffle(candidates)

            logger.info(f"Найдено {len(candidates)} кандидатов")
            return candidates[:50]  # Ограничиваем количество

        except vk_api.ApiError as e:
            logger.error(f"Ошибка VK API при поиске людей: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске людей: {e}")
            return []

    def get_popular_photos(self, user_id: int) -> List[Dict]:
        """Получение популярных фотографий пользователя"""
        try:
            # Получаем фотографии профиля используя пользовательский токен
            response = self.vk_user.photos.get(
                owner_id=user_id,
                album_id='profile',
                extended=1,
                photo_sizes=1,
                count=200,  # Максимальное количество
                v=VK_API_VERSION
            )

            if not response or 'items' not in response:
                logger.warning(f"Нет фотографий у пользователя {user_id}")
                return []

            photos = response['items']

            # Сортируем по популярности (лайки + комментарии)
            photos.sort(key=lambda x: x.get('likes', {}).get('count', 0) +
                                      x.get('comments', {}).get('count', 0),
                        reverse=True)

            # Фильтруем фотографии с минимальным количеством лайков
            min_likes = SEARCH_CONFIG.get('min_photo_likes', 1)
            popular_photos = [
                photo for photo in photos
                if photo.get('likes', {}).get('count', 0) >= min_likes
            ]

            # Если популярных фото мало, берем любые
            if len(popular_photos) < 3 and photos:
                popular_photos = photos

            logger.info(f"Найдено {len(popular_photos)} фотографий для пользователя {user_id}")
            return popular_photos[:SEARCH_CONFIG.get('max_photos', 3)]

        except vk_api.ApiError as e:
            if e.code == 30:  # Профиль приватный
                logger.info(f"Приватный профиль {user_id}")
            else:
                logger.error(f"Ошибка VK API при получении фото {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении фото {user_id}: {e}")
            return []

    def _build_search_params(self, user_info: Dict) -> Dict:
        """Построение параметров поиска"""
        params = {
            'count': SEARCH_CONFIG.get('count', 100),
            'fields': 'bdate,city,photo_100,sex',
            'has_photo': 1,  # Только с фотографией
            'sort': 0  # По популярности
        }

        # Определяем пол для поиска (ищем противоположный)
        user_sex = user_info.get('sex', 0)
        if user_sex == 1:  # Если пользователь женщина, ищем мужчин
            params['sex'] = 2
        elif user_sex == 2:  # Если пользователь мужчина, ищем женщин
            params['sex'] = 1
        # Если пол не указан, ищем всех

        # Возраст
        user_age = user_info.get('age')
        if user_age:
            age_range = SEARCH_CONFIG.get('age_range', 5)
            params['age_from'] = max(18, user_age - age_range)
            params['age_to'] = min(80, user_age + age_range)
        else:
            params['age_from'] = 18
            params['age_to'] = 35

        # Город
        city = user_info.get('city', '').lower()
        if city and city in CITIES:
            params['city'] = CITIES[city]

        return params

    def _calculate_age(self, bdate: str) -> Optional[int]:
        """Вычисление возраста из даты рождения"""
        if not bdate:
            return None

        try:
            # Формат даты: DD.MM.YYYY или DD.MM
            date_parts = bdate.split('.')
            if len(date_parts) < 3:
                return None

            birth_year = int(date_parts[2])
            current_year = time.localtime().tm_year

            age = current_year - birth_year

            # Проверяем корректность возраста
            if 10 <= age <= 100:
                return age

            return None

        except (ValueError, IndexError):
            return None


def test_vk_service():
    """Функция для тестирования VK сервиса"""
    import vk_api
    from config import VK_GROUP_TOKEN, VK_USER_TOKEN

    try:
        # Инициализация
        vk_session = vk_api.VkApi(token=VK_GROUP_TOKEN)
        user_session = vk_api.VkApi(token=VK_USER_TOKEN)
        vk_service = VKService(vk_session, user_session)

        print("🔍 Тестирование VK Service...")

        # Тест получения информации о пользователе
        print("1. Тест получения информации о пользователе...")
        user_info = vk_service.get_user_info(1)  # Pavel Durov
        if user_info:
            print(f"   ✅ Пользователь: {user_info['first_name']} {user_info['last_name']}")
        else:
            print("   ❌ Не удалось получить информацию")

        # Тест поиска людей
        if user_info:
            print("2. Тест поиска людей...")
            candidates = vk_service.search_people(user_info)
            print(f"   ✅ Найдено кандидатов: {len(candidates)}")

            if candidates:
                # Тест получения фотографий
                print("3. Тест получения фотографий...")
                photos = vk_service.get_popular_photos(candidates[0]['id'])
                print(f"   ✅ Найдено фотографий: {len(photos)}")

        print("🎉 Тестирование завершено!")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")


if __name__ == "__main__":
    test_vk_service()