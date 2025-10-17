# config.py
import os
from datetime import time

class Config:
    # === Modbus настройки ===
    MODBUS_HOST = '10.0.0.175'
    MODBUS_PORT = 502
    MODBUS_DEVICE_ID = 175
    
    # Адреса счетчиков
    IVAMS_COUNTER_ADDR = 6000    # 32-битный общий счетчик (Big-endian)
    HOUR_COUNTER_ADDR = 6001     # 16-битный часовой счетчик
    AUX_COUNTER_ADDR = 6011      # 16-битный дополнительный счетчик
    
    # === Настройки линии ===
    LINE_NAME = "Линия 5"
    LINE_CODE = "LINE_5"
    
    # === Сменный режим ===
    SHIFTS = [
        {"start": time(7, 0), "end": time(19, 0), "number": 1},   # 1-я смена
        {"start": time(19, 0), "end": time(7, 0), "number": 2}    # 2-я смена
    ]
    
    # === Целевые показатели ===
    TARGET_PRODUCTION_RATE = 1000  # шт/час (плановый показатель) - ОСНОВНАЯ ПЕРЕМЕННАЯ!
    TARGET_SHIFT_PRODUCTION = 12000  # шт/смена (12 часов * 1000 шт/час)
    
    # === Настройки мониторинга простоев ===
    DOWNTIME_THRESHOLD = 3 * 60  # 3 минуты в секундах
    POLLING_INTERVAL = 3  # секунды между опросами
    
    # === Настройки OEE ===
    QUALITY_RATE = 0.98  # Плановый показатель качества (98%)
    
    # === Настройки БД ===
    DATABASE_URL = 'sqlite:///oee.db'
    
    # === Настройки Flask ===
    SECRET_KEY = 'your-secret-key-here'
    DEBUG = True