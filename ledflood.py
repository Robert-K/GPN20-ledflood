import requests, json, random, sys, websocket, threading, os
from time import sleep
from PIL import Image
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

requests.packages.urllib3.disable_warnings()

url = "https://pixel.gulas.ch/auth/api/pixels" # I'm sorry Paule
auths = [
    "Bearer xxx", # Authorization Headers go here, can be generated with GitLab logins
]
ws_url = "wss://pixel.gulas.ch/api/pixels/ws"

tmp_file = "koeri.png" # Image goes here, make sure it's 40x16

requests_count = 0
current_pixel = 0
size_x = 40
size_y = 16
painted_pixels = []

canvas = [[0 for x in range(size_x)] for y in range(size_y)]
tmp = [[0 for x in range(size_x)] for y in range(size_y)]


def get_new_pixel():
    while True:
        x = random.randint(0, 39)
        y = random.randint(0, 15)
        if (x, y) not in painted_pixels:
            painted_pixels.append((x, y))
            print(f"Random Pixel: {x} {y}")
            return (x, y)


def set_pixel(x, y, color, auth):
    prevcolor = canvas[y][x]
    canvas[y][x] = color
    global requests_count
    payload = json.dumps({"x": str(x), "y": str(y), "color": str(color)}).encode(
        "utf-8"
    )
    response = requests.post(
        url, payload, verify=False, headers={"Authorization": auth}
    )
    if response.status_code == 201:
        requests_count += 1
    else:
        canvas[y][x] = prevcolor
        print(response.content)
        os.execv(sys.executable, ["python"] + sys.argv)
        exit()


def random_pixel(auth):
    x = random.randint(0, size_x - 1)
    y = random.randint(0, size_y - 1)
    set_pixel(x, y, auth)


def next_pixel(auth):
    global current_pixel, size_x, size_y
    x = current_pixel % size_x
    y = int(current_pixel / size_y)
    print(f"Next Pixel: {x} {y} ({current_pixel})")
    set_pixel(x, y, "#ffffff", auth)
    current_pixel += 1


def loop_order():
    global requests_count
    while True:
        for auth in auths:
            next_pixel(auth)
        print(requests_count)
        sleep(10)


def loop_random():
    global requests_count
    while True:
        for auth in auths:
            pixel = get_new_pixel()
            set_pixel(pixel[0], pixel[1], "#ffffff", auth)
        print(requests_count)
        sleep(10)


def ws_message(ws, msg):
    global got_canvas
    data = json.loads(msg)
    if "update_full" in data:
        got_canvas = True
        update_canvas_full(data["update_full"]["pixels"])
    if "update_single" in data:
        pixel = data["update_single"]
        update_canvas_single(pixel.x, pixel.y, pixel.color)


def update_canvas_full(pixels):
    global canvas
    for i, pixel in enumerate(pixels):
        x = i % size_x
        y = int(i / size_x)
        canvas[y][x] = pixel


def update_canvas_single(x, y, color):
    global canvas
    canvas[y][x] = color


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb[0:3]


def hex_to_rgb(hex):
    return tuple(int(hex.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def load_template():
    global tmp
    im = Image.open(tmp_file)
    pixels = list(im.getdata())
    for i, pixel in enumerate(pixels):
        x = i % size_x
        y = int(i / size_x)
        tmp[y][x] = rgb_to_hex(pixel)


def color_diff(a, b):
    a_rgb = hex_to_rgb(str(a))
    b_rgb = hex_to_rgb(str(b))
    a_col = convert_color(
        sRGBColor(a_rgb[0] / 256, a_rgb[1] / 256, a_rgb[2] / 256), LabColor
    )
    b_col = convert_color(
        sRGBColor(b_rgb[0] / 256, b_rgb[1] / 256, b_rgb[2] / 256), LabColor
    )
    return delta_e_cie2000(a_col, b_col)


def set_tmp_pixel(auth):
    global canvas
    max_diff = 0
    max_x = 0
    max_y = 0
    for i in range(size_x * size_y):
        x = i % size_x
        y = int(i / size_x)
        diff = color_diff(tmp[y][x], canvas[y][x])
        if diff > max_diff:
            max_diff = diff
            max_x = x
            max_y = y
    if max_diff == 0:
        return
    print(f"TMP: {max_x} {max_y} | Diff: {'{:.2f}'.format(max_diff)}%")
    set_pixel(max_x, max_y, tmp[max_y][max_x], auth)


def set_tmp_pixel_simple(auth):
    global canvas
    f = 0
    while f < 1000:
        f += 1
        x = random.randint(0, size_x - 1)
        y = random.randint(0, size_y - 1)
        if tmp[y][x] != canvas[y][x]:
            print(f"TMP: {x} {y} | Random")
            set_pixel(x, y, tmp[y][x], auth)
            return


def loop_tmp():
    global requests_count
    while True:
        for auth in auths:
            set_tmp_pixel_simple(auth)
        calc_domination()
        print(f"Requests this run: {requests_count} | Domination: {domination * 100}%")
        sleep(10)


def calc_domination():
    global domination
    dominated = 0
    hostile = size_x * size_y
    for i in range(size_x * size_y):
        x = i % size_x
        y = int(i / size_x)
        if tmp[y][x] == canvas[y][x]:
            dominated += 1
        else:
            hostile += 1
    domination = dominated / (size_x * size_y)


def loop_user(auth):
    while True:
        set_tmp_pixel_simple(auth)
        sleep(10)


if len(sys.argv) > 1:
    print(sys.argv)
    current_pixel = int(sys.argv[1])

load_template()

ws = websocket.WebSocketApp(ws_url, on_message=ws_message)
ws_thread = threading.Thread(target=ws.run_forever)
ws_thread.daemon = True
ws_thread.start()

got_canvas = False

while not got_canvas:
    sleep(0.1)

user_threads = []
for auth in auths:
    thread = threading.Thread(target=loop_user, args=[auth])
    thread.daemon = True
    user_threads.append(thread)
    thread.start()
    sleep(1)

while True:
    calc_domination()
    print(
        f"Agents: {len(user_threads)} | Requests this run: {requests_count} | Domination: {domination * 100}%"
    )
    sleep(2)
