from enum import StrEnum


class RiskLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class IncidentPattern(StrEnum):
    TRAFFIC_JAM = "TRAFFIC_JAM"
    ACCIDENT = "ACCIDENT"
    ROAD_WORK = "ROAD_WORK"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    WEATHER_CONDITIONS = "WEATHER_CONDITIONS"
    UNKNOWN_DELAY = "UNKNOWN_DELAY"


class PredictionStatus(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    NO_TARGET = "NO_TARGET"
