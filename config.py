import os
import json
import time
import sys

#APP_VERSION = "v2.1.3" #2025-11-23
APP_VERSION = "v2.1.4" #2026-09-11

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


# =================== MIDI TIMING & RESET DEFAULTS =====================
# Tunable via the "midi_timing" object in config.json.
DEFAULT_MIDI_TIMING = {
    # How to reset the Morningstar MC8 Pro before loading a song's bank:
    #   "always_pc127"   - Send PC 127 (MUTE) once before loading QC, then switch to target bank (safest, ~120ms)
    #   "same_bank_only" - Only hop via PC 127 when re-selecting the same MC8 bank; otherwise send CC3=127 (clear toggles)
    #   "cc3_clear"      - Skip PC 127; send Morningstar CC3=127 (Disengage All Toggles) before target bank
    #   "none"           - No MC8 reset before bank change
    "mc8_reset_mode": "always_pc127",
    # Settle time (ms) after PC 127 + QC PC before switching MC8 to target bank (runs QC load in parallel with MUTE)
    "pc127_settle_ms": 120,
    # Settle time (ms) after QC PC before sending follow-up CH1 CCs (e.g., QC Scene select CC 43)
    "qc_post_pc_cc_delay_ms": 120,
    # Settle time (ms) after MC8 PC before sending follow-up CH2 CCs (only waited when song has CH2 CCs)
    "mc8_post_pc_cc_delay_ms": 60,
    # Extra margin (ms) added to settle delays when running in Bluetooth (BT) mode
    "bt_extra_delay_ms": 40,
    # Clock reset before MC8 bank change:
    #   "mc8_pulse"  - Start MC8 Pro BPM via CC5/CC6 before bank change, then auto-stop (CC5=0, CC6=0) in background
    #   "mc8_stop"   - Instant MC8 Pro MIDI Clock Stop via CC5=0 + CC6=0 (<2ms)
    #   "mc8_cc"     - Instant MC8 Pro BPM set via CC5/CC6 (keeps clock running continuously)
    #   "none"       - Do not send clock from PC (clocks are set per-bank on MC8 / CH2)
    #   "midi_clock" - Legacy sendmidi clock burst (~1.33s blocking at 90 BPM)
    "clock_reset_mode": "mc8_pulse",
    "clock_reset_bpm": 90,
    # How long (ms) to let MC8 transmit clock in "mc8_pulse" mode before auto-stopping in background (~2 beats at 90 BPM)
    "clock_pulse_ms": 1500,
    # Minimum milliseconds between patch button clicks
    "button_debounce_ms": 400,
}

def get_midi_timing(conf=None):
    """Returns effective MIDI timing settings merged with defaults."""
    if conf is None:
        conf = load_config()
    timing = dict(DEFAULT_MIDI_TIMING)
    user_timing = conf.get("midi_timing")
    if isinstance(user_timing, dict):
        timing.update(user_timing)
    return timing

# =================== GLOBAL CONFIG MANAGEMENT =====================
def save_config(device=None, csv_file_used=None, relaunch_on_monitor_fail=None, 
                current_setlist_display_name=None, usb_lock_active=None, debug_enabled=None,
                ch1_override_active=None, # --- !! NEW !! ---
                DEVICE_NAME_BT=None, DEVICE_NAME_CH1=None, DEVICE_NAME_CH2=None,
                midi_timing=None, last_mode=None):
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
    if midi_timing is not None:
        config["midi_timing"] = midi_timing
    if last_mode is not None:
        config["last_mode"] = last_mode
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