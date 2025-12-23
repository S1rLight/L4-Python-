from abc import ABC, abstractmethod
import time
from datetime import datetime
from functools import wraps
from enum import Enum
from typing import Set
import logging

'-------------------------------------------------LOGGING-------------------------------------------------'

logging.basicConfig(
    level=logging.INFO,
    filename='py_log.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

'-------------------------------------------------ROLE-------------------------------------------------'

class Role(Enum):
    ADMIN = 'admin'
    USER = 'user'
    GUEST = 'guest'

'-------------------------------------------------USER-------------------------------------------------'

class User:
    def __init__(self, name: str, role: Role):
        self.name = name
        self.role = role

'-------------------------------------------------DEVICE_TYPE-------------------------------------------------'

class DeviceType(Enum):
    LIGHT = 'light'
    THERMOSTAT = 'thermostat'
    CAMERA = 'camera'
    CLOCK = 'clock'
    SMARTHOME = 'smarthome'

'-------------------------------------------------DECORATOR-------------------------------------------------'

def access_for(roles: Set[Role]):
    def decorator(func):
        @wraps(func)
        def wrapper(self, user: User, *args, **kwargs):

            if user.role == Role.ADMIN:
                return func(self, user, *args, **kwargs)

            if user.role not in roles:
                raise PermissionError(f"Роль '{user.role.value}' не имеет прав доступа.")

            if user.role == Role.GUEST:
                if self.type == DeviceType.LIGHT and func.__name__ in {'turn_on', 'turn_off'}:
                    return func(self, user, *args, **kwargs)
                else:
                    raise PermissionError("Гости могут только включать и выключать лампы.")

            if user.role == Role.USER:
                if self.type == DeviceType.SMARTHOME and func.__name__ in {'add_device'}:
                    return func(self, user, *args, **kwargs)

                if self.type in {DeviceType.LIGHT, DeviceType.THERMOSTAT}:
                    return func(self, user, *args, **kwargs)
                else:
                    raise PermissionError("Пользователь не может управлять этим устройством.")

            else:
                raise PermissionError("Неизвестная роль пользователя.")

        return wrapper
    return decorator

'-------------------------------------------------DEVICE-------------------------------------------------'

class Device(ABC):
    def __init__(self, id_name, name):
        self.id_name = id_name
        self.name = name
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str):
            raise TypeError("name должно быть формата string")
        if not value.strip():
            raise ValueError("name не может быть пустым")
        self._name = value

    @property
    def id_name(self):
        return self._id_name

    @id_name.setter
    def id_name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("id_name должно быть формата string")
        if not value.strip():
            raise ValueError("id_name не может быть пустым")
        self._id_name = value

    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass

    @property
    @abstractmethod
    def status(self):
        pass

    @property
    @abstractmethod
    def type(self):
        pass

    def __str__(self):
        return f'{self.id_name}: {self.name}'

'-------------------------------------------------LIGHT-------------------------------------------------'

class Light(Device):
    def __init__(self, id_name: str, name: str, brightness: int = 0):
        super().__init__(id_name, name)
        self.brightness = brightness
        self._status = False

    @property
    def type(self):
        return DeviceType.LIGHT

    @property
    def brightness(self) -> int:
        return self.__brightness

    @brightness.setter
    def brightness(self, value: int) -> None:
        int_value = int(value)
        if not (0 <= int_value <= 100):
            raise ValueError('Яркость может быть только от 0 до 100')
        self.__brightness = int_value

    @access_for({Role.ADMIN, Role.USER})
    def set_brightness(self, user: User, value: int = 50):
        self.brightness = value
        self._logger.info('%s: выставлена текущая яркость %d', self.name, self.__brightness)

    @property
    def status(self) -> bool:
        return self._status

    @access_for({Role.ADMIN, Role.USER, Role.GUEST})
    def turn_off(self, user: User) -> None:
        self._status = False
        self._logger.info('%s выключен.', self.name)

    @access_for({Role.ADMIN, Role.USER, Role.GUEST})
    def turn_on(self, user: User, level: int = 50) -> None:
        self.brightness = level
        self._status = True
        self._logger.info('%s включён.', self.name)

