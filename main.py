from flask import Flask, Response, request
import io
import time

import pyautogui
import pygetwindow as gw
import psutil
import qrcode
from PIL import Image, ImageDraw, ImageFont
from mss import mss
from pyzbar.pyzbar import decode

app = Flask(__name__)

# 添加全局变量用于缓存
request_lock = False
last_qr_bytes = None
last_qr_time = 0

def qrmai_action():
    img_io = io.BytesIO()
    # 根据配置选择窗口标题
    window_title = "舞萌丨中二" if config.get('standalone_mode', False) else "微信"
    wechat = gw.getWindowsWithTitle(window_title)[0]
    if wechat.isMinimized:
        wechat.restore()
    wechat.activate()

    def move_click(x, y):
        pyautogui.moveTo(x, y)
        pyautogui.click()


    move_click(config["p1"][0], config["p1"][1])

    time.sleep(2)
    move_click(config["p2"][0], config["p2"][1])
    decoded_objects = None
    wechat.minimize()
    for i in range(config["decode"]["retry_count"]):
        time.sleep(config["decode"]["time"] / config["decode"]["retry_count"])
        with mss() as sct:
            # 截取整个屏幕
            screenshot = sct.grab(sct.monitors[1])  # monitors[1] 表示第一个显示器
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        # 解码二维码
        decoded_objects = decode(image)
        if decoded_objects and len(decoded_objects) > 0:
            break
        else:
            if i == 9:
                window = gw.getWindowsWithTitle("微信")[0]
                window.close()
                im = Image.new("L", (100, 100), "#FFFFFF")
                font= ImageFont.load_default(size=23)
                draw = ImageDraw.Draw(im)
                draw.text((0, 0), "Unable\nto load\nQRCode\n(Timeout)", font=font, fill="#000000")
                im.save(img_io, format='PNG')
                img_io.seek(0)

                return img_io
            print(f"二维码解码失败 过{config["decode"]["time"] / config["decode"]["retry_count"]}s后重试 ({i+1}/{config["decode"]["retry_count"]})")
    qr_img = qrcode.make(decoded_objects[0].data.decode("utf-8"))

    import os
    # 如果skin.png存在
    if "skin.png" in os.listdir():
        skin = Image.open("skin.png")
        qr_img = qr_img.convert('RGBA')
        width, height = qr_img.size
        for x in range(width):
            for y in range(height):
                r, g, b, a = qr_img.getpixel((x, y))  # 获取当前像素的颜色值
                if r > 200 and g > 200 and b > 200:  # 判断是否为接近白色的像素
                    qr_img.putpixel((x, y), (255, 255, 255, 0))  # 替换为透明像素
        qr_location_x = config["qr_location_x"]
        qr_location_y = config["qr_location_y"]
        qr_size = config["qr_size"]
        resized_qr = qr_img.resize((qr_size,qr_size))
        skin.paste(resized_qr, (qr_location_x,qr_location_y), mask=resized_qr)  # 使用 resize 后的图像作为 mask

        skin.save(img_io, format='PNG')
    else:
        qr_img.save(img_io, format='PNG')

    img_io.seek(0)

    '''window = gw.getWindowsWithTitle("微信")[0]
    #window.close()'''
    #检测进程，杀掉带有WeChatAppEx的进程（关闭微信内置浏览器窗口）
    for proc in psutil.process_iter(['name']):
        if "wechatappex" in proc.info['name'].lower():
            try:
                proc.kill()
            except:
                break
    #显示微信窗口
    wechat_windows = gw.getWindowsWithTitle("微信")
    wechat_window = wechat_windows[0]
    #最大化后是全屏，需要restore来恢复原来窗口大小
    wechat_window.maximize()
    wechat_window.restore()

    return img_io

@app.route('/qrmai')
def qrmai():
    if request.args.get('token') != config['token']:
        return Response('403 Forbidden', status=403)

    global request_lock, last_qr_bytes, last_qr_time

    current_time = time.time()
    cache_duration = config.get('cache_duration', 60)
    
    # 如果有正在进行的请求，等待直到请求完成
    while request_lock:
        time.sleep(0.5)
        print("等待请求完成...")
        
    # 检查缓存是否有效
    if last_qr_bytes and (current_time - last_qr_time) < cache_duration:
        return Response(io.BytesIO(last_qr_bytes), mimetype='image/png')

    # 设置锁
    request_lock = True
    try:
        img_io = qrmai_action()
        img_io.seek(0)
        last_qr_bytes = img_io.getvalue()
        last_qr_time = current_time
        return Response(io.BytesIO(last_qr_bytes), mimetype='image/png')
    finally:
        # 释放锁
        request_lock = False

if __name__ == '__main__':
    import json
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    app.run(host=config["host"], port=config["port"])