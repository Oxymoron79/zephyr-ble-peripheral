"""
Custom UUIDs for the WRCD Service
"""
wrcdCharacteristicsNameByUuid = {
    # GATT Service UUIDs
    "00000100-f5bf-58d5-9d17-172177d1316a": "WRCD",
    "ffffff00-f5bf-58d5-9d17-172177d1316a": "WRCD Simulator",

    # GATT WRCD Service Characteristics
    "00000101-f5bf-58d5-9d17-172177d1316a": "State",
    "00000102-f5bf-58d5-9d17-172177d1316a": "Channel Settings",
    "00000103-f5bf-58d5-9d17-172177d1316a": "Status",
    "00000104-f5bf-58d5-9d17-172177d1316a": "Data",
    "00000105-f5bf-58d5-9d17-172177d1316a": "Calibration",

    # GATT WRCD Simulator Service Characteristics
    "ffffff01-f5bf-58d5-9d17-172177d1316a": "Sim Connection Parameters",
    "ffffff11-f5bf-58d5-9d17-172177d1316a": "Sim Sampling Interval",
    "ffffff12-f5bf-58d5-9d17-172177d1316a": "Sim Scans per Data Notification",
    "ffffff13-f5bf-58d5-9d17-172177d1316a": "Sim Channels per Scan",
    "ffffff14-f5bf-58d5-9d17-172177d1316a": "Sim Channel Signal Source",
    "ffffff15-f5bf-58d5-9d17-172177d1316a": "Sim Signal Amplitude",
    "ffffff16-f5bf-58d5-9d17-172177d1316a": "Sim Signal Interval",
    "ffffff30-f5bf-58d5-9d17-172177d1316a": "Sim Sensor State",
    "ffffff31-f5bf-58d5-9d17-172177d1316a": "Sim Channel Settings",
    "ffffff32-f5bf-58d5-9d17-172177d1316a": "Sim Status",
    "ffffff50-f5bf-58d5-9d17-172177d1316a": "Sim Battery Level",

    # GATT SMP Service Characteristics
    "8d53dc1d-1db7-4cd3-868b-8a527460aa84": "DFU SMP"
}