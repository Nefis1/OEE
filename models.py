# models.py
from datetime import datetime, time, timedelta
from config import Config

class ShiftManager:
    """Управление сменами"""
    
    @staticmethod
    def get_current_shift():
        """Определение текущей смены"""
        now = datetime.now().time()
        
        for shift in Config.SHIFTS:
            if shift["start"] < shift["end"]:
                # Обычная смена (в пределах одного дня)
                if shift["start"] <= now < shift["end"]:
                    return shift
            else:
                # Ночная смена (переход через полночь)
                if now >= shift["start"] or now < shift["end"]:
                    return shift
        return None
    
    @staticmethod
    def get_shift_start_time(shift_number=None, for_date=None):
        """Получение времени начала смены"""
        if for_date is None:
            for_date = datetime.now().date()
        
        if shift_number is None:
            shift = ShiftManager.get_current_shift()
            shift_number = shift["number"] if shift else 1
        
        shift_config = next((s for s in Config.SHIFTS if s["number"] == shift_number), None)
        if shift_config:
            # Для ночной смены начало - предыдущий день в 19:00
            if shift_config["start"].hour >= 19:
                return datetime.combine(for_date - timedelta(days=1), shift_config["start"])
            else:
                return datetime.combine(for_date, shift_config["start"])
        return None

class OEECalculator:
    """Калькулятор OEE показателей"""
    
    def __init__(self):
        self.config = Config
    
    def calculate_oee(self, actual_production, planned_production, operating_time, available_time, good_units=None):
        """
        Полный расчет OEE
        
        Args:
            actual_production: Фактическое производство (шт)
            planned_production: Плановое производство (шт)
            operating_time: Время работы (мин)
            available_time: Доступное время (мин)
            good_units: Количество годных изделий (если None, используется quality_rate)
        """
        
        try:
            # Availability (Доступность)
            if available_time > 0:
                availability = min(1.0, operating_time / available_time)
            else:
                availability = 0
            
            # Performance (Производительность)
            if operating_time > 0:
                # Рассчитываем идеальное производство за указанное время
                ideal_production = (self.config.TARGET_PRODUCTION_RATE / 60) * operating_time
                performance = min(1.0, actual_production / ideal_production) if ideal_production > 0 else 0
            else:
                performance = 0
            
            # Quality (Качество)
            if good_units is not None and actual_production > 0:
                quality = good_units / actual_production
            else:
                quality = self.config.QUALITY_RATE
            
            # OEE
            oee = availability * performance * quality
            
            # Расчет производственной скорости (шт/час)
            if operating_time > 0:
                production_rate = (actual_production / operating_time) * 60
            else:
                production_rate = 0
            
            return {
                'oee_percentage': round(oee * 100, 2),
                'availability': round(availability * 100, 2),
                'performance': round(performance * 100, 2),
                'quality': round(quality * 100, 2),
                'production_rate': round(production_rate, 2),
                'actual_production': actual_production,
                'planned_production': planned_production,
                'operating_time': operating_time,
                'available_time': available_time
            }
        except Exception as e:
            print(f"Ошибка в расчете OEE: {e}")
            # Возвращаем значения по умолчанию при ошибке
            return {
                'oee_percentage': 0,
                'availability': 0,
                'performance': 0,
                'quality': 0,
                'production_rate': 0,
                'actual_production': actual_production,
                'planned_production': planned_production,
                'operating_time': operating_time,
                'available_time': available_time
            }
    def calculate_shift_oee(self, shift_data):
        """Расчет OEE для смены"""
        shift_duration = 12 * 60  # 12 часов в минутах
        planned_production = self.config.TARGET_SHIFT_PRODUCTION
        
        return self.calculate_oee(
            actual_production=shift_data['total_production'],
            planned_production=planned_production,
            operating_time=shift_duration - shift_data['downtime_minutes'],
            available_time=shift_duration
        )

class DowntimeMonitor:
    """Мониторинг простоев оборудования"""
    
    def __init__(self):
        self.config = Config
        self.last_production_count = None
        self.last_production_time = None
        self.downtime_start = None
        self.current_downtime_reason = None
    
    def check_downtime(self, current_count, timestamp):
        """Проверка состояния простоя"""
        
        if self.last_production_count is None:
            self.last_production_count = current_count
            self.last_production_time = timestamp
            return False, None
        
        # Проверяем, изменился ли счетчик
        if current_count > self.last_production_count:
            # Производство идет - сбрасываем мониторинг простоя
            self.last_production_count = current_count
            self.last_production_time = timestamp
            self.downtime_start = None
            self.current_downtime_reason = None
            return False, None
        
        # Счетчик не изменился - проверяем время
        time_since_last_production = timestamp - self.last_production_time
        
        if time_since_last_production >= self.config.DOWNTIME_THRESHOLD:
            # Превышен порог простоя
            if self.downtime_start is None:
                self.downtime_start = self.last_production_time
                self.current_downtime_reason = "Автоматически детектированный простой"
            
            downtime_duration = timestamp - self.downtime_start
            return True, {
                'start_time': self.downtime_start,
                'duration': downtime_duration,
                'reason': self.current_downtime_reason
            }
        
        return False, None
    
    def add_downtime_reason(self, reason):
        """Добавление причины простоя (для ручного ввода)"""
        self.current_downtime_reason = reason