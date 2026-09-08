import win32api, win32gui, win32con
import threading
import tkinter as tk
from tkinter import ttk
import keyboard
import time
import dxcam, cv2
import pyautogui
import easyocr
import numpy as np
import enchant
import pytesseract



# Tell pytesseract where the exe is
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# Keybinds
keybind_toggle = '.'


# Bot Stuff
bot_running = True
bot_active = False
delay_cpu = 0.5

d = enchant.Dict("en_US")

################# Functions #################
def start_bot():
    window_name = window_entry.get()
    
    if not window_name:
        status_label.config(text="ENTER WINDOW TITLE", fg="orange")
        return
    
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd == 0:
        status_label.config(text="WINDOW NOT FOUND", fg="red")
        return
    
    status_label.config(text="READY", fg="blue")
    keyboard.add_hotkey(keybind_toggle, toggle_bot)
    threading.Thread(target=typer_bot, daemon=True).start()


def toggle_bot():
    global bot_active
    bot_active = not bot_active
    if bot_active:
        print(f"✅ Bot Activated!")
        status_label.config(text="✅ RUNNING", fg="green")
    else:
        print(f"⏸️ Pausing...")
        status_label.config(text="⏸️ PAUSED", fg="blue")




################# Typing #################
def fix_muw(word):
    import itertools
    
    quick_fix = word.replace('u', 'w')
    if is_valid_word(quick_fix):
        return quick_fix
    
    # Define possible swaps
    swaps = [
        ('n', 'm'),
        ('m', 'n'),
        ('u', 'w'),
        ('w', 'u'),
        ('u', 'y'),  # add this
        ('y', 'u'),  # and this
        ('vv', 'w'),
        ('e', 'o'),
        ('o', 'e'),
    ]
    
    candidates = set()
    candidates.add(word)
    
    # Try single swaps
    for old, new in swaps:
        candidates.add(word.replace(old, new))
    
    
    # Triple swaps
    for (o1,n1),(o2,n2),(o3,n3) in itertools.combinations(swaps, 3):
        candidate = word.replace(o1,n1).replace(o2,n2).replace(o3,n3)
        candidates.add(candidate)
    
    for candidate in candidates:
        if is_valid_word(candidate):
            return candidate
    
    return None  # return None so caller knows it failed



custom_words = {'beadwork', 'welcomer', 'wormhole', 'beadwork', 'dimmers'}  
d = enchant.Dict("en_US")



def is_valid_word(word):
    return d.check(word) or word in custom_words



def get_best_word(word):
    if is_valid_word(word):
        return word.strip()
    
    # Try swaps first before enchant
    fixed = fix_muw(word)
    if fixed and is_valid_word(fixed):
        return fixed.strip()
    
    # Only fall back to enchant if swaps failed
    suggestions = d.suggest(word)
    if suggestions:
        top = suggestions[0].lower().strip()
        if abs(len(top) - len(word)) <= 2:
            return top
    
    # Last resort: return the swap result even if not in dictionary
    if fixed:
        return fixed
    
    return None



def extract_text_regions(gray):
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Back to targeting white text
    _, thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)
    
    cv2.imwrite("debug_thresh.png", thresh)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 20))
    dilated = cv2.dilate(thresh, kernel, iterations=3)
    
    cv2.imwrite("debug_dilated.png", dilated)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    regions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # h=217 seems to be the consistent word blob height
        # adjust the range slightly for tolerance
        if 180 < h < 250 and w > 100:
            pad = 5
            y1 = max(0, y - pad)
            y2 = min(gray.shape[0], y + h + pad)
            x1 = max(0, x - pad)
            x2 = min(gray.shape[1], x + w + pad)
            word_crop = gray[y1:y2, x1:x2]
            regions.append((x, word_crop))
            # print(f"Accepted: w={w} h={h}")
    
    regions.sort(key=lambda r: r[0])
    return regions