'-------------------------------------------------THERMOSTAT-------------------------------------------------'

class Thermostat(Device):
    def __init__(self, id_name: str, name: str, current: float = 28.0):
        super().__init__(id_name, name)
        self.current = current
        self.__target = None
        self._status = False

    @staticmethod
    def _is_validate(temp: float):
        float_temp = float(temp)
        if not (5 <= float_temp <= 30):
            raise ValueError("Температура должна быть установлена от 5 до 30°С")
        return float_temp

    @property
    def type(self):
        return DeviceType.THERMOSTAT

    @property
    def current(self):
        return self.__current

    @current.setter
    def current(self, temp: float):
        self.__current = self._is_validate(temp)

    @access_for({Role.ADMIN, Role.USER})
    def set_current_temp(self, user: User, temp=24.0):
        self.current = temp
        self._logger.info('%s: установлена текущая температура - %.1f°C', self.name, self.__current)

    @property
    def target(self):
        return self.__target

    @target.setter
    def target(self, temp: float):
        self.__target = self._is_validate(temp)

    @access_for({Role.ADMIN, Role.USER})
    def set_target_temp(self, user: User, temp: float = 20.0):
        self.target = temp
        self.turn_on(user)
        self._logger.info('%s: выставлена целевая температура - %.1f°C.', self.name, self.__target)

    @property
    def status(self):
        return self._status

    @access_for({Role.ADMIN, Role.USER})
    def turn_on(self, user: User):
        if not self._status:
            self._status = True
            self._logger.info('%s включён.', self.name)

    @access_for({Role.ADMIN, Role.USER})
    def turn_off(self, user: User):
        if self._status:
            self._status = False
            self._logger.info('%s выключен.', self.name)

    @access_for({Role.ADMIN, Role.USER})
    def start(self, user: User, step_sec: int = 3, step_temp: float = 0.5):
        if not self._status:
            raise RuntimeError(f'{self.name} выключен.')
        elif self.__target is None:
            raise RuntimeError(f'У {self.name} не задана целевая температура.')

        self._logger.info('[%s] %s: старт с %.1f°C к %.1f°C',
                          time.strftime('%H:%M:%S'), self.name, self.current, self.__target)
        time.sleep(step_sec)

        while abs(self.__current - self.__target) > 1e-6:
            if self.__current < self.__target:
                self.current = min(self.__target, self.__current + step_temp)
            else:
                self.current = max(self.__target, self.__current - step_temp)

            self._logger.info('[%s] %s: текущая = %.1f°C',
                              time.strftime('%H:%M:%S'), self.name, self.current)
            time.sleep(step_sec)

        self._logger.info('[%s] %s: достигнута цель %.1f°C',
                          time.strftime('%H:%M:%S'), self.name, self.__target)
        self.turn_off(user)

'-------------------------------------------------CAMERA-------------------------------------------------'

class Camera(Device):
    def __init__(self, id_name: str, name: str):
        super().__init__(id_name, name)
        self._status = False
        self.__memory = {}
        self.__record = None
        self.__next_id = 1

    @property
    def type(self):
        return DeviceType.CAMERA

    @property
    def status(self):
        return self._status

    @access_for({Role.ADMIN})
    def turn_on(self, user: User):
        if not self._status:
            self._status = True
            self._logger.info('%s включён.', self.name)

    @access_for({Role.ADMIN})
    def turn_off(self, user: User):
        if self._status:
            self._status = False
            self._logger.info('%s выключён.', self.name)

    @access_for({Role.ADMIN})
    def start_recording(self, user: User):
        if not self._status:
            raise RuntimeError(f"{self.name} выключен.")
        if self.__record is not None:
            raise RuntimeError("Запись уже начата. Сначала вызовите stop_recording().")
        self.__record = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._logger.info('%s: начата запись в %s', self.name, self.__record)

    @access_for({Role.ADMIN})
    def stop_recording(self, user: User):
        if not self._status:
            raise RuntimeError(f"{self.name} выключен.")
        elif self.__record is None:
            raise RuntimeError("Запись не начата. Сначала вызовите start_recording().")

        finish = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key = str(self.__next_id)
        self.__memory[key] = f'{self.__record} -- {finish}'
        self.__record = None
        self.__next_id += 1
        self._logger.info('%s: запись остановлена.', self.name)

    @access_for({Role.ADMIN})
    def show_memory(self, user: User):
        return self.__memory

    @access_for({Role.ADMIN})
    def remove(self, user: User, id_obj: int):
        key = str(id_obj)
        try:
            del self.__memory[key]
        except KeyError:
            raise KeyError(f"Запись с ID {id_obj} не найдена.")
        self._logger.info('Запись с ID %d удалена.', id_obj)

