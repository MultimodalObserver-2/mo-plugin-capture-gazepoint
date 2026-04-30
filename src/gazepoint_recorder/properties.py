from mo.core import Properties, PropertySelectOption
from mo import translate

properties = Properties()

properties.add_path("config_name", translate("Select Config Name"))
properties.set_default("config_name", "Gazepoint_Config_1")

properties.add_int("device_port", translate("Selecto Device Port"), min=1, max=65535, step=1)
properties.set_default("device_port", 4242)

properties.add_select("time_autosave", translate("Select Time Save"), [
    PropertySelectOption(label="5 seconds", value=5),
    PropertySelectOption(label="10 seconds", value=10),
    PropertySelectOption(label="15 seconds", value=15),
    PropertySelectOption(label="20 seconds", value=20),
])
properties.set_default("time_autosave", 10)