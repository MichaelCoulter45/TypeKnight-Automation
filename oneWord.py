import win32gui
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
import itertools



# Keybinds
keybind_toggle = '.'

# Bot Stuff
active = False
bot_active = False
delay_cpu = 0.01
word = 'mmmm'



################# GUI Functions #################
def start_bot():
    global active
    if active == False:
        active = True
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
    else:
        print(f"Bot has already started!")


def toggle_bot():
    global bot_active
    bot_active = not bot_active
    if bot_active:
        print("✅ Bot Started!")
        status_label.config(text="✅ RUNNING", fg="green")
    else:
        print("⏸️ Pausing...")
        status_label.config(text="⏸️ PAUSED", fg="blue")
        





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
    while True:
        if bot_active:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.01)
            pyautogui.write(word)
            pyautogui.press("backspace", presses=len(word) + 1)



################### GUI ###################
root = tk.Tk()
root.title("Michael's Type Knight Bot")

tk.Label(root, text="Game Window:").grid(row=0, column=0, padx=5, pady=5)
window_entry = tk.Entry(root)
window_entry.insert(0, "Type Knight")
window_entry.grid(row=0, column=1, padx=5, pady=5)

tk.Label(root, text=f"Toggle Key: [ {keybind_toggle} ]").grid(row=2, column=0, padx=5, pady=5)

status_label = tk.Label(root, text="ENTER WINDOW TITLE", fg="orange")
status_label.grid(row=3, column=0, padx=5, pady=5)

start_button = ttk.Button(root, text=" ✅ Start ", command=start_bot)
start_button.grid(row=4, column=0, padx=5, pady=5)

quit_button = ttk.Button(root, text=" 🚫 Quit ", command=root.destroy)
quit_button.grid(row=4, column=1, padx=5, pady=5)

root.mainloop()