# database.py
import sqlite3
import json
from datetime import datetime, timedelta
from config import Config

class Database:
    def __init__(self):
        self.db_path = 'oee.db'
        self._init_database()  # Переименовали метод
    
    def _init_database(self):
        """Инициализация структуры БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Включаем foreign keys
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Таблица для сырых данных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS production_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ivams_total INTEGER,
                    hour_count INTEGER,
                    aux_count INTEGER,
                    production_delta INTEGER DEFAULT 0,
                    line_code TEXT DEFAULT 'LINE_5'
                )
            ''')
            
            # Таблица для OEE показателей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS oee_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    oee_percentage REAL,
                    availability REAL,
                    performance REAL,
                    quality REAL,
                    production_rate REAL
                )
            ''')
            
            # Таблица для сменных отчетов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_date DATE,
                    shift_number INTEGER,
                    line_code TEXT DEFAULT 'LINE_5',
                    total_production INTEGER,
                    planned_production INTEGER,
                    downtime_minutes INTEGER,
                    oee_percentage REAL,
                    availability REAL,
                    performance REAL,
                    quality REAL,
                    actual_production_rate REAL
                )
            ''')
            
            # Таблица для мониторинга простоев
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downtime_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    reason TEXT,
                    line_code TEXT DEFAULT 'LINE_5',
                    shift_number INTEGER,
                    resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Таблица для причин простоев (справочник)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downtime_reasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reason_code TEXT UNIQUE,
                    reason_name TEXT,
                    category TEXT,
                    line_code TEXT DEFAULT 'LINE_5'
                )
            ''')
            
            # Таблица для хранения почасовой мощности (НОВАЯ ТАБЛИЦА)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hourly_power (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    hour INTEGER,
                    power_value REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, hour)
                )
            ''')
            
            # Начальное заполнение справочника причин простоев
            cursor.execute('''
                INSERT OR IGNORE INTO downtime_reasons 
                (reason_code, reason_name, category) 
                VALUES 
                ('AUTO_DETECTED', 'Автоматически детектированный простой', 'Неопределенный'),
                ('MAINTENANCE', 'Плановое техническое обслуживание', 'Плановый'),
                ('MATERIAL_WAIT', 'Ожидание материалов', 'Организационный'),
                ('QUALITY_ISSUE', 'Проблемы с качеством', 'Технический')
            ''')

            # поминутка:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS minute_power (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    hour INTEGER,
                    minute INTEGER,
                    power_value REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, hour, minute)
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ База данных инициализирована успешно")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации БД: {e}")

    def save_production_data(self, data):
        """Сохранение данных производства"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем предыдущее значение для расчета дельты
            cursor.execute('''
                SELECT ivams_total FROM production_data 
                ORDER BY timestamp DESC LIMIT 1
            ''')
            last_row = cursor.fetchone()
            
            production_delta = 0
            if last_row and data.get('ivams_total'):
                production_delta = max(0, data['ivams_total'] - last_row[0])
            
            cursor.execute('''
                INSERT INTO production_data 
                (ivams_total, hour_count, aux_count, production_delta)
                VALUES (?, ?, ?, ?)
            ''', (
                data.get('ivams_total'), 
                data.get('hour_count'), 
                data.get('aux_count'), 
                production_delta
            ))
            
            conn.commit()
            conn.close()
            
            return production_delta
            
        except Exception as e:
            print(f"❌ Ошибка сохранения production_data: {e}")
            return 0

    def save_oee_metrics(self, oee_data):
        """Сохранение OEE показателей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO oee_metrics 
                (oee_percentage, availability, performance, quality, production_rate)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                oee_data.get('oee_percentage', 0),
                oee_data.get('availability', 0),
                oee_data.get('performance', 0),
                oee_data.get('quality', 0),
                oee_data.get('production_rate', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения OEE метрик: {e}")
            return False

    def save_downtime_event(self, downtime_data, shift_number):
        """Сохранение события простоя"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Преобразуем timestamp в datetime строку
            start_time = datetime.fromtimestamp(downtime_data['start_time']).isoformat()
            
            cursor.execute('''
                INSERT INTO downtime_events 
                (start_time, duration_seconds, reason, shift_number, line_code)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                start_time,
                downtime_data.get('duration', 0),
                downtime_data.get('reason', 'Неизвестно'),
                shift_number,
                'LINE_5'
            ))
            
            conn.commit()
            conn.close()
            print(f"✅ Сохранен простой: {downtime_data.get('reason', 'Неизвестно')}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения события простоя: {e}")
            return False

    def get_shift_data(self, shift_date, shift_number):
        """Получение данных по конкретной смене"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Упрощенный расчет времени смены
            if shift_number == 1:
                shift_start = f"{shift_date} 07:00:00"
                shift_end = f"{shift_date} 19:00:00"
            else:
                shift_start = f"{shift_date} 19:00:00"
                next_date = (datetime.strptime(shift_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                shift_end = f"{next_date} 07:00:00"
            
            cursor.execute('''
                SELECT 
                    SUM(production_delta) as total_production,
                    COUNT(*) as data_points
                FROM production_data 
                WHERE timestamp BETWEEN ? AND ?
            ''', (shift_start, shift_end))
            
            production_data = cursor.fetchone()
            
            # Получаем данные о простоях
            cursor.execute('''
                SELECT SUM(duration_seconds) as total_downtime
                FROM downtime_events 
                WHERE shift_number = ? 
                AND DATE(start_time) = ?
            ''', (shift_number, shift_date))
            
            downtime_data = cursor.fetchone()
            
            conn.close()
            
            result = {
                'total_production': production_data[0] or 0,
                'data_points': production_data[1] or 0,
                'downtime_minutes': (downtime_data[0] or 0) / 60
            }
            
            print(f"📊 Данные смены {shift_number} за {shift_date}: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Ошибка получения данных смены: {e}")
            return {
                'total_production': 0,
                'data_points': 0,
                'downtime_minutes': 0
            }

    def get_latest_data(self, limit=100):
        """Получение последних записей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    datetime(timestamp, 'localtime') as local_time,
                    ivams_total,
                    hour_count,
                    aux_count,
                    production_delta
                FROM production_data 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'timestamp': row[0],
                'ivams_total': row[1],
                'hour_count': row[2],
                'aux_count': row[3],
                'production_delta': row[4]
            } for row in rows]
        except Exception as e:
            print(f"❌ Ошибка получения последних данных: {e}")
            return []

    def get_oee_history(self, limit=50):
        """Получение истории OEE"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    datetime(timestamp, 'localtime') as local_time,
                    oee_percentage,
                    availability,
                    performance,
                    quality,
                    production_rate
                FROM oee_metrics 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'timestamp': row[0],
                'oee_percentage': row[1],
                'availability': row[2],
                'performance': row[3],
                'quality': row[4],
                'production_rate': row[5]
            } for row in rows]
        except Exception as e:
            print(f"❌ Ошибка получения истории OEE: {e}")
            return []
        
    def save_hourly_power(self, hour, power_value):
        """Сохранение почасовой мощности"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            # Проверяем, есть ли уже запись за этот час сегодня
            cursor.execute('''
                SELECT id FROM hourly_power 
                WHERE date = ? AND hour = ?
            ''', (today, hour))
            
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Обновляем существующую запись, если новая мощность больше
                cursor.execute('''
                    UPDATE hourly_power 
                    SET power_value = MAX(power_value, ?), timestamp = CURRENT_TIMESTAMP
                    WHERE date = ? AND hour = ?
                ''', (power_value, today, hour))
            else:
                # Вставляем новую запись
                cursor.execute('''
                    INSERT INTO hourly_power (date, hour, power_value)
                    VALUES (?, ?, ?)
                ''', (today, hour, power_value))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения почасовой мощности: {e}")
            return False

    def get_today_hourly_power(self):
        """Получение почасовой мощности за сегодня"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            cursor.execute('''
                SELECT hour, power_value 
                FROM hourly_power 
                WHERE date = ? 
                ORDER BY hour
            ''', (today,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Создаем массив на 24 часа с нулевыми значениями
            hourly_data = [0] * 24
            for hour, power in rows:
                if 0 <= hour < 24:
                    hourly_data[hour] = float(power) if power else 0
            
            return hourly_data
        except Exception as e:
            print(f"❌ Ошибка получения почасовой мощности: {e}")
            return [0] * 24

    def get_hourly_power_history(self, days=7):
        """Получение истории почасовой мощности за несколько дней"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
            
            cursor.execute('''
                SELECT date, hour, power_value 
                FROM hourly_power 
                WHERE date >= ? 
                ORDER BY date, hour
            ''', (start_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Группируем по дням
            history = {}
            for date, hour, power in rows:
                if date not in history:
                    history[date] = [0] * 24
                if 0 <= hour < 24:
                    history[date][hour] = float(power) if power else 0
            
            return history
        except Exception as e:
            print(f"❌ Ошибка получения истории почасовой мощности: {e}")
            return {}   

    def save_minute_power(self, hour, minute, power_value):
        """Сохранение поминутной мощности"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
                def get_today_minute_power(self):
        """Получение поминутной мощности за сегодня"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            cursor.execute('''
                SELECT hour, minute, power_value 
                FROM minute_power 
                WHERE date = ? 
                ORDER BY hour, minute
            ''', (today,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Создаем массив 24×60 с нулевыми значениями
            minute_data = [[0] * 60 for _ in range(24)]
            
            for hour, minute, power in rows:
                if 0 <= hour < 24 and 0 <= minute < 60:
                    minute_data[hour][minute] = float(power) if power else 0
            
            return minute_data
        except Exception as e:
            print(f"❌ Ошибка получения поминутной мощности: {e}")
            return [[0] * 60 for _ in range(24)]

    def get_minute_power_by_date(self, target_date):
        """Получение поминутной мощности за конкретную дату"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT hour, minute, power_value 
                FROM minute_power 
                WHERE date = ? 
                ORDER BY hour, minute
            ''', (target_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Создаем массив 24×60 с нулевыми значениями
            minute_data = [[0] * 60 for _ in range(24)]
            
            for hour, minute, power in rows:
                if 0 <= hour < 24 and 0 <= minute < 60:
                    minute_data[hour][minute] = float(power) if power else 0
            
            return minute_data
        except Exception as e:
            print(f"❌ Ошибка получения поминутной мощности за {target_date}: {e}")
            return [[0] * 60 for _ in range(24)]

    def get_available_dates(self):
        """Получение списка доступных дат с данными"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT date 
                FROM minute_power 
                ORDER BY date DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
        except Exception as e:
            print(f"❌ Ошибка получения списка дат: {e}")
            return []

    def get_hourly_power_by_date(self, target_date):
        """Получение почасовой мощности за конкретную дату"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT hour, power_value 
                FROM hourly_power 
                WHERE date = ? 
                ORDER BY hour
            ''', (target_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Создаем массив на 24 часа с нулевыми значениями
            hourly_data = [0] * 24
            for hour, power in rows:
                if 0 <= hour < 24:
                    hourly_data[hour] = float(power) if power else 0
            
            return hourly_data
        except Exception as e:
            print(f"❌ Ошибка получения почасовой мощности за {target_date}: {e}")
            return [0] * 24ив 24×60 с нулевыми значениями
            minute_data = [[0] * 60 for _ in range(24)]
            
            for hour, minute, power in rows:
                if 0 <= hour < 24 and 0 <= minute < 60:
                    minute_data[hour][minute] = float(power) if power else 0
            
            return minute_data
        except Exception as e:
            print(f"❌ Ошибка получения поминутной мощности: {e}")
            return [[0] * 60 for _ in range(24)]            