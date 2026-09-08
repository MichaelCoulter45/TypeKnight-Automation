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
    reader = easyocr.Reader(['en'], gpu=True)
    camera.start(region=crop_region, target_fps=60)
    history = {}
    while True:
        if bot_active:
            current_time = time.time()
            frame = camera.get_latest_frame()
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                
                binary_frame = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                kernel = np.array([[0, 0, 0],
                    [-1, 5, -1],
                    [0, 0, 0]])
                binary_frame = cv2.filter2D(binary_frame, -1, kernel)
                _, binary_frame = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)
                
                cv2.imwrite("./debug_frame.png", binary_frame)
                # Remove contrast_ths/adjust_contrast that suppresses OCR
                results = reader.readtext(
                    binary_frame,
                    detail=1,
                    paragraph=False,
                    allowlist='abcdefghijklmnopqrstuvwxyz',
                )
                
                best_fallback = None
                best_fallback_conf = 0

                for (bbox, word, confidence) in results:
                    # print(f"RAW: '{word}' conf={confidence:.2f}") 
                    word = word.lower().strip()
                    if word and word != '':
                        suggestions = d.suggest(word)
                        if suggestions:
                            suggestions = suggestions[0].lower().strip()
                        else:
                            suggestions = 'blocked'
                    if len(word) < 2:
                        continue

                    if confidence >= 0.70:
                        best = get_best_word(word)
                        if best and best not in history:
                            
                            win32gui.SetForegroundWindow(hwnd)
                            time.sleep(0.01)
                            print(f"Best: {best} | Word: {word} | Sugg: {suggestions}\n")
                            pyautogui.write(best)
                            pyautogui.press("backspace", presses=len(best))
                            
                            pyautogui.write(word)
                            pyautogui.press("backspace", presses=len(word))
                            
                            pyautogui.write(suggestions)
                            pyautogui.press("backspace", presses=len(suggestions))
                            
                            history[best] = current_time

                    # else:
                    #     # Track best low-confidence read as fallback
                    #     best = get_best_word(word)
                    #     if best and confidence > best_fallback_conf:
                    #         best_fallback = best
                    #         best_fallback_conf = confidence

                # After the loop, if nothing was typed and we have a fallback
                # if best_fallback and best_fallback not in history:
                #     print(f"FALLBACK ({best_fallback_conf:.2f}): {best_fallback}")
                #     win32gui.SetForegroundWindow(hwnd)
                #     time.sleep(0.01)
                #     pyautogui.write(best_fallback)
                #     pyautogui.press("backspace", presses=len(best_fallback))
                #     history[best_fallback] = current_time
                    
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