def find_shadow_boxes(gray):
    _, dark = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if 23 < h < 27 and w > 30:
            # Check how filled the contour is vs its bounding box
            contour_area = cv2.contourArea(cnt)
            bounding_area = w * h
            fill_ratio = contour_area / bounding_area if bounding_area > 0 else 0
            
            # print(f"Box: w={w} h={h} fill={fill_ratio:.2f}")
            
            # Shadow boxes are solid rectangles so fill ratio should be high
            if fill_ratio > 0.8:
                boxes.append((x, y, w, h))
                # print(f"Accepted: x={x} y={y} w={w} h={h}")
    
    return boxes




def scan_strips(gray, strip_height=30, step=10):
    results = []
    h, w = gray.shape
    
    for y in range(0, h - strip_height, step):
        strip = gray[y:y+strip_height, 0:w]
        
        # Check if strip has any white pixels worth OCRing
        white_pixels = cv2.countNonZero(cv2.threshold(strip, 200, 255, cv2.THRESH_BINARY)[1])
        if white_pixels < 50:  # skip mostly empty strips
            continue
        
        upscaled = cv2.resize(strip, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        _, upscaled = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        results.append(upscaled)
    
    return results




def isolate_labels(frame):
    b, g, r = cv2.split(frame)
    
    rg_diff = cv2.absdiff(r, g)
    rb_diff = cv2.absdiff(r, b)
    gb_diff = cv2.absdiff(g, b)
    max_diff = cv2.max(cv2.max(rg_diff, rb_diff), gb_diff)
    
    brightness = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Only use bright neutral - this is our clean signal
    bright_neutral = cv2.bitwise_and(
        cv2.threshold(max_diff, 15, 255, cv2.THRESH_BINARY_INV)[1],
        cv2.threshold(brightness, 180, 255, cv2.THRESH_BINARY)[1]
    )
    
    cv2.imwrite("debug_mask.png", bright_neutral)
    
    # Connect nearby letters into word blobs
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 5))
    dilated = cv2.dilate(bright_neutral, kernel, iterations=2)
    
    cv2.imwrite("debug_dilated.png", dilated)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0
        # print(f"Contour: w={w} h={h} ratio={aspect_ratio:.1f}")
        
        # Filter out contours that are too short to be words
        if aspect_ratio > 1.5 and w > 40 and 15 < h < 60:  # raised from 30 to 40
            boxes.append((x, y, w, h))
            # print(f"Accepted: w={w} h={h}")
    
    return boxes




def trim_vertical_noise(img):
    # Find rows that contain actual black pixels (text)
    row_darkness = np.sum(img == 0, axis=1)  # count black pixels per row
    text_rows = np.where(row_darkness > 3)[0]  # rows with more than 3 black pixels
    
    if len(text_rows) == 0:
        return img
    
    top = max(0, text_rows[0] - 10)
    bottom = min(img.shape[0], text_rows[-1] + 3)
    return img[top:bottom, :]






