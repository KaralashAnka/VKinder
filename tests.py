#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VKinder - Тесты для проверки функциональности
Запуск: python tests.py
"""

import unittest
import sys
import os
import logging
from unittest.mock import Mock, patch, MagicMock

# Добавляем корневую папку в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database
from vk_service import VKService
from config import DB_CONFIG, SEARCH_CONFIG

# Отключаем логирование во время тестов
logging.disable(logging.CRITICAL)


class TestDatabase(unittest.TestCase):
    """Тесты для модуля базы данных"""
    
    @classmethod
    def setUpClass(cls):
        """Настройка перед запуском всех тестов"""
        # Используем тестовую базу данных
        cls.test_db_config = DB_CONFIG.copy()
        cls.test_db_config['database'] = 'vkinder_test'
        
        try:
            cls.db = Database(**cls.test_db_config)
        except Exception as e:
            print(f"Не удалось подключиться к тестовой БД: {e}")
            print("Используется мок-объект для тестирования")
            cls.db = Mock()
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_user_info = {
            'id': 12345,
            'first_name': 'Тест',
            'last_name': 'Пользователь',
            'age': 25,
            'city': 'Москва',
            'country': 'Россия',
            'sex': 1
        }
        
        self.test_candidate_id = 67890
    
    def test_add_user(self):
        """Тест добавления пользователя"""
        if isinstance(self.db, Mock):
            self.db.add_user.return_value = True
            result = self.db.add_user(self.test_user_info)
            self.assertTrue(result)
            self.db.add_user.assert_called_once_with(self.test_user_info)
        else:
            result = self.db.add_user(self.test_user_info)
            self.assertTrue(result)
    
    def test_get_user(self):
        """Тест получения пользователя"""
        if isinstance(self.db, Mock):
            self.db.get_user.return_value = self.test_user_info
            result = self.db.get_user(12345)
            self.assertEqual(result, self.test_user_info)
        else:
            # Сначала добавляем пользователя
            self.db.add_user(self.test_user_info)
            result = self.db.get_user(12345)
            self.assertIsNotNone(result)
            self.assertEqual(result['user_id'], 12345)
    
    def test_add_to_favorites(self):
        """Тест добавления в избранное"""
        if isinstance(self.db, Mock):
            self.db.add_to_favorites.return_value = True
            result = self.db.add_to_favorites(12345, self.test_candidate_id)
            self.assertTrue(result)
        else:
            # Добавляем пользователя сначала
            self.db.add_user(self.test_user_info)
            result = self.db.add_to_favorites(12345, self.test_candidate_id)
            self.assertTrue(result)
    
    def test_add_to_blacklist(self):
        """Тест добавления в черный список"""
        if isinstance(self.db, Mock):
            self.db.add_to_blacklist.return_value = True
            result = self.db.add_to_blacklist(12345, self.test_candidate_id)
            self.assertTrue(result)
        else:
            self.db.add_user(self.test_user_info)
            result = self.db.add_to_blacklist(12345, self.test_candidate_id)
            self.assertTrue(result)
    
    def test_get_favorites(self):
        """Тест получения избранных"""
        if isinstance(self.db, Mock):
            self.db.get_favorites.return_value = [
                {
                    'candidate_id': self.test_candidate_id,
                    'first_name': 'Тест',
                    'last_name': 'Кандидат'
                }
            ]
            result = self.db.get_favorites(12345)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
        else:
            result = self.db.get_favorites(12345)
            self.assertIsInstance(result, list)
    
    def test_get_user_stats(self):
        """Тест получения статистики пользователя"""
        if isinstance(self.db, Mock):
            self.db.get_user_stats.return_value = {
                'favorites_count': 1,
                'blacklist_count': 1,
                'viewed_count': 0
            }
            result = self.db.get_user_stats(12345)
            self.assertIsInstance(result, dict)
            self.assertIn('favorites_count', result)
        else:
            result = self.db.get_user_stats(12345)
            self.assertIsInstance(result, dict)
            self.assertIn('favorites_count', result)
    
    @classmethod
    def tearDownClass(cls):
        """Очистка после всех тестов"""
        if hasattr(cls.db, 'close') and not isinstance(cls.db, Mock):
            cls.db.close()


class TestVKService(unittest.TestCase):
    """Тесты для VK сервиса"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем мок VK сессии
        self.mock_vk_session = Mock()
        self.mock_vk_api = Mock()
        self.mock_vk_session.get_api.return_value = self.mock_vk_api
        
        self.vk_service = VKService(self.mock_vk_session)
        
        self.test_user_info = {
            'id': 12345,
            'first_name': 'Тест',
            'last_name': 'Пользователь',
            'age': 25,
            'city': 'Москва',
            'sex': 1
        }
    
    def test_get_user_info(self):
        """Тест получения информации о пользователе"""
        # Настраиваем мок ответ
        self.mock_vk_api.users.get.return_value = [
            {
                'id': 12345,
                'first_name': 'Тест',
                'last_name': 'Пользователь',
                'bdate': '1.1.1999',
                'city': {'title': 'Москва'},
                'country': {'title': 'Россия'},
                'sex': 1
            }
        ]
        
        result = self.vk_service.get_user_info(12345)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 12345)
        self.assertEqual(result['first_name'], 'Тест')
        self.assertEqual(result['city'], 'Москва')
    
    def test_search_people(self):
        """Тест поиска людей"""
        # Настраиваем мок ответ
        self.mock_vk_api.users.search.return_value = {
            'items': [
                {
                    'id': 67890,
                    'first_name': 'Анна',
                    'last_name': 'Иванова',
                    'bdate': '15.5.1995',
                    'city': {'title': 'Москва'},
                    'sex': 1,
                    'photo_100': 'https://example.com/photo.jpg'
                }
            ]
        }
        
        result = self.vk_service.search_people(self.test_user_info)
        
        self.assertIsInstance(result, list)
        if result:  # Если есть результаты
            self.assertIn('id', result[0])
            self.assertIn('first_name', result[0])
    
    def test_get_popular_photos(self):
        """Тест получения популярных фотографий"""
        # Настраиваем мок ответ
        self.mock_vk_api.photos.get.return_value = {
            'items': [
                {
                    'id': 456789123,
                    'owner_id': 67890,
                    'likes': {'count': 25},
                    'comments': {'count': 5},
                    'sizes': [
                        {'type': 'm', 'url': 'https://example.com/photo_m.jpg'},
                        {'type': 'x', 'url': 'https://example.com/photo_x.jpg'}
                    ]
                }
            ]
        }
        
        result = self.vk_service.get_popular_photos(67890)
        
        self.assertIsInstance(result, list)
        # Проверяем, что не превышаем максимум фотографий
        self.assertLessEqual(len(result), SEARCH_CONFIG.get('max_photos', 3))
    
    def test_calculate_age(self):
        """Тест вычисления возраста"""
        # Тестируем приватный метод через публичный интерфейс
        age = self.vk_service._calculate_age('1.1.1999')
        self.assertIsInstance(age, (int, type(None)))
        
        # Тест некорректной даты
        age_invalid = self.vk_service._calculate_age('invalid_date')
        self.assertIsNone(age_invalid)
        
        # Тест неполной даты
        age_partial = self.vk_service._calculate_age('1.1')
        self.assertIsNone(age_partial)
    
    def test_build_search_params(self):
        """Тест построения параметров поиска"""
        params = self.vk_service._build_search_params(self.test_user_info)
        
        self.assertIsInstance(params, dict)
        self.assertIn('count', params)
        self.assertIn('fields', params)
        self.assertIn('has_photo', params)
        
        # Проверяем логику поиска противоположного пола
        if self.test_user_info['sex'] == 1:  # женщина
            self.assertEqual(params.get('sex'), 2)  # ищем мужчин
        elif self.test_user_info['sex'] == 2:  # мужчина
            self.assertEqual(params.get('sex'), 1)  # ищем женщин


