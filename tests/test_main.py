import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
import threading
import time
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from gazepoint_recorder.main import GazePointRecorderPlugin


class MockSettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get_setting(self, key):
        return self._data.get(key)


REC_LINE = (
    'REC K0="0.5" K1="0.6" K2="0" K3="0" K4="0" K5="1"'
    ' K6="0.4" K7="0.5" K8="1" K9="0.6" K10="0.7" K11="1"'
    ' K12="0.5" K13="0.6" K14="1" K15="0.4" K16="0.5" K17="3.5"'
    ' K18="0" K19="0.6" K20="0.6" K21="0.7" K22="3.6" K23="0" K24="1"'
)

RAW_HEADER = (
    'TIME_TICK|DATE|FPOGX|FPOGY|FPOGV|LPOGX|LPOGY|LPOGV|'
    'RPOGX|RPOGY|RPOGV|BPOGX|BPOGY|BPOGV|LPCX|LPCY|LPD|LPV|'
    'RPCX|RPCY|RPD|RPV|WIDTH|HEIGHT\n'
)


def make(settings=None):
    p = GazePointRecorderPlugin()
    p.settings = MockSettings(settings or {})
    p.load()
    return p


class TestMain(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._p = make()
        self._p.screen_width = 1920
        self._p.screen_height = 1080

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def active(self):
        p = make()
        p.capture_event.set()
        p.paused_event.set()
        return p

    def sample_data(self):
        return {
            'fpogx': 0.5, 'fpogy': 0.6, 'fpogv': 1,
            'lpogx': 0.4, 'lpogy': 0.5, 'lpogv': 1,
            'rpogx': 0.6, 'rpogy': 0.7, 'rpogv': 1,
            'bpogx': 0.5, 'bpogy': 0.6, 'bpogv': 1,
            'lpcx': 0.4, 'lpcy': 0.5, 'lpd': 3.5, 'lpv': '1',
            'rpcx': 0.6, 'rpcy': 0.7, 'rpd': 3.6, 'rpv': '1',
        }

    def gaze_parts(self, fpogv='1'):
        return [
            '1000', '2022-01-01 00:00:00.000',
            '0.5', '0.6', fpogv,
            '0.4', '0.5', '1',
            '0.6', '0.7', '1',
            '0.5', '0.6', '1',
            '0.4', '0.5', '3.5', '1',
            '0.6', '0.7', '3.6', '1',
            '1920', '1080',
        ]

    def loop_plugin(self):
        p = make()
        p.raw_output_path = os.path.join(self._tmpdir, 'test.raw')
        p.get_timestamp = MagicMock(return_value=1.0)
        p.on_data = MagicMock()
        p.connect_gazepoint = MagicMock()
        p.setup_gazepoint = MagicMock()
        p.get_screen_size = MagicMock()
        p.disconnect_gazepoint = MagicMock()
        p.last_dump_time = time.time()
        return p

    def test_load_capture_event_not_set(self):
        p = make()
        self.assertFalse(p.capture_event.is_set())

    def test_load_paused_event_not_set(self):
        p = make()
        self.assertFalse(p.paused_event.is_set())

    def test_load_paths_empty(self):
        p = make()
        self.assertEqual(p.output_path, "")
        self.assertEqual(p.raw_output_path, "")

    def test_load_socket_none(self):
        p = make()
        self.assertIsNone(p.socket_connection)

    def test_load_buffer_empty(self):
        p = make()
        self.assertEqual(p.buffer, [])

    def test_load_last_dump_time_none(self):
        p = make()
        self.assertIsNone(p.last_dump_time)

    def test_load_default_time_autosave(self):
        p = make()
        self.assertEqual(p.time_autosave, 10)

    def test_load_default_device_port(self):
        p = make()
        self.assertEqual(p.device_port, 4242)

    def test_load_screen_dimensions_zero(self):
        p = make()
        self.assertEqual(p.screen_width, 0)
        self.assertEqual(p.screen_height, 0)

    def test_load_workflow_status_one(self):
        p = make()
        self.assertEqual(p.workflow_status, 1)

    def test_load_pause_offsets_zero(self):
        p = make()
        self.assertEqual(p.resume_offset, 0)
        self.assertEqual(p.pause_start, 0)

    def test_load_capture_thread_none(self):
        p = make()
        self.assertIsNone(p.capture_thread)

    def test_unload_clears_capture_event(self):
        p = make()
        p.capture_event.set()
        p.unload()
        self.assertFalse(p.capture_event.is_set())

    def test_unload_sets_paused_event(self):
        p = make()
        p.unload()
        self.assertTrue(p.paused_event.is_set())

    def test_unload_closes_socket(self):
        p = make()
        mock_sock = MagicMock()
        p.socket_connection = mock_sock
        p.unload()
        mock_sock.close.assert_called_once()
        self.assertIsNone(p.socket_connection)

    def test_unload_no_socket_ok(self):
        p = make()
        p.socket_connection = None
        p.unload()

    def test_prepare_sets_output_path(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertEqual(p.output_path, os.path.join(self._tmpdir, 'rec.txt'))

    def test_prepare_sets_raw_output_path(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertEqual(p.raw_output_path, os.path.join(self._tmpdir, 'rec.raw'))

    def test_prepare_default_port(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertEqual(p.device_port, 4242)

    def test_prepare_port_from_settings(self):
        p = make({'port': 5000})
        p.prepare(self._tmpdir, 'rec')
        self.assertEqual(p.device_port, 5000)

    def test_prepare_autosave_from_settings(self):
        p = make({'time_autosave': 15})
        p.prepare(self._tmpdir, 'rec')
        self.assertEqual(p.time_autosave, 15)

    def test_prepare_paused_event_set(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertTrue(p.paused_event.is_set())

    def test_prepare_creates_directory(self):
        p = make()
        subdir = os.path.join(self._tmpdir, 'new_subdir')
        p.prepare(subdir, 'rec')
        self.assertTrue(os.path.isdir(subdir))

    def test_prepare_creates_output_files(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertTrue(os.path.exists(p.output_path))
        self.assertTrue(os.path.exists(p.raw_output_path))

    def test_prepare_last_dump_time_set(self):
        p = make()
        p.prepare(self._tmpdir, 'rec')
        self.assertIsNotNone(p.last_dump_time)


    @patch('threading.Thread')
    def test_start_sets_recording_start_ts(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        self.assertEqual(p.recording_start_ts, 1000.0)

    @patch('threading.Thread')
    def test_start_captures_get_timestamp(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        fn = MagicMock(return_value=1.0)
        p.start(1000.0, fn, MagicMock())
        self.assertEqual(p.get_timestamp, fn)

    @patch('threading.Thread')
    def test_start_captures_on_data(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        cb = MagicMock()
        p.start(1000.0, MagicMock(), cb)
        self.assertEqual(p.on_data, cb)

    @patch('threading.Thread')
    def test_start_capture_event_set(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        self.assertTrue(p.capture_event.is_set())

    @patch('threading.Thread')
    def test_start_paused_event_set(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        self.assertTrue(p.paused_event.is_set())

    @patch('threading.Thread')
    def test_start_workflow_status(self, mock_thread):
        mock_thread.return_value = MagicMock()
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        self.assertEqual(p.workflow_status, 1)

    @patch('threading.Thread')
    def test_start_thread_started(self, mock_thread):
        mock_inst = MagicMock()
        mock_thread.return_value = mock_inst
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        mock_inst.start.assert_called_once()

    @patch('threading.Thread')
    def test_start_thread_is_daemon(self, mock_thread):
        mock_inst = MagicMock()
        mock_thread.return_value = mock_inst
        p = make()
        p.start(1000.0, MagicMock(), MagicMock())
        self.assertTrue(mock_inst.daemon)

    def test_pause_clears_paused_event(self):
        p = self.active()
        p.pause(10.0)
        self.assertFalse(p.paused_event.is_set())

    def test_pause_sets_workflow_status(self):
        p = self.active()
        p.pause(10.0)
        self.assertEqual(p.workflow_status, 2)

    def test_pause_records_pause_start(self):
        p = self.active()
        p.pause(10.0)
        self.assertEqual(p.pause_start, 10.0)

    def test_pause_not_capturing(self):
        p = make()
        p.capture_event.clear()
        p.paused_event.set()
        p.pause(10.0)
        self.assertTrue(p.paused_event.is_set())

    def test_pause_already_paused(self):
        p = self.active()
        p.paused_event.clear()
        p.pause(10.0)
        self.assertEqual(p.pause_start, 0)

    def test_resume_sets_paused_event(self):
        p = self.active()
        p.pause(10.0)
        p.resume(20.0)
        self.assertTrue(p.paused_event.is_set())

    def test_resume_sets_workflow_status(self):
        p = self.active()
        p.pause(10.0)
        p.resume(20.0)
        self.assertEqual(p.workflow_status, 1)

    def test_resume_calculates_offset(self):
        p = self.active()
        p.pause(10.0)
        p.resume(20.0)
        self.assertEqual(p.resume_offset, 10.0)

    def test_resume_not_paused(self):
        p = self.active()
        p.resume(20.0)
        self.assertEqual(p.resume_offset, 0)

    def test_resume_not_capturing(self):
        p = make()
        p.capture_event.clear()
        p.paused_event.clear()
        p.resume(20.0)
        self.assertEqual(p.resume_offset, 0)

    def test_stop_clears_capture_event(self):
        p = make()
        p.capture_event.set()
        p.stop(100.0)
        self.assertFalse(p.capture_event.is_set())

    def test_stop_sets_paused_event(self):
        p = make()
        p.paused_event.clear()
        p.stop(100.0)
        self.assertTrue(p.paused_event.is_set())

    def test_stop_sets_workflow_status(self):
        p = make()
        p.stop(100.0)
        self.assertEqual(p.workflow_status, 0)

    def test_stop_joins_alive_thread(self):
        p = make()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        p.capture_thread = mock_thread
        p.stop(100.0)
        mock_thread.join.assert_called_once_with(timeout=2.0)

    def test_stop_skips_join_dead_thread(self):
        p = make()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        p.capture_thread = mock_thread
        p.stop(100.0)
        mock_thread.join.assert_not_called()

    def test_stop_no_thread_ok(self):
        p = make()
        p.capture_thread = None
        p.stop(100.0)

    @patch('socket.socket')
    def test_creates_tcp_socket(self, mock_cls):
        import socket as socket_mod
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        p = make()
        p.connect_gazepoint()
        mock_cls.assert_called_once_with(socket_mod.AF_INET, socket_mod.SOCK_STREAM)

    @patch('socket.socket')
    def test_socket_localhost(self, mock_cls):
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        p = make()
        p.device_port = 4242
        p.connect_gazepoint()
        mock_inst.connect.assert_called_once_with(('127.0.0.1', 4242))

    @patch('socket.socket')
    def test_custom_port(self, mock_cls):
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        p = make()
        p.device_port = 5000
        p.connect_gazepoint()
        mock_inst.connect.assert_called_once_with(('127.0.0.1', 5000))

    @patch('socket.socket')
    def test_socket_timeout(self, mock_cls):
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        p = make()
        p.connect_gazepoint()
        mock_inst.settimeout.assert_called_once_with(0.1)

    @patch('socket.socket')
    def test_stores_socket(self, mock_cls):
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        p = make()
        p.connect_gazepoint()
        self.assertEqual(p.socket_connection, mock_inst)

    @patch('time.sleep')
    def test_setup_sends_eight_commands(self, _sleep):
        p = make()
        mock_sock = MagicMock()
        p.socket_connection = mock_sock
        p.setup_gazepoint()
        self.assertEqual(mock_sock.sendall.call_count, 8)

    @patch('time.sleep')
    def test_setup_first_command_enables_data(self, _sleep):
        p = make()
        mock_sock = MagicMock()
        p.socket_connection = mock_sock
        p.setup_gazepoint()
        first_arg = mock_sock.sendall.call_args_list[0][0][0]
        self.assertIn(b'ENABLE_SEND_DATA', first_arg)

    @patch('time.sleep')
    def test_setup_last_command_screen_size(self, _sleep):
        p = make()
        mock_sock = MagicMock()
        p.socket_connection = mock_sock
        p.setup_gazepoint()
        last_arg = mock_sock.sendall.call_args_list[-1][0][0]
        self.assertIn(b'SCREEN_SIZE', last_arg)

    def test_screen_size_parses_width_and_height(self):
        p = make()
        mock_sock = MagicMock()
        response = '<ACK ID="SCREEN_SIZE" X="1920" Y="1080" />\r\n'
        mock_sock.recv.return_value = response.encode()
        p.socket_connection = mock_sock
        p.get_screen_size()
        self.assertEqual(p.screen_width, 1920)
        self.assertEqual(p.screen_height, 1080)

    def test_screen_size_defaults_no_message(self):
        p = make()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b'<ACK ID="OTHER" />\r\n'
        p.socket_connection = mock_sock
        p.get_screen_size()
        self.assertEqual(p.screen_width, 1920)
        self.assertEqual(p.screen_height, 1080)

    def test_screen_size_defaults_empty_response(self):
        p = make()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b''
        p.socket_connection = mock_sock
        p.get_screen_size()
        self.assertEqual(p.screen_width, 1920)
        self.assertEqual(p.screen_height, 1080)

    def test_read_returns_none_on_empty(self):
        p = make()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b''
        p.socket_connection = mock_sock
        self.assertIsNone(p.read_gazepoint_data())

    def test_read_returns_dict_on_valid_rec(self):
        p = make()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = (REC_LINE + '\r\n').encode()
        p.socket_connection = mock_sock
        result = p.read_gazepoint_data()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_read_sets_timeout(self):
        p = make()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b''
        p.socket_connection = mock_sock
        p.read_gazepoint_data()
        mock_sock.settimeout.assert_called_with(1.0)

    def test_parse_invalid_data(self):
        p = make()
        self.assertIsNone(p.parse_gazepoint_data("invalid_data"))

    def test_parse_rec_insufficient_parts(self):
        p = make()
        self.assertIsNone(p.parse_gazepoint_data('<REC CNT="0" TIME="1000" />'))

    def test_parse_screen_size_only(self):
        p = make()
        self.assertIsNone(p.parse_gazepoint_data('<ACK ID="SCREEN_SIZE" X="1920" Y="1080" />'))

    def test_parse_valid_rec_line(self):
        p = make()
        result = p.parse_gazepoint_data(REC_LINE)
        self.assertIsNotNone(result)
        self.assertIn('fpogx', result)
        self.assertIn('fpogy', result)

    def test_parse_fpogx_value(self):
        p = make()
        self.assertAlmostEqual(p.parse_gazepoint_data(REC_LINE)['fpogx'], 0.5)

    def test_parse_fpogy_value(self):
        p = make()
        self.assertAlmostEqual(p.parse_gazepoint_data(REC_LINE)['fpogy'], 0.6)

    def test_parse_fpogv_is_int(self):
        p = make()
        self.assertIsInstance(p.parse_gazepoint_data(REC_LINE)['fpogv'], int)

    def test_parse_has_raw_data(self):
        p = make()
        self.assertIn('raw_data', p.parse_gazepoint_data(REC_LINE))

    def test_parse_value_errors_skipped(self):
        p = make()
        bad = ('REC K0="abc" K1="def" K2="0" K3="0" K4="0" K5="ghi"'
               ' K6="0" K7="0" K8="0" K9="0" K10="0" K11="jkl"'
               ' K12="0" K13="0" K14="0" K15="0" K16="0" K17="0"'
               ' K18="0" K19="0" K20="0" K21="0" K22="0" K23="0" K24="0"')
        self.assertIsNone(p.parse_gazepoint_data(bad))

    def test_parse_empty_string(self):
        p = make()
        self.assertIsNone(p.parse_gazepoint_data(""))

    @patch('time.time')
    def test_process_appends_to_buffer(self, mock_time):
        mock_time.return_value = 1001.0
        p = make()
        p.last_dump_time = 1000.0
        p.process_data(self.sample_data(), 1640995200.0)
        self.assertEqual(len(p.buffer), 1)

    @patch('time.time')
    def test_process_buffer_contains_timestamp(self, mock_time):
        mock_time.return_value = 1001.0
        p = make()
        p.last_dump_time = 1000.0
        p.process_data(self.sample_data(), 1640995200.0)
        self.assertIn('1640995200000', p.buffer[0])

    @patch('time.time')
    def test_process_buffer_contains_screen_dims(self, mock_time):
        mock_time.return_value = 1001.0
        p = make()
        p.screen_width = 1920
        p.screen_height = 1080
        p.last_dump_time = 1000.0
        p.process_data(self.sample_data(), 1640995200.0)
        self.assertIn('1920', p.buffer[0])
        self.assertIn('1080', p.buffer[0])

    @patch('time.time')
    def test_process_triggers_autosave(self, mock_time):
        mock_time.return_value = 1015.0
        p = make()
        p.time_autosave = 10
        p.last_dump_time = 1000.0
        p.dump_to_file = MagicMock()
        p.process_data(self.sample_data(), 1640995200.0)
        p.dump_to_file.assert_called_once()

    @patch('time.time')
    def test_process_no_autosave_within_interval(self, mock_time):
        mock_time.return_value = 1005.0
        p = make()
        p.time_autosave = 10
        p.last_dump_time = 1000.0
        p.dump_to_file = MagicMock()
        p.process_data(self.sample_data(), 1640995200.0)
        p.dump_to_file.assert_not_called()


    def test_dump_writes_buffer(self):
        p = make()
        p.raw_output_path = os.path.join(self._tmpdir, 'test.raw')
        p.buffer = ['line1\n', 'line2\n']
        p.dump_to_file()
        with open(p.raw_output_path, 'r') as f:
            content = f.read()
        self.assertIn('line1', content)
        self.assertIn('line2', content)

    def test_dump_clears_buffer(self):
        p = make()
        p.raw_output_path = os.path.join(self._tmpdir, 'test.raw')
        p.buffer = ['line1\n']
        p.dump_to_file()
        self.assertEqual(p.buffer, [])

    def test_dump_updates_last_dump_time(self):
        p = make()
        p.raw_output_path = os.path.join(self._tmpdir, 'test.raw')
        p.buffer = []
        p.last_dump_time = 0.0
        p.dump_to_file()
        self.assertGreater(p.last_dump_time, 0.0)

    def test_dump_empty_buffer_no_file(self):
        p = make()
        path = os.path.join(self._tmpdir, 'test.raw')
        p.raw_output_path = path
        p.buffer = []
        p.dump_to_file()
        self.assertFalse(os.path.exists(path))

    def test_closes_socket(self):
        p = make()
        mock_sock = MagicMock()
        p.socket_connection = mock_sock
        p.disconnect_gazepoint()
        mock_sock.close.assert_called_once()

    def test_socket_is_none(self):
        p = make()
        p.socket_connection = MagicMock()
        p.disconnect_gazepoint()
        self.assertIsNone(p.socket_connection)

    def test_no_socket_ok(self):
        p = make()
        p.socket_connection = None
        p.disconnect_gazepoint()

    def test_format_contains_timestamp_and_st(self):
        self.assertIn('t:1000 st:7', self._p.format_gaze_line(self.gaze_parts()))

    def test_format_fx_true_when_fpogv_one(self):
        self.assertIn('fx:true', self._p.format_gaze_line(self.gaze_parts('1')))

    def test_format_fx_false_when_fpogv_zero(self):
        self.assertIn('fx:false', self._p.format_gaze_line(self.gaze_parts('0')))

    def test_format_sm_scales_screen(self):
        self.assertIn('sm:960.0;648.0', self._p.format_gaze_line(self.gaze_parts()))

    def test_format_lpc_scales_screen(self):
        self.assertIn('lpc:768.0;540.0', self._p.format_gaze_line(self.gaze_parts()))

    def test_format_rpc_scales_screen(self):
        self.assertIn('rpc:1152.0;756.0', self._p.format_gaze_line(self.gaze_parts()))

    def test_format_ends_newline(self):
        self.assertTrue(self._p.format_gaze_line(self.gaze_parts()).endswith('\n'))

    def test_final_output_missing_raw_file(self):
        p = make()
        p.raw_output_path = '/nonexistent/path.raw'
        p.output_path = os.path.join(self._tmpdir, 'out.txt')
        p.formatt_final_output()

    def test_final_output_skips_short_lines(self):
        raw = os.path.join(self._tmpdir, 'test.raw')
        out = os.path.join(self._tmpdir, 'test.txt')
        with open(raw, 'w') as f:
            f.write(RAW_HEADER)
            f.write('1000|2022-01-01|0.5|0.6\n')
        p = make()
        p.raw_output_path = raw
        p.output_path = out
        p.formatt_final_output()
        with open(out, 'r') as f:
            self.assertEqual(f.read(), '')

    def test_final_output_formats_valid_line(self):
        raw = os.path.join(self._tmpdir, 'test.raw')
        out = os.path.join(self._tmpdir, 'test.txt')
        with open(raw, 'w') as f:
            f.write(RAW_HEADER)
            f.write('1000|2022-01-01 00:00:00.000|'
                    '0.5|0.6|1|0.4|0.5|1|0.6|0.7|1|0.5|0.6|1|'
                    '0.4|0.5|3.5|1|0.6|0.7|3.6|1|1920|1080\n')
        p = make()
        p.raw_output_path = raw
        p.output_path = out
        p.screen_width = 1920
        p.screen_height = 1080
        p.formatt_final_output()
        with open(out, 'r') as f:
            content = f.read()
        self.assertIn('t:1000 st:7', content)
        self.assertIn('fx:true', content)
        self.assertIn('sm:960.0;648.0', content)

    def test_save_dump_called_when_buffer_nonempty(self):
        p = make()
        p.buffer = ['x\n']
        p.dump_to_file = MagicMock()
        p.formatt_final_output = MagicMock()
        p.save([], end_of_data=False)
        p.dump_to_file.assert_called_once()

    def test_save_dump_not_called_empty(self):
        p = make()
        p.buffer = []
        p.dump_to_file = MagicMock()
        p.formatt_final_output = MagicMock()
        p.save([], end_of_data=False)
        p.dump_to_file.assert_not_called()

    def test_save_formatt_called_on_end_of_data(self):
        p = make()
        p.buffer = []
        p.dump_to_file = MagicMock()
        p.formatt_final_output = MagicMock()
        p.save([], end_of_data=True)
        p.formatt_final_output.assert_called_once()

    def test_save_formatt_not_called_end_of_data(self):
        p = make()
        p.buffer = []
        p.dump_to_file = MagicMock()
        p.formatt_final_output = MagicMock()
        p.save([], end_of_data=False)
        p.formatt_final_output.assert_not_called()

    def test_save_both_called_buffer_and_end_of_data(self):
        p = make()
        p.buffer = ['x\n']
        p.dump_to_file = MagicMock()
        p.formatt_final_output = MagicMock()
        p.save([], end_of_data=True)
        p.dump_to_file.assert_called_once()
        p.formatt_final_output.assert_called_once()

    def test_extension_is_txt(self):
        self.assertEqual(make().get_file_extension(), 'txt')

    def test_descriptor_format(self):
        self.assertEqual(make().get_output_descriptor()['format'], 'gaze_data')

    def test_descriptor_version(self):
        self.assertEqual(make().get_output_descriptor()['version'], '1.0')

    def test_descriptor_has_timestamp_field(self):
        self.assertIn('timestamp', make().get_output_descriptor()['fields'])

    def test_descriptor_coordinate_system(self):
        self.assertEqual(make().get_output_descriptor()['coordinate_system'], 'screen_pixels')

    def test_loop_called(self):
        p = self.loop_plugin()
        p.read_gazepoint_data = MagicMock(return_value=None)
        p.capture_event.set()
        p.paused_event.set()
        t = threading.Thread(target=p.capture_loop)
        t.daemon = True
        t.start()
        time.sleep(0.05)
        p.capture_event.clear()
        t.join(timeout=12.0)
        p.connect_gazepoint.assert_called_once()
        p.disconnect_gazepoint.assert_called_once()

    def test_loop_on_workflow_status_zero(self):
        p = self.loop_plugin()
        p.read_gazepoint_data = MagicMock(return_value=None)
        p.capture_event.set()
        p.paused_event.set()
        p.workflow_status = 1
        t = threading.Thread(target=p.capture_loop)
        t.daemon = True
        t.start()
        time.sleep(0.05)
        p.workflow_status = 0
        t.join(timeout=12.0)
        self.assertFalse(t.is_alive())

    def test_loop_on_data_called_data_received(self):
        p = self.loop_plugin()
        p.read_gazepoint_data = MagicMock(return_value=self.sample_data())
        p.capture_event.set()
        p.paused_event.set()
        t = threading.Thread(target=p.capture_loop)
        t.daemon = True
        t.start()
        time.sleep(0.05)
        p.capture_event.clear()
        t.join(timeout=12.0)
        p.on_data.assert_called()

    def test_loop_buffer_dumped_on_exit(self):
        p = self.loop_plugin()
        p.read_gazepoint_data = MagicMock(return_value=None)
        p.buffer = ['line1\n']
        p.dump_to_file = MagicMock()
        p.capture_event.set()
        p.paused_event.set()
        t = threading.Thread(target=p.capture_loop)
        t.daemon = True
        t.start()
        time.sleep(0.05)
        p.capture_event.clear()
        t.join(timeout=12.0)
        p.dump_to_file.assert_called()


if __name__ == '__main__':
    unittest.main()