'-------------------------------------------------CLOCK-------------------------------------------------'

class Clock(Device):
    def __init__(self, id_name: str, name: str):
        super().__init__(id_name, name)
        self._status = False
        self._en_time = False

    @property
    def type(self):
        return DeviceType.CLOCK

    @property
    def status(self):
        return self._status

    @property
    def current_time(self):
        if self._status:
            now = time.localtime()
            if not self._en_time:
                return time.strftime('%H:%M:%S', now)
            else:
                return time.strftime('%I:%M:%S %p', now)
        raise RuntimeError(f"{self.name} выключен.")

    @property
    def current_datetime(self):
        if self._status:
            now = datetime.now()
            if not self._en_time:
                return now.strftime('%Y/%m/%d, %H:%M:%S')
            else:
                return now.strftime('%Y/%m/%d, %I:%M:%S %p')
        raise RuntimeError(f"{self.name} выключен.")

    @access_for({Role.ADMIN})
    def set_12h(self, user: User):
        if not self._status:
            raise RuntimeError(f"{self.name} выключен.")
        self._en_time = True

    @access_for({Role.ADMIN})
    def set_24h(self, user: User):
        if not self._status:
            raise RuntimeError(f"{self.name} выключен.")
        self._en_time = False


    @access_for({Role.ADMIN})
    def turn_on(self, user: User):
        if not self._status:
            self._status = True
            self._logger.info('%s включён.', self.name)

    @access_for({Role.ADMIN})
    def turn_off(self, user: User):
        if self._status:
            self._status = False
            self._logger.info('%s выключен.', self.name)

'-------------------------------------------------SMARTHOME-------------------------------------------------'

class SmartHome():
    def __init__(self):
        self.__all_devices = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def type(self):
        return DeviceType.SMARTHOME

    @access_for({Role.ADMIN, Role.USER})
    def add_device(self, user: User, device):
        key = device.id_name
        if key in self.__all_devices:
            raise KeyError(f'Устройство с таким ключом: ({key}) уже есть.')

        self.__all_devices[key] = device
        self._logger.info('Устройство %s добавлено в SmartHome.', device.name)


    @access_for({Role.ADMIN})
    def remove_device(self, user: User, device):
        key = device.id_name
        try:
            del self.__all_devices[key]
            self._logger.info('Устройство %s удалено из SmartHome.', device.name)
        except KeyError:
            raise KeyError(f"Устройство не найдено.")


    @access_for({Role.ADMIN})
    def show_all_devices(self, user: User):
        return self.__all_devices.copy()

    def control_device(self, user: User, id_name: str, method_name: str, *args, **kwargs):
        if id_name in self.__all_devices:
            obj = self.__all_devices[id_name]

            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                return method(user, *args, **kwargs)
            else:
                raise ValueError("Неизвестный метод")
        else:
            raise KeyError(f"Устройство не найдено по id: {id_name}")

    @access_for({Role.ADMIN})
    def find(self, user: User, id_name: str):
        try:
            return self.__all_devices[id_name]
        except KeyError:
            raise KeyError(f"Устройство не найдено по id: {id_name}")

    @access_for({Role.ADMIN})
    def clear(self, user: User):
        self._logger.info("Очистка SmartHome")
        self.__all_devices.clear()