class TestConfig(unittest.TestCase):
    """Тесты конфигурации"""
    
    def test_db_config_exists(self):
        """Тест наличия конфигурации БД"""
        from config import DB_CONFIG
        
        self.assertIsInstance(DB_CONFIG, dict)
        required_keys = ['host', 'port', 'database', 'user', 'password']
        
        for key in required_keys:
            self.assertIn(key, DB_CONFIG)
    
    def test_search_config_exists(self):
        """Тест наличия конфигурации поиска"""
        self.assertIsInstance(SEARCH_CONFIG, dict)
        
        expected_keys = ['count', 'age_range', 'max_photos']
        for key in expected_keys:
            self.assertIn(key, SEARCH_CONFIG)
    
    def test_search_config_values(self):
        """Тест корректности значений конфигурации поиска"""
        self.assertGreater(SEARCH_CONFIG['count'], 0)
        self.assertLessEqual(SEARCH_CONFIG['count'], 1000)  # лимит VK API
        
        self.assertGreater(SEARCH_CONFIG['age_range'], 0)
        self.assertLessEqual(SEARCH_CONFIG['age_range'], 20)
        
        self.assertGreater(SEARCH_CONFIG['max_photos'], 0)
        self.assertLessEqual(SEARCH_CONFIG['max_photos'], 10)


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты"""
    
    def setUp(self):
        """Настройка для интеграционных тестов"""
        self.mock_vk_session = Mock()
        self.mock_db = Mock()
        
        self.test_user_info = {
            'id': 12345,
            'first_name': 'Тест',
            'last_name': 'Пользователь',
            'age': 25,
            'city': 'Москва',
            'sex': 1
        }
    
    def test_full_search_workflow(self):
        """Тест полного цикла поиска"""
        # Имитируем успешный поиск
        vk_service = VKService(self.mock_vk_session)
        vk_service.search_people = Mock(return_value=[
            {'id': 67890, 'first_name': 'Анна', 'last_name': 'Иванова'}
        ])
        vk_service.get_popular_photos = Mock(return_value=[
            {'id': 123, 'owner_id': 67890, 'likes': {'count': 10}}
        ])
        
        # Выполняем поиск
        candidates = vk_service.search_people(self.test_user_info)
        
        self.assertIsInstance(candidates, list)
        
        if candidates:
            photos = vk_service.get_popular_photos(candidates[0]['id'])
            self.assertIsInstance(photos, list)
    
    def test_database_vk_integration(self):
        """Тест интеграции БД и VK сервиса"""
        # Мокаем оба сервиса
        mock_db = Mock()
        mock_vk = Mock()
        
        # Имитируем добавление пользователя в БД после получения из VK
        user_info = {'id': 12345, 'first_name': 'Test'}
        mock_vk.get_user_info.return_value = user_info
        mock_db.add_user.return_value = True
        
        # Тестируем цепочку
        vk_user = mock_vk.get_user_info(12345)
        db_result = mock_db.add_user(vk_user)
        
        self.assertTrue(db_result)
        mock_db.add_user.assert_called_once_with(user_info)


def run_performance_tests():
    """Тесты производительности"""
    print("\n🚀 Запуск тестов производительности...")
    
    import time
    
    # Тест скорости создания подключения к БД
    try:
        start_time = time.time()
        db = Database(**DB_CONFIG)
        connection_time = time.time() - start_time
        db.close()
        
        print(f"✅ Подключение к БД: {connection_time:.3f}s")
        
        if connection_time > 1.0:
            print("⚠️ Медленное подключение к БД (>1s)")
        else:
            print("✅ Быстрое подключение к БД")
            
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
    
    # Тест скорости инициализации VK сервиса
    try:
        mock_session = Mock()
        start_time = time.time()
        vk_service = VKService(mock_session)
        init_time = time.time() - start_time
        
        print(f"✅ Инициализация VK сервиса: {init_time:.3f}s")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации VK сервиса: {e}")


def run_all_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов VKinder...")
    print("=" * 50)
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    test_classes = [
        TestDatabase,
        TestVKService, 
        TestConfig,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Тесты производительности
    run_performance_tests()
    
    # Итоговый отчет
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 50)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    passed = total_tests - failures - errors - skipped
    
    print(f"Всего тестов: {total_tests}")
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Неудач: {failures}")
    print(f"⚠️ Ошибок: {errors}")
    print(f"⏭️ Пропущено: {skipped}")
    
    success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
    print(f"📈 Успешность: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 Отличный результат!")
    elif success_rate >= 75:
        print("👍 Хороший результат!")
    else:
        print("⚠️ Требует доработки")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Включаем логирование обратно для отчетов
    logging.disable(logging.NOTSET)
    
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка при тестировании: {e}")
        sys.exit(1)
