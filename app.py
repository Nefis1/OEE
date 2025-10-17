# app.py (с добавленными изменениями)
from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from datetime import datetime, timedelta
import threading
import time
from database import Database
from modbus_client import ProductionMonitor
from models import ShiftManager, OEECalculator, DowntimeMonitor
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация компонентов
db = Database()
monitor = ProductionMonitor()
downtime_monitor = DowntimeMonitor()
oee_calculator = OEECalculator()

# Глобальные переменные для хранения текущего состояния
current_state = {
    'production_data': {},
    'oee_data': {},
    'downtime_status': {'is_downtime': False, 'info': None},
    'shift_info': {},
    'last_update': ''
}

def background_monitoring():
    """Фоновая задача для мониторинга оборудования"""
    while True:
        try:
            # Получаем текущие данные
            production_data = monitor.get_production_data()
            
            if production_data and production_data['success']:
                try:
                    # Сохраняем в БД
                    production_delta = db.save_production_data(production_data)
                except Exception as db_error:
                    print(f"❌ Ошибка сохранения в БД: {db_error}")
                    production_delta = 0
                
                # Проверяем простой
                is_downtime, downtime_info = downtime_monitor.check_downtime(
                    production_data['ivams_total'], 
                    datetime.now().timestamp()
                )
                
                # Получаем информацию о текущей смене
                current_shift = ShiftManager.get_current_shift()
                
                # Рассчитываем OEE (упрощенный расчет для теста)
                test_production = 1 if production_delta == 0 else production_delta
                
                oee_data = oee_calculator.calculate_oee(
                    actual_production=test_production,
                    planned_production=Config.TARGET_PRODUCTION_RATE / 20,
                    operating_time=3,
                    available_time=3
                )
                
                # РАСЧЕТ И СОХРАНЕНИЕ ПОЧАСОВОЙ МОЩНОСТИ
                current_hour = datetime.now().hour
                current_power = 0
                
                # Используем production_delta для расчета мощности
                if production_delta > 0:
                    current_power = production_delta * 20  # Переводим в шт/мин
                
                # Сохраняем почасовую мощность в БД
                if current_power > 0:
                    db.save_hourly_power(current_hour, current_power)

                # После расчета current_power добавьте:
                current_time = datetime.now()
                current_hour = current_time.hour
                current_minute = current_time.minute

                # Сохраняем поминутную мощность
                if current_power > 0:
                    db.save_minute_power(current_hour, current_minute, current_power)    
                
                # Сохраняем OEE метрики
                if oee_data:
                    try:
                        db.save_oee_metrics(oee_data)
                    except Exception as e:
                        print(f"❌ Ошибка сохранения OEE: {e}")
                
                # Обновляем глобальное состояние с безопасными данными
                current_state['production_data'] = production_data
                current_state['oee_data'] = oee_data or {
                    'oee_percentage': 0,
                    'availability': 0, 
                    'performance': 0,
                    'quality': 0,
                    'production_rate': 0
                }
                current_state['downtime_status'] = {
                    'is_downtime': is_downtime,
                    'info': str(downtime_info) if downtime_info else None
                }
                current_state['shift_info'] = current_shift
                current_state['last_update'] = datetime.now().isoformat()
                
                # Сохраняем событие простоя
                if is_downtime and downtime_info and current_shift:
                    try:
                        db.save_downtime_event(
                            downtime_info, 
                            current_shift['number']
                        )
                    except Exception as e:
                        print(f"❌ Ошибка сохранения простоя: {e}")
            else:
                # Тестовые данные если оборудование не отвечает
                current_shift = ShiftManager.get_current_shift()
                current_state['production_data'] = {
                    'ivams_total': 2265349,
                    'hour_count': 37094,
                    'aux_count': 1414,
                    'success': False
                }
                current_state['oee_data'] = {
                    'oee_percentage': 78.5,
                    'availability': 85.0,
                    'performance': 92.1,
                    'quality': 98.0,
                    'production_rate': 850
                }
                current_state['downtime_status'] = {
                    'is_downtime': False,
                    'info': None
                }
                current_state['shift_info'] = current_shift
                current_state['last_update'] = datetime.now().isoformat()
            
            time.sleep(Config.POLLING_INTERVAL)
            
        except Exception as e:
            print(f"❌ Ошибка в фоновом мониторинге: {e}")
            current_state['last_update'] = datetime.now().isoformat()
            time.sleep(5)

