import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gazepoint_recorder.properties import properties
from mo.core import PropertySelectOption
from mo.core.plugin.models.properties import PropertyType


class TestPropertiesObject(unittest.TestCase):
    def test_properties_has_config_name(self):
        self.assertTrue(properties.has_property('config_name'))

    def test_properties_has_device_port(self):
        self.assertTrue(properties.has_property('device_port'))

    def test_properties_has_time_autosave(self):
        self.assertTrue(properties.has_property('time_autosave'))

    def test_has_three_fields(self):
        self.assertEqual(len(properties.get_default_values()), 3)

    def test_config_name_is_path_type(self):
        self.assertEqual(properties.get_type('config_name'), PropertyType.PATH)

    def test_config_name_default(self):
        self.assertEqual(properties.get_default_values()['config_name'], 'Gazepoint_Config_1')

    def test_device_port_is_int_type(self):
        self.assertEqual(properties.get_type('device_port'), PropertyType.INT)

    def test_device_port_default(self):
        self.assertEqual(properties.get_default_values()['device_port'], 4242)

    def test_device_port_min(self):
        self.assertEqual(properties.get_property('device_port').data['min'], 1)

    def test_device_port_max(self):
        self.assertEqual(properties.get_property('device_port').data['max'], 65535)

    def test_device_port_step(self):
        self.assertEqual(properties.get_property('device_port').data['step'], 1)

    def test_time_autosave_is_select_type(self):
        self.assertEqual(properties.get_type('time_autosave'), PropertyType.SELECT)

    def test_time_autosave_default(self):
        self.assertEqual(properties.get_default_values()['time_autosave'], 10)

    def test_time_autosave_has_four_options(self):
        opts = properties.get_property('time_autosave').data['options']
        self.assertEqual(len(opts), 4)

    def test_time_autosave_option_values(self):
        opts = properties.get_property('time_autosave').data['options']
        values = [o.value for o in opts]
        self.assertIn(5, values)
        self.assertIn(10, values)
        self.assertIn(15, values)
        self.assertIn(20, values)

    def test_time_autosave_option_labels(self):
        opts = properties.get_property('time_autosave').data['options']
        labels = [o.label for o in opts]
        self.assertIn('5 seconds', labels)
        self.assertIn('10 seconds', labels)
        self.assertIn('15 seconds', labels)
        self.assertIn('20 seconds', labels)

    def test_options_are_select_option_instances(self):
        opts = properties.get_property('time_autosave').data['options']
        for opt in opts:
            self.assertIsInstance(opt, PropertySelectOption)


if __name__ == '__main__':
    unittest.main()