################# Main Loop #################
def typer_bot():
    window_name = window_entry.get()
    hwnd = win32gui.FindWindow(None, window_name)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    crop_region = (
        left + int(width * 0.05),
        top + int(height * 0.35),
        right - int(width * 0.05),
        bottom - int(height * 0.12)
    )
    
    camera = dxcam.create()
    camera.start(region=crop_region, target_fps=60)
    history = {}
    while True:
        if bot_active:
            current_time = time.time()
            frame = camera.get_latest_frame()
            if frame is not None:
                # Convert for both color isolation and OCR
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                
                boxes = isolate_labels(bgr_frame)
                
                for (x, y, w, h) in boxes:
                    pad_x = 4  # only pad horizontally
                    pad_y = 0  # no vertical padding, trust the contour height
                    y1 = max(0, y + pad_y)
                    y2 = min(gray.shape[0], y + h - pad_y)
                    x1 = max(0, x - pad_x)
                    x2 = min(gray.shape[1], x + w + pad_x)
                    
                    word_crop = gray[y1:y2, x1:x2]
                    
                    # Upscale the tight crop
                    upscaled = cv2.resize(word_crop, None, fx=10, fy=10, interpolation=cv2.INTER_CUBIC)
                    _, upscaled = cv2.threshold(upscaled, 100, 255, cv2.THRESH_BINARY)
                    upscaled = cv2.bitwise_not(upscaled)
                    # Apply after threshold and invert
                    upscaled = trim_vertical_noise(upscaled)
                    
                    # Remove small noise blobs before feeding to Tesseract
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                    upscaled = cv2.morphologyEx(upscaled, cv2.MORPH_OPEN, kernel)
                    
                    # Add border only horizontally, not vertically
                    upscaled = cv2.copyMakeBorder(upscaled, 0, 0, 20, 20, cv2.BORDER_CONSTANT, value=255)
                    
                    
                    
                    cv2.imwrite("debug_crop.png", upscaled)
                    
                    mean_val = cv2.mean(upscaled)[0]
                    # print(f"Mean brightness: {mean_val:.1f}")
                    
                    if mean_val < 210:
                        # print("Skipping dark crop")
                        continue  # skip entirely, won't reach the for loop
                    
                    
                    
                    
                    
                    
                    # Try multiple configs and print all results
                    configs = [
                        '--psm 7 --oem 3',
                        '--psm 8 --oem 3', 
                        '--psm 13 --oem 3',  # raw line, no preprocessing
                    ]

                    for cfg in configs:
                        result = pytesseract.image_to_string(
                            upscaled,
                            lang='eng',
                            config=f'{cfg} -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz'
                        ).strip()
                        print(f"Config {cfg}: '{result}'")
                    
                    
                    
                    
                    
                    word_result = pytesseract.image_to_data(
                        upscaled,
                        lang='eng',
                        config='--psm 7 --oem 3 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz',
                        output_type=pytesseract.Output.DICT
                    )
                    
                    for i, word in enumerate(word_result['text']):
                        word = word.lower().strip()
                        conf = int(word_result['conf'][i])
                        
                        if len(word) < 2:
                            continue
                        
                        # Accept anything Tesseract returns and let get_best_word validate it
                        # print(f"RAW: '{word}' conf={conf}")
                        
                        best = get_best_word(word)
                        if best is None:
                            continue
                        
                        best = best.lower().strip()
                        if best not in history:
                            print(f"Best: {best} | Raw: {word}")
                            win32gui.SetForegroundWindow(hwnd)
                            time.sleep(0.01)
                            pyautogui.write(best)
                            pyautogui.press("backspace", presses=len(best))
                            pyautogui.write(word)
                            pyautogui.press("backspace", presses=len(word))
                            history[best] = current_time
            history = {w: t for w, t in history.items() if current_time - t < 3}
        else:
            time.sleep(delay_cpu)






################### GUI ###################
root = tk.Tk()

root.title("Michael's Type Knight Bot")

tk.Label(root, text="Game Window:").grid(row=0,column=0,padx=5,pady=5)
window_entry = tk.Entry(root)
window_entry.insert(0, "Type Knight")
window_entry.grid(row=0,column=1,padx=5,pady=5)

tk.Label(root, text=f"Toggle Key: [ {keybind_toggle} ]").grid(row=2,column=0,padx=5,pady=5)

status_label = tk.Label(root,text="ENTER WINDOW TITLE", fg="orange")
status_label.grid(row=3,column=0,padx=5,pady=5)

start_button = ttk.Button(root, text=" ✅ Start ", command=start_bot)
start_button.grid(row=4,column=0,padx=5,pady=5)

quit_button = ttk.Button(root, text=" 🚫 Quit ", command=root.destroy)
quit_button.grid(row=4,column=1,padx=5,pady=5)

root.mainloop()
####################################
