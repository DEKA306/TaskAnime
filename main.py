import sys
import time
import psutil
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage, QColor
import pynvml


app = QApplication(sys.argv)

def get_network_percent(nic="Wi-Fi"):
    global prev_net, prev_time

    now = psutil.net_io_counters(pernic=True).get(nic)
    stats = psutil.net_if_stats().get(nic)

    if not now or not stats or stats.speed <= 0:
        return 0

    now_time = time.time()

    sent = now.bytes_sent - prev_net.bytes_sent
    recv = now.bytes_recv - prev_net.bytes_recv
    elapsed = now_time - prev_time

    prev_net = now
    prev_time = now_time

    # 초당 전송량
    bps = (sent + recv) / elapsed

    # 링크 속도 → bytes/sec
    max_bps = stats.speed * 125000

    percent = (bps / max_bps) * 100
    return min(100, percent)



def get_active_bytes(interface="Wi-Fi"):
    net = psutil.net_io_counters(pernic=True)
    if interface in net:
        return net[interface].bytes_sent + net[interface].bytes_recv
    return 0


def load_config(path="config.txt"):
    cfg = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                cfg[key.strip()] = value.strip()
    return cfg


config = load_config()


# GPU 타입 초기화
if config["gpu"] == "nvidia":
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    gpu_type = "nvidia"
elif config["gpu"] == "radeon":
    handle = None
    gpu_type = "amd"

sprite_paths = []
order = (config["order"].split())
for i in order:
    if i == "cpu":
         sprite_paths.append("cpu/" + config["cpu"] + ".png")
    elif i == "gpu":
         sprite_paths.append("gpu/" + config["gpu"] + ".png")
    elif i == "ram":
         sprite_paths.append("ram/" + config["ram"] + ".png")
    elif i == "network":
         sprite_paths.append("network/" + config["network"] + ".png")
    elif i == "custom":
         sprite_paths.append("custom/" + config["custom"] + ".png")
    
print(sprite_paths)

frame_width = int(config["x_size"])
frame_height = int(config["y_size"])
scale = int(config["scale"])
x_pos = int(config["x_pos"])
y_pos = int(config["y_pos"])
distance = int(config["distance"])

custom_speed = int(config["custom_speed"])

labels = []
frames_list = []
indexes = []
timers = []
speeds = [100, 100, 100, 100, 100]


def process_image(pixmap):
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
            if r > 240 and g > 240 and b > 240:
                color.setAlpha(0)
            elif r < 15 and g < 15 and b < 15:
                color = QColor(40, 40, 40, a)
            image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


def make_timer(label, frames, idx_pointer, speed):
    def update_frame():
        idx_pointer[0] = idx_pointer[0] % len(frames)
        pix = frames[idx_pointer[0]].scaled(
            label.width(),
            label.height(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        label.setPixmap(pix)
        idx_pointer[0] += 1

    timer = QTimer()
    timer.timeout.connect(update_frame)
    timer.start(speed)
    return timer


# 스프라이트 로드
for i, path in enumerate(sprite_paths):
    label = QLabel()
    label.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
    label.setAttribute(Qt.WA_TranslucentBackground)
    label.resize(frame_width * scale, frame_height * scale)
    label.move(x_pos + i * ((frame_width * scale) + (distance * scale)), y_pos)

    sheet = QPixmap(path)
    sheet = process_image(sheet)
    num_frames = sheet.width() // frame_width
    frames = [sheet.copy(j * frame_width, 0, frame_width, frame_height) for j in range(num_frames)]

    labels.append(label)
    frames_list.append(frames)
    indexes.append(0)
    timers.append(make_timer(label, frames, [indexes[i]], speeds[i]))
    label.show()


# 초기값
prev_disk = psutil.disk_io_counters()
prev_net = psutil.net_io_counters(pernic=True)["Wi-Fi"]
prev_time = time.time()


def read_gpu_temp():  # AMD 온도용
    return 50


def get_gpu_percent():
    if gpu_type == "nvidia" and handle:
        return pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
    else:
        temp = read_gpu_temp()
        return min(100, max(0, (temp - 30) / 60 * 100))



def update_dynamic_speeds():
    global prev_disk

    base_speed = 10000 // int(config.get("speed", 100))

    cpu = psutil.cpu_percent(interval=0)
    ram = psutil.virtual_memory().percent
    gpu_percent = get_gpu_percent()


    # 네트워크 (%로 환산됨)
    net_percent = get_network_percent("Wi-Fi")

    # 속도 계산
    new_cpu_speed  = base_speed * (max(10, 200 - int(cpu * 1.5)))**2 // 20000
    new_gpu_speed  = base_speed * (max(10, 200 - int(gpu_percent * 1.5)))**2 // 20000
    new_ram_speed  = base_speed * (max(10, 200 - int(ram * 1.2)))**2 // 20000
    new_disk_speed = custom_speed

    # 네트워크는 퍼센트 기반
    if int(net_percent) == 0.0:
        new_net_speed = 5000000
    else:    
        new_net_speed  = base_speed * (max(1, 200 - int(net_percent * 1.5)))**4 // 800000000

    # 적용


    for i in range(len(order)):
            if order[i] == "cpu":
                 timers[i].setInterval(new_cpu_speed)
                 #print("cpu")
            elif order[i] == "gpu":
                 timers[i].setInterval(new_gpu_speed)
                 #print("gpu")
            elif order[i] == "ram":
                 timers[i].setInterval(new_ram_speed)
                 #print("ram")
            elif order[i] == "network":
                 timers[i].setInterval(new_net_speed)
                 #print("network")
            elif order[i] == "custom":
                 timers[i].setInterval(new_disk_speed)
                 #print("custom")
            #print(order[i], order)
             
    #timers[0].setInterval(new_cpu_speed)
    #timers[1].setInterval(new_gpu_speed)
    #timers[2].setInterval(new_ram_speed)
    #timers[3].setInterval(new_disk_speed)
    #timers[4].setInterval(new_net_speed)

    #print(new_net_speed)


# 1초마다 갱신
speed_timer = QTimer()
speed_timer.timeout.connect(update_dynamic_speeds)
speed_timer.start(1000)

sys.exit(app.exec_())
