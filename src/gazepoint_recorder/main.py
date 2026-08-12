from typing import Callable, Any
import threading
import time
import os
import sys
import socket
from datetime import datetime 

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from mo.core import load_metadata_json
from mo.modules.capture.plugins.capture_plugin import CaptureData, CapturePlugin

MAX_RECORDING_TIME = 28800

@load_metadata_json("../..")
class GazePointRecorderPlugin(CapturePlugin):


    def load(self):
        self.capture_event = threading.Event()
        self.paused_event = threading.Event()
        self.output_path = ""
        self.raw_output_path = ""
        self.socket_connection = None
        self.buffer =[]
        self.last_dump_time = None
        self.time_autosave = 10
        self.device_port = 4242
        self.screen_width = 0
        self.screen_height = 0
        self.workflow_status = 1
        self.pause_lock = threading.Lock()
        self.resume_offset = 0
        self.pause_start = 0
        self.capture_thread = None

    def unload(self):
        self.capture_event.clear()
        self.paused_event.set()
        if self.socket_connection:
            self.socket_connection.close()
            self.socket_connection = None

    def prepare(self, path: str, file_name: str):
        self.device_port = self.settings.get_setting("port") or 4242
        self.time_autosave = self.settings.get_setting("time_autosave") or 10

        self.output_path = os.path.join(path, f"{file_name}.txt")
        self.raw_output_path = os.path.join(path, f"{file_name}.raw")

        os.makedirs(path, exist_ok=True)

        open(self.output_path, 'w').close()
        open(self.raw_output_path, 'w').close()
        self.paused_event.set()
        self.last_dump_time = time.time()

    def start(self, start_ts: float, get_timestamp: Callable[[], float], on_data: Callable[[CaptureData], None]):
        self.recording_start_ts = start_ts
        self.get_timestamp = get_timestamp
        self.on_data = on_data

        self.capture_event.set()
        self.paused_event.set()
        self.workflow_status = 1

        self.capture_thread = threading.Thread(target=self.capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()

    def capture_loop(self):
        self.connect_gazepoint()
        self.setup_gazepoint()
        self.get_screen_size()

        with open(self.raw_output_path, 'w') as f:
            f.write("TIME_TICK|DATE|FPOGX|FPOGY|FPOGV|LPOGX|LPOGY|LPOGV|RPOGX|RPOGY|RPOGV|BPOGX|BPOGY|BPOGV|LPCX|LPCY|LPD|LPV|RPCX|RPCY|RPD|RPV|WIDTH|HEIGHT\n")
        start_time = time.time()
        while self.capture_event.is_set() and (time.time() - start_time) < MAX_RECORDING_TIME:
            self.paused_event.wait()
            
            if self.workflow_status == 0:
                break
                
            data = self.read_gazepoint_data()
            if data:
                current_ts = self.get_timestamp()
                self.on_data(CaptureData(timestamp=current_ts, data=data))
                self.process_data(data, current_ts)
            time.sleep(0.001)

        self.disconnect_gazepoint()
        if self.buffer:
            self.dump_to_file()

    def connect_gazepoint(self):
        self.socket_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_connection.connect(('127.0.0.1', self.device_port))
        self.socket_connection.settimeout(0.1)

    def setup_gazepoint(self):
        commands = [
            '<SET ID="ENABLE_SEND_DATA" STATE="1" />',
            '<SET ID="ENABLE_SEND_POG_FIX" STATE="1" />',
            '<SET ID="ENABLE_SEND_POG_LEFT" STATE="1" />',
            '<SET ID="ENABLE_SEND_POG_RIGHT" STATE="1" />',
            '<SET ID="ENABLE_SEND_POG_BEST" STATE="1" />',
            '<SET ID="ENABLE_SEND_PUPIL_LEFT" STATE="1" />',
            '<SET ID="ENABLE_SEND_PUPIL_RIGHT" STATE="1" />',
            '<GET ID="SCREEN_SIZE" />',
        ]

        for cmd in commands:
            self.socket_connection.sendall(f"{cmd}\r\n".encode())
            time.sleep(0.05)

    def get_screen_size(self):
        response = self.socket_connection.recv(4096).decode('utf-8')
        messages = response.split('\r\n')
        for message in messages:
            if "SCREEN_SIZE" in message and "ACK" in message:
                parts = message.split('"')
                if len(parts) >= 7:
                    for i, part in enumerate(parts):
                        if part == " X=":
                            self.screen_width = int(parts[i + 1])
                        elif part == " Y=":
                            self.screen_height = int(parts[i + 1])
                            break
        if not (self.screen_width > 0 and self.screen_height > 0):
            self.screen_width = 1920
            self.screen_height = 1080

    def read_gazepoint_data(self):
        self.socket_connection.settimeout(1.0)
        data = self.socket_connection.recv(4096).decode('utf-8')
        
        if data:
            return self.parse_gazepoint_data(data)
        return None
    
    def parse_gazepoint_data(self, data_buffer: str):
        lines = data_buffer.split('\r\n')
        parsed_data = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if "SCREEN_SIZE" in line:           
                parts = line.split('"')
                if len(parts) >= 10:
                    for i, part in enumerate(parts):
                        clean_part = part.strip()
                        if clean_part == "W=":
                            self.screen_width = int(parts[i + 1])
                        elif clean_part == "H=":
                            self.screen_height = int(parts[i + 1])

                    if self.screen_width == 0:
                        self.screen_width = int(parts[7])
                    if self.screen_height == 0:
                        self.screen_height = int(parts[9])

            elif "REC" in line:
                try:
                    parts = line.split('"')
                    if len(parts) >= 50:
                        parsed_data = {
                            'fpogx': float(parts[1]), 'fpogy': float(parts[3]), 'fpogv': int(parts[11]),
                            'lpogx': float(parts[13]), 'lpogy': float(parts[15]), 'lpogv': int(parts[17]),
                            'rpogx': float(parts[19]), 'rpogy': float(parts[21]), 'rpogv': int(parts[23]),
                            'bpogx': float(parts[25]), 'bpogy': float(parts[27]), 'bpogv': int(parts[29]),
                            'lpcx': float(parts[31]), 'lpcy': float(parts[33]), 'lpd': float(parts[35]), 'lpv': parts[39],
                            'rpcx': float(parts[41]), 'rpcy': float(parts[43]), 'rpd': float(parts[45]), 'rpv': parts[49],
                            'raw_data': line 
                        }
                except ValueError:
                    continue

        return parsed_data
        
    def process_data(self, data: dict, timestamp: float):
        time_tick = int(timestamp * 1000)
        datetime_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        raw_line = (f"{time_tick}|{datetime_str}|"
                    f"{data['fpogx']:.5f}|{data['fpogy']:.5f}|{data['fpogv']}|"
                    f"{data['lpogx']:.5f}|{data['lpogy']:.5f}|{data['lpogv']}|"
                    f"{data['rpogx']:.5f}|{data['rpogy']:.5f}|{data['rpogv']}|"
                    f"{data['bpogx']:.5f}|{data['bpogy']:.5f}|{data['bpogv']}|"
                    f"{data['lpcx']:.5f}|{data['lpcy']:.5f}|{data['lpd']:.5f}|{data['lpv']}|"
                    f"{data['rpcx']:.5f}|{data['rpcy']:.5f}|{data['rpd']:.5f}|{data['rpv']}|"
                    f"{self.screen_width}|{self.screen_height}\n")
        self.buffer.append(raw_line)

        if time.time() - self.last_dump_time >= self.time_autosave:
            self.dump_to_file()

    def pause(self, pause_ts: float):
        if not self.capture_event.is_set() or not self.paused_event.is_set():
            return
        self.paused_event.clear()
        self.workflow_status = 2
        self.pause_start = pause_ts

    def resume(self, resume_ts: float):
        if not self.capture_event.is_set() or self.paused_event.is_set():
            return
        self.paused_event.set()
        self.workflow_status = 1
        self.resume_offset = resume_ts -self.pause_start

    def stop(self, stop_ts: float):
        self.capture_event.clear()
        self.paused_event.set()
        self.workflow_status = 0

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)

    def save(self, data: list[CaptureData], end_of_data: bool = False):
        if self.buffer:
            self.dump_to_file()

        if end_of_data:
            self.formatt_final_output()
            
    def dump_to_file(self):
        if self.buffer:
            with open(self.raw_output_path, 'a') as f:
                f.writelines(self.buffer)
            self.buffer.clear()
        self.last_dump_time = time.time()

    def disconnect_gazepoint(self):
        if self.socket_connection:
            self.socket_connection.close()
            self.socket_connection = None
    
    def formatt_final_output(self):
        if not os.path.exists(self.raw_output_path):
            return
        
        with open(self.raw_output_path, 'r') as raw_file, open(self.output_path, 'w') as out_file:
            next(raw_file)
            
            for line in raw_file:
                parts = line.strip().split('|')
                if len(parts) < 24:
                    continue

                formatted_line = self.format_gaze_line(parts)
                out_file.write(formatted_line)

    def format_gaze_line(self, parts: list) -> str:
        time_tick = parts[0]

        fpogx = float(parts[2]) * self.screen_width
        fpogy = float(parts[3]) * self.screen_height
        fpogv = parts[4]

        lpogx = float(parts[5]) * self.screen_width
        lpogy = float(parts[6]) * self.screen_height
        lpogv = parts[7]

        rpogx = float(parts[8]) * self.screen_width
        rpogy = float(parts[9]) * self.screen_height
        rpogv = parts[10]

        bpogx = float(parts[11]) * self.screen_width
        bpogy = float(parts[12]) * self.screen_height
        bpogv = parts[13]

        lpcx = float(parts[14]) * self.screen_width
        lpcy = float(parts[15]) * self.screen_height
        lpd = parts[16]
        lpv = parts[17]

        rpcx = float(parts[18]) * self.screen_width
        rpcy = float(parts[19]) * self.screen_height
        rpd = parts[20]
        rpv = parts[21]

        formatted = f"t:{time_tick} st:7"

        formatted += f" fx:{str(fpogv == '1').lower()}"

        formatted += f" sm:{fpogx:.1f};{fpogy:.1f}"
        formatted += f" rw:{bpogx:.1f};{bpogy:.1f}"

        formatted += f" lsm:{lpogx:.1f};{lpogy:.1f}"
        formatted += f" lrw:{lpogx:.1f};{lpogy:.1f}"
        formatted += f" lpc:{lpcx:.1f};{lpcy:.1f}"
        formatted += f" lps:{lpd}"

        formatted += f" rsm:{rpogx:.1f};{rpogy:.1f}"
        formatted += f" rrw:{rpogx:.1f};{rpogy:.1f}"
        formatted += f" rpc:{rpcx:.1f};{rpcy:.1f}"
        formatted += f" rps:{rpd}"
        formatted += "\n"

        return formatted
    
    
    
    def get_file_extension(self) -> str:
        return "txt"
    
    def get_output_descriptor(self) -> dict[str, Any] | None:
        return {
            "format": "gaze_data",
            "version": "1.0",
            "fields": [
                "timestamp",
                "fixation_point",
                "left_eye_coordinates",
                "right_eye_coordinates",
                "pupil_measurements",
                "screen_dimensions"
            ],
            "coordinate_system": "screen_pixels",
            "data_rate": "variable"
        }