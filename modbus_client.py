# modbus_client.py
from pymodbus.client import ModbusTcpClient
import time
from config import Config

class ProductionMonitor:
    def __init__(self):
        self.config = Config
        self.client = ModbusTcpClient(
            self.config.MODBUS_HOST, 
            port=self.config.MODBUS_PORT, 
            timeout=5
        )
        
    def read_32bit_counter(self, address):
        """Чтение 32-битного счетчика (Big-endian)"""
        try:
            if not self.client.connect():
                return None
                
            result = self.client.read_input_registers(
                address, 
                count=2, 
                device_id=self.config.MODBUS_DEVICE_ID
            )
            
            if not result.isError():
                reg1, reg2 = result.registers
                # Big-endian: (reg1 << 16) | reg2
                value = (reg1 << 16) | reg2
                return value
        except Exception as e:
            print(f"Ошибка чтения 32-битного счетчика {address}: {e}")
        finally:
            self.client.close()
        return None
    
    def read_16bit_counter(self, address):
        """Чтение 16-битного счетчика"""
        try:
            if not self.client.connect():
                return None
                
            result = self.client.read_input_registers(
                address, 
                count=1, 
                device_id=self.config.MODBUS_DEVICE_ID
            )
            
            if not result.isError():
                return result.registers[0]
        except Exception as e:
            print(f"Ошибка чтения 16-битного счетчика {address}: {e}")
        finally:
            self.client.close()
        return None
    
    def get_production_data(self):
        """Получение всех данных производства"""
        try:
            ivams_count = self.read_32bit_counter(self.config.IVAMS_COUNTER_ADDR)
            hour_count = self.read_16bit_counter(self.config.HOUR_COUNTER_ADDR)
            aux_count = self.read_16bit_counter(self.config.AUX_COUNTER_ADDR)
            
            if ivams_count is not None:
                return {
                    'timestamp': time.time(),
                    'ivams_total': ivams_count,
                    'hour_count': hour_count or 0,
                    'aux_count': aux_count or 0,
                    'success': True
                }
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            
        return {'success': False}
    
    def calculate_oee(self, produced_count, time_interval_minutes=1):
        """Расчет OEE показателей"""
        try:
            # Availability (Доступность) - упрощенный расчет
            availability = 0.85  # Можно сделать динамическим
            
            # Performance (Производительность)
            actual_rate = (produced_count / time_interval_minutes) * 60  # шт/час
            performance = min(1.0, actual_rate / self.config.TARGET_PRODUCTION_RATE)
            
            # Quality (Качество)
            quality = 0.98  # Можно сделать динамическим
            
            oee = availability * performance * quality
            
            return {
                'oee_percentage': round(oee * 100, 2),
                'availability': round(availability * 100, 2),
                'performance': round(performance * 100, 2),
                'quality': round(quality * 100, 2),
                'production_rate': round(actual_rate, 2),
                'target_rate': self.config.TARGET_PRODUCTION_RATE
            }
        except Exception as e:
            print(f"Ошибка расчета OEE: {e}")
            return None