# Запускаем фоновый мониторинг
monitor_thread = threading.Thread(target=background_monitoring, daemon=True)
monitor_thread.start()

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Главная страница dashboard"""
    return render_template('index.html', 
                         line_name=Config.LINE_NAME,
                         target_rate=Config.TARGET_PRODUCTION_RATE)

@app.route('/api/current_data')
def get_current_data():
    """API для получения текущих данных"""
    try:
        # Создаем безопасную копию для JSON сериализации
        safe_state = {}
        
        for key, value in current_state.items():
            if value is None:
                safe_state[key] = None
            elif hasattr(value, 'isoformat'):  # Для datetime, time объектов
                safe_state[key] = value.isoformat()
            elif isinstance(value, dict):
                # Рекурсивно обрабатываем словари
                safe_state[key] = {}
                for k, v in value.items():
                    if hasattr(v, 'isoformat'):
                        safe_state[key][k] = v.isoformat()
                    else:
                        safe_state[key][k] = v
            else:
                safe_state[key] = value
        
        return jsonify(safe_state)
    except Exception as e:
        print(f"Ошибка сериализации JSON: {e}")
        return jsonify({'error': 'Data serialization error'})

@app.route('/api/production_history')
def get_production_history():
    """API для получения исторических данных производства"""
    limit = request.args.get('limit', 100, type=int)
    data = db.get_latest_data(limit)
    return jsonify(data)

@app.route('/api/oee_history')
def get_oee_history():
    """API для получения истории OEE"""
    limit = request.args.get('limit', 50, type=int)
    data = db.get_oee_history(limit)
    return jsonify(data)

@app.route('/api/shift_data')
def get_shift_data():
    """API для получения данных по смене"""
    try:
        shift_date = request.args.get('date', '')
        shift_number_str = request.args.get('shift', '')
        
        # Проверяем и преобразуем параметры
        if not shift_date:
            shift_date = datetime.now().date().isoformat()
            
        if shift_number_str:
            shift_number = int(shift_number_str)
        else:
            current_shift = ShiftManager.get_current_shift()
            if current_shift and isinstance(current_shift, dict):
                shift_number = current_shift.get('number', 1)
            else:
                shift_number = 1
        
        data = db.get_shift_data(shift_date, shift_number)
        return jsonify(data)
    except Exception as e:
        print(f"Ошибка в get_shift_data: {e}")
        return jsonify({
            'total_production': 0,
            'data_points': 0,
            'downtime_minutes': 0
        })

@app.route('/api/hourly_power')
def get_hourly_power():
    """API для получения почасовой мощности за сегодня"""
    try:
        hourly_data = db.get_today_hourly_power()
        return jsonify({
            'hourly_power': hourly_data,
            'current_hour': datetime.now().hour
        })
    except Exception as e:
        print(f"Ошибка получения почасовой мощности: {e}")
        return jsonify({'hourly_power': [0]*24, 'current_hour': 0})

@app.route('/api/update_downtime_reason', methods=['POST'])
def update_downtime_reason():
    """API для обновления причины простоя"""
    try:
        # Получаем данные с проверкой
        data = request.get_json(silent=True) or {}
        reason = data.get('reason')
        
        if reason:
            downtime_monitor.add_downtime_reason(reason)
            return jsonify({'success': True, 'message': f'Причина простоя обновлена: {reason}'})
        else:
            return jsonify({'success': False, 'error': 'No reason provided'})
            
    except Exception as e:
        print(f"❌ Ошибка обновления причины простоя: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'})

@app.route('/api/system_info')
def get_system_info():
    """API для получения информации о системе"""
    return jsonify({
        'line_name': Config.LINE_NAME,
        'target_production_rate': Config.TARGET_PRODUCTION_RATE,
        'shift_duration': '12 часов',
        'downtime_threshold': f"{Config.DOWNTIME_THRESHOLD} секунд",
        'polling_interval': f"{Config.POLLING_INTERVAL} секунд"
    })

@app.route('/api/test_data')
def test_data():
    """Тестовые данные для отладки"""
    return jsonify({
        'production_data': {
            'ivams_total': 2265349,
            'hour_count': 37094,
            'aux_count': 1414,
            'success': True
        },
        'oee_data': {
            'oee_percentage': 78.5,
            'availability': 85.0,
            'performance': 92.1,
            'quality': 98.0
        },
        'downtime_status': {
            'is_downtime': False,
            'info': None
        },
        'shift_info': {
            'number': 1,
            'start': '07:00:00',
            'end': '19:00:00'
        },
        'last_update': datetime.now().isoformat()
    })

@app.route('/api/minute_power')
def get_minute_power():
    """API для получения поминутной мощности за сегодня"""
    try:
        minute_data = db.get_today_minute_power()
        current_time = datetime.now()
        return jsonify({
            'minute_power': minute_data,
            'current_hour': current_time.hour,
            'current_minute': current_time.minute
        })
    except Exception as e:
        print(f"Ошибка получения поминутной мощности: {e}")
        return jsonify({
            'minute_power': [[0] * 60 for _ in range(24)],
            'current_hour': 0,
            'current_minute': 0
        })

if __name__ == '__main__':
    print(f"🚀 Запуск системы мониторинга OEE для {Config.LINE_NAME}")
    print(f"📊 Целевой показатель: {Config.TARGET_PRODUCTION_RATE} шт/час")
    print(f"⏰ Мониторинг простоев: {Config.DOWNTIME_THRESHOLD} сек")
    print(f"🔧 Адрес устройства: {Config.MODBUS_HOST}:{Config.MODBUS_PORT}")
    print(f"🌐 Веб-интерфейс доступен по: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)