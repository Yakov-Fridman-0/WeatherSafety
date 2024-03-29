import datetime
from typing import List
import serial

from station import SerialStation
import logging
from utils import OutsideArduinoReading, OutsideArduinoDatum
from config.config import make_cfg
from init_log import init_log
from arduino import Arduino
from db_access import make_db_manager, DbManager
from sqlalchemy.orm import scoped_session

logger = logging.getLogger('outside-arduino')
init_log(logger)


class OutsideArduino(SerialStation, Arduino):

    db_manager: DbManager

    def __init__(self, name: str):
        self.name = name

        try:
            super().__init__(name=self.name)
        except Exception as ex:
            logger.error(f"Cannot construct SerialStation for '{self.name}'", exc_info=ex)
            return

        cfg = make_cfg()
        self.interval = cfg.station_settings[self.name].interval
        self.db_manager = make_db_manager()

    @classmethod
    def datums(cls) -> List[str]:
        return [item.value for item in OutsideArduinoDatum]

    def fetcher(self) -> None:
        # print(f"{self.name}: fetcher is bypassed")
        # return
        reading: OutsideArduinoReading = OutsideArduinoReading()
        try:
            self.ser = serial.Serial(port=self.port, baudrate=self.baud,
                                     timeout=self.timeout, write_timeout=self.write_timeout)
        except Exception as ex:
            logger.error(f"Could not open '{self.port}", exc_info=ex)
            self.ser.close()
            return

        try:
            self.get_wind(reading)
            self.get_light(reading)
            self.get_pressure_humidity_temperature(reading)
            self.ser.close()
        except Exception as ex:
            logger.error(f"Failed to get readings", exc_info=ex)
            self.ser.close()
            return

        reading.tstamp = datetime.datetime.utcnow()
        logger.debug(f"reading: {reading.__dict__}")
        with self.lock:
            self.readings.push(reading)
        if hasattr(self, 'saver'):
            self.saver(reading)

    def saver(self, reading: OutsideArduinoReading) -> None:
        from db_access import ArduinoOutDbClass

        arduino_out = ArduinoOutDbClass(
            temp_out=reading.datums[OutsideArduinoDatum.TemperatureOut],
            humidity_out=reading.datums[OutsideArduinoDatum.HumidityOut],
            pressure_out=reading.datums[OutsideArduinoDatum.PressureOut],
            dew_point=reading.datums[OutsideArduinoDatum.DewPoint],
            visible_lux_out=reading.datums[OutsideArduinoDatum.VisibleLuxOut],
            ir_luminosity=reading.datums[OutsideArduinoDatum.IrLuminosity],
            wind_speed=reading.datums[OutsideArduinoDatum.WindSpeed],
            wind_direction=reading.datums[OutsideArduinoDatum.WindDirection],
            tstamp=reading.tstamp
        )

        # db_manager = make_db_manager()
        # db_manager.session.add(arduino_out)
        Session = scoped_session(self.db_manager.session_factory)
        session = Session()
        try:
            session.add(arduino_out)
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            Session.remove()

    def get_wind(self, reading: OutsideArduinoReading):
        wind_results = self.query("wind", 0.05, "v={f} m/s  dir. {f}°")

        if wind_results:
            reading.datums[OutsideArduinoDatum.WindSpeed] = wind_results[0]
            reading.datums[OutsideArduinoDatum.WindDirection] = wind_results[1]

    def get_light(self, reading: OutsideArduinoReading):
        light_results = self.query("light", 0.08, "TSL vis(Lux) IR(luminosity): {i} {i}")

        if light_results:
            reading.datums[OutsideArduinoDatum.VisibleLuxOut] = light_results[0]
            reading.datums[OutsideArduinoDatum.IrLuminosity] = light_results[1]

    def get_pressure_humidity_temperature(self, reading: OutsideArduinoReading):
        results = self.query("pht", 0.08, "P:{f}hPa T:{f}°C RH:{f}% comp RH:{f}% dew point:{f}°C")

        if results:
            reading.datums[OutsideArduinoDatum.PressureOut] = results[0]
            reading.datums[OutsideArduinoDatum.TemperatureOut] = results[1]
            reading.datums[OutsideArduinoDatum.HumidityOut] = results[2]
            reading.datums[OutsideArduinoDatum.DewPoint] = results[3]

    def get_correct_file(self) -> str:
        return "Outdoor_multiQuery.ino"
