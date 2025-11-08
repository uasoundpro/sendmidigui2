import os
import json
import time
import sys

APP_VERSION = "v2.1.2" #2025-11-02

# =================== FILE PATHS =====================
# Resolve the script's location
SCRIPT_PATH = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))

SENDMIDI_PATH = os.path.join(SCRIPT_PATH, "sendmidi", "sendmidi.exe")
RECEIVEMIDI_PATH = os.path.join(SCRIPT_PATH, "receivemidi", "receivemidi.exe")
CSV_FILE_DEFAULT = os.path.join(SCRIPT_PATH, "MidiList.csv")
CONFIG_FILE = os.path.join(SCRIPT_PATH, "config.json")
SETLIST_FOLDER = os.path.join(SCRIPT_PATH, "Setlist")
CSV_FILE_DEFAULT_SOURCE = os.path.join(SCRIPT_PATH, "MidiList-DEFAULT.csv")
ICON_FILE = os.path.join(SCRIPT_PATH, "sendmidi.ico")

# =================== MIDI DEVICE NAMES (NOW FLEXIBLE) =====================
# These will be populated by reload_device_names() from config.json
# Default values are provided as a fallback.
DEVICE_NAME_BT = "loopMIDI Port"
DEVICE_NAME_CH1 = "Quad Cortex MIDI Control" # CH1 (QC)
DEVICE_NAME_CH2 = "Morningstar MC8 Pro"   # CH2 (MC8) / USB_DIRECT / HYBRID

# --- !! NEW: Process name to monitor in BT Mode !! ---
# (Assumes the executable is named this. Change if needed.)
BT_PROCESS_MONITOR_NAME = "MIDIberry.exe" 
# --- !! END NEW !! ---

def reload_device_names(conf=None):
    """
    Loads device names from the config file into these global variables.
    """
    global DEVICE_NAME_BT, DEVICE_NAME_CH1, DEVICE_NAME_CH2
    
    if not conf:
        conf = load_config()
        
    DEVICE_NAME_BT = conf.get("DEVICE_NAME_BT", "loopMIDI Port")
    DEVICE_NAME_CH1 = conf.get("DEVICE_NAME_CH1", None) # None forces first-launch popup
    DEVICE_NAME_CH2 = conf.get("DEVICE_NAME_CH2", None) # None forces first-launch popup

# ================ DARK THEME COLORS ===============
DARK_BG = "#1e1e1e"
DARK_FG = "#ffffff"
BUTTON_BG = "#2d2d2d"
BUTTON_HL = "#3c3c3c"
DISABLED_BG = "#555555"
HIGHLIGHT_BG = "#5b82a7"
SCROLLBAR_COLOR = "#444444"
TOAST_YELLOW = "#f5c542"

# --- STATUS COLORS FOR CHECKBOX ---
USB_AVAILABLE_COLOR = "#2a8f44" # Green
USB_UNAVAILABLE_COLOR = "#b02f2f" # Red
USB_AVAILABLE_ACTIVE_COLOR = "#207030" # Darker Green for click active
USB_UNAVAILABLE_ACTIVE_COLOR = "#902020" # Darker Red for click active
# --- END STATUS COLORS ---

# --- !! NEW: BT Monitor App Colors !! ---
BT_MONITOR_OK_COLOR = "#2a8f44" # Green
BT_MONITOR_WARNING_COLOR = "#b02f2f" # Red
# --- !! END NEW !! ---

# =================== FONTS =====================
big_font = ("Comic Sans MS", 20)
narrow_font_plain = ("Arial", 10)
narrow_font_small = ("Arial", 9)


# =================== GLOBAL CONFIG MANAGEMENT =====================
def save_config(device=None, csv_file_used=None, relaunch_on_monitor_fail=None, 
                current_setlist_display_name=None, usb_lock_active=None, debug_enabled=None,
                ch1_override_active=None, # --- !! NEW !! ---
                DEVICE_NAME_BT=None, DEVICE_NAME_CH1=None, DEVICE_NAME_CH2=None):
    """Saves application configuration to config.json."""
    config = load_config() # Load existing config first
    
    if device is not None:
        config["device"] = device
    if csv_file_used is not None:
        config["csv_file_used"] = os.path.abspath(csv_file_used)  # Store absolute path
    if relaunch_on_monitor_fail is not None:
        config["relaunch_on_monitor_fail"] = relaunch_on_monitor_fail
    if current_setlist_display_name is not None:
        config["current_setlist_display_name"] = current_setlist_display_name
    if usb_lock_active is not None:
        config["usb_lock_active"] = usb_lock_active
    if debug_enabled is not None:
        config["debug_enabled"] = debug_enabled
        
    # --- !! NEW !! ---
    if ch1_override_active is not None:
        config["ch1_override_active"] = ch1_override_active
    # --- !! END NEW !! ---
        
    # --- !! NEWLY ADDED !! ---
    if DEVICE_NAME_BT is not None:
        config["DEVICE_NAME_BT"] = DEVICE_NAME_BT
    if DEVICE_NAME_CH1 is not None:
        config["DEVICE_NAME_CH1"] = DEVICE_NAME_CH1
    if DEVICE_NAME_CH2 is not None:
        config["DEVICE_NAME_CH2"] = DEVICE_NAME_CH2
    # --- !! END NEW !! ---
        
    config["last_run"] = time.time()  # Always update last_run
    
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_config():
    """Loads application configuration from config.json."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}  # handle corrupted config
    return {}