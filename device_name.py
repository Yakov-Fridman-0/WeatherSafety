from enum import Enum


class DeviceName(str, Enum):
    """
    Represents the device type
    """
    ARDUINO_IN = "arduino_in"
    ARDUINO_OUT = "arduino_out"
    DAVIS_VANTAGE = "davis_vantage"
    SUN_ELEVATION_CALCULATOR = "sun_elevation_calculator"
