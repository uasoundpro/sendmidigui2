import tkinter as tk
import os
import shutil
import subprocess
import config
import utils
import time
import sys
import traceback

# --- !! DEBUG LOGGING !! ---
try:
    POPUP_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.abspath(os.path.join(POPUP_SCRIPT_DIR, ".."))
    LOG_FILE_PATH = os.path.join(BASE_DIR, "debug_log.txt")
except Exception as e:
    print(f"FATAL: gui/popups.py cannot find log file path. {e}")

def write_log(message):
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            f.write(f"[{timestamp}] [gui.popups] {message}\n")
    except Exception as e:
        print(f"POPUP LOG FAIL: {e}. Message: {message}")
# --- !! END DEBUG LOGGING !! ---

# --- !! HELPER: ADD VERSION LABEL !! ---
def _add_version_label(popup_window):
    """Adds the version label to the top right of a Toplevel window."""
    try:
        tk.Label(
            popup_window,
            text=config.APP_VERSION,
            font=config.narrow_font_small,
            bg=config.DARK_BG,
            fg="#888888" # Subtle grey
        ).place(relx=1.0, rely=0, anchor="ne", x=-5, y=2) # Place in top-right corner
    except Exception as e:
        # Fallback in case config hasn't loaded
        tk.Label(
            popup_window,
            text="v?.?.?",
            font=("Arial", 9),
            bg="#1e1e1e",
            fg="#888888"
        ).place(relx=1.0, rely=0, anchor="ne", x=-5, y=2)
        write_log(f"Error adding version label: {e}")
# --- !! END HELPER !! ---


# --- !! HELPER: GET DEVICE LIST !! ---
def _get_device_list():
    """Internal helper to get MIDI devices."""
    try:
        # Use CREATE_NO_WINDOW to prevent flash
        result = subprocess.run([config.SENDMIDI_PATH, "list"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        device_list = result.stdout.strip().splitlines()
        # Filter out common junk devices
        filtered_list = [dev for dev in device_list if "Microsoft GS" not in dev and "MIDIOUT" not in dev]
        if not filtered_list: # Handle case where only junk devices are found
            return ["No Devices Found"]
        return filtered_list
    except FileNotFoundError:
        write_log(f"Error: {config.SENDMIDI_PATH} not found.")
        return ["Error: sendmidi not found"]
    except Exception as e:
        write_log(f"Error listing devices in _get_device_list: {e}")
        return ["Error listing devices"]

# --- !! NEW DEVICE VERIFICATION POPUP !! ---
def show_device_verification(root):
    """
    Shows a popup to verify current MIDI device settings on every launch.
    Allows user to accept or proceed to change settings.
    """
    write_log("show_device_verification() called.")
    try:
        popup = tk.Toplevel(root)
        popup.title("Verify MIDI Devices")
        popup.configure(bg=config.DARK_BG)
        _add_version_label(popup) # <--- ADDED VERSION

        win_width = 600
        win_height = 350 # Adjusted height
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")
        write_log("Popup geometry set.")

        # --- !! Skip grab/transient as root is hidden !! ---
        # popup.grab_set()
        # popup.transient(root)
        write_log("Skipping grab_set() and transient().")
        # --- !! End Skip !! ---

        # Load current settings from config module (which main.py loaded)
        current_ch1 = config.DEVICE_NAME_CH1 if config.DEVICE_NAME_CH1 else "Not Set"
        current_ch2 = config.DEVICE_NAME_CH2 if config.DEVICE_NAME_CH2 else "Not Set"
        current_bt = config.DEVICE_NAME_BT if config.DEVICE_NAME_BT else "Not Set"

        # --- Widgets ---
        tk.Label(popup, text="Current MIDI Device Settings:",
                 font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=20)

        info_frame = tk.Frame(popup, bg=config.DARK_BG)
        info_frame.pack(pady=10, padx=30, fill="x")

        tk.Label(info_frame, text=f"CH1 (e.g., QC):  {current_ch1}",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG, justify="left").pack(anchor="w", pady=3)
        tk.Label(info_frame, text=f"CH2/USB (e.g., MC8):  {current_ch2}",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG, justify="left").pack(anchor="w", pady=3)
        tk.Label(info_frame, text=f"Bluetooth (e.g., loopMIDI):  {current_bt}",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG, justify="left").pack(anchor="w", pady=3)

        button_frame = tk.Frame(popup, bg=config.DARK_BG)
        button_frame.pack(pady=30)

        def on_ok():
            write_log("User accepted current device settings.")
            popup.destroy()

        def on_change():
            write_log("User chose to change device settings.")
            popup.destroy() # Close this verification popup first
            write_log("Calling show_initial_device_setup()...")
            show_initial_device_setup(root) # Now open the full setup
            write_log("Returned from show_initial_device_setup().")


        ok_button = tk.Button(button_frame, text="OK (Use These)", font=("Arial", 14),
                              bg="#2a8f44", fg="white", command=on_ok, width=15)
        ok_button.grid(row=0, column=0, padx=15)

        change_button = tk.Button(button_frame, text="Change Devices", font=("Arial", 14),
                                  bg="#b02f2f", fg="white", command=on_change, width=15)
        change_button.grid(row=0, column=1, padx=15)

        write_log("Calling root.wait_window(popup) for verification... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for verification has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_device_verification ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()

# --- !! END NEW POPUP !! ---


# --- DEVICE SETUP POPUP (Modified slightly for clarity/robustness) ---
def show_initial_device_setup(root):
    """
    Shows the setup popup to select MIDI device names.
    Can be called on first launch OR when user clicks 'Change Devices'.
    """
    write_log("show_initial_device_setup() called.")
    try:
        popup = tk.Toplevel(root)
        popup.title("MIDI Device Setup") # Changed title slightly
        popup.configure(bg=config.DARK_BG)
        _add_version_label(popup) # <--- ADDED VERSION

        win_width = 700
        # Increased height slightly for the refresh button
        win_height = 500
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")
        write_log("Popup geometry set.")

        # --- !! FIX: Comment out grab_set and transient AGAIN !! ---
        # These cause problems when root is hidden, even if called after another popup.
        # popup.grab_set()
        # popup.transient(root)
        write_log("Skipping grab_set() and transient() to prevent potential crash.")
        # --- !! END FIX !! ---

        # Get the list of actual MIDI devices
        initial_devices = _get_device_list()

        # Variables
        ch1_device_var = tk.StringVar(popup)
        ch2_device_var = tk.StringVar(popup)
        bt_device_var = tk.StringVar(popup)

        # --- Widgets ---
        tk.Label(popup, text="Please map your MIDI devices:", # Changed text slightly
                 font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=20)

        main_frame = tk.Frame(popup, bg=config.DARK_BG)
        main_frame.pack(pady=10, padx=20, fill="x")

        # Create OptionMenu widgets initially (will be populated/updated by _refresh_device_menus)
        ch1_menu = tk.OptionMenu(main_frame, ch1_device_var, *["Initializing..."])
        ch1_menu.config(font=config.narrow_font_plain, width=60)

        ch2_menu = tk.OptionMenu(main_frame, ch2_device_var, *["Initializing..."])
        ch2_menu.config(font=config.narrow_font_plain, width=60)

        bt_menu = tk.OptionMenu(main_frame, bt_device_var, *["Initializing..."])
        bt_menu.config(font=config.narrow_font_plain, width=60)

        # --- !! REFRESH FUNCTION !! ---
        def _refresh_device_menus():
            """Gets the latest device list and updates the OptionMenus."""
            write_log("Refreshing device list...")
            available_devices = _get_device_list()
            write_log(f"Found: {available_devices}")

            # Store currently selected values before clearing
            current_ch1_val = ch1_device_var.get()
            current_ch2_val = ch2_device_var.get()
            current_bt_val = bt_device_var.get()

            # Update CH1 menu
            menu1 = ch1_menu["menu"]
            menu1.delete(0, "end")
            for device in available_devices:
                menu1.add_command(label=device, command=tk._setit(ch1_device_var, device))
            # Try to restore selection, else default
            if current_ch1_val in available_devices:
                ch1_device_var.set(current_ch1_val)
            elif config.DEVICE_NAME_CH1 and config.DEVICE_NAME_CH1 in available_devices:
                 ch1_device_var.set(config.DEVICE_NAME_CH1)
            elif "Quad Cortex MIDI Control" in available_devices:
                 ch1_device_var.set("Quad Cortex MIDI Control")
            elif available_devices:
                ch1_device_var.set(available_devices[0])
            else:
                ch1_device_var.set("No Devices Found")


            # Update CH2 menu
            menu2 = ch2_menu["menu"]
            menu2.delete(0, "end")
            for device in available_devices:
                menu2.add_command(label=device, command=tk._setit(ch2_device_var, device))
            # Try to restore selection, else default
            if current_ch2_val in available_devices:
                ch2_device_var.set(current_ch2_val)
            elif config.DEVICE_NAME_CH2 and config.DEVICE_NAME_CH2 in available_devices:
                ch2_device_var.set(config.DEVICE_NAME_CH2)
            elif "Morningstar MC8 Pro" in available_devices:
                ch2_device_var.set("Morningstar MC8 Pro")
            elif available_devices:
                ch2_device_var.set(available_devices[0])
            else:
                 ch2_device_var.set("No Devices Found")

            # Update BT menu
            menu3 = bt_menu["menu"]
            menu3.delete(0, "end")
            for device in available_devices:
                menu3.add_command(label=device, command=tk._setit(bt_device_var, device))
            # Try to restore selection, else default
            if current_bt_val in available_devices:
                 bt_device_var.set(current_bt_val)
            elif config.DEVICE_NAME_BT and config.DEVICE_NAME_BT in available_devices:
                bt_device_var.set(config.DEVICE_NAME_BT)
            elif "loopMIDI Port" in available_devices:
                 bt_device_var.set("loopMIDI Port")
            elif available_devices:
                bt_device_var.set(available_devices[0])
            else:
                bt_device_var.set("No Devices Found")
            write_log("Device menus refreshed.")
        # --- !! END REFRESH FUNCTION !! ---

        # Initial population
        _refresh_device_menus()


        # --- CH1 (Quad Cortex) ---
        tk.Label(main_frame, text="CH1 Device (e.g., Quad Cortex):",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG).pack(anchor="w")
        ch1_menu.pack(fill="x", pady=(5, 15))

        # --- CH2 (Morningstar MC8) ---
        tk.Label(main_frame, text="CH2 / USB Device (e.g., Morningstar MC8):",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG).pack(anchor="w")
        ch2_menu.pack(fill="x", pady=(5, 15))

        # --- BT (loopMIDI) ---
        tk.Label(main_frame, text="Bluetooth Device (e.g., loopMIDI Port):",
                 font=config.narrow_font_plain, bg=config.DARK_BG, fg=config.DARK_FG).pack(anchor="w")
        bt_menu.pack(fill="x", pady=(5, 15))

        # --- Button Frame ---
        button_frame = tk.Frame(popup, bg=config.DARK_BG)
        button_frame.pack(pady=20)

        # --- !! REFRESH BUTTON !! ---
        refresh_button = tk.Button(button_frame, text="Refresh List", font=("Arial", 12),
                                   bg="#444444", fg="white", command=_refresh_device_menus)
        refresh_button.grid(row=0, column=0, padx=20)
        # --- !! END REFRESH BUTTON !! ---

        def on_save():
            write_log("Saving selected device setup...")
            new_ch1 = ch1_device_var.get()
            new_ch2 = ch2_device_var.get()
            new_bt = bt_device_var.get()

            # Prevent saving if error messages are selected
            if "Error" in new_ch1 or "Error" in new_ch2 or "Error" in new_bt or \
               "No Devices" in new_ch1 or "No Devices" in new_ch2 or "No Devices" in new_bt:
                write_log("Save prevented due to error/no device selection.")
                # Optionally show a message to the user here
                tk.Label(popup, text="Cannot save with 'Error' or 'No Devices Found'. Please refresh and select valid devices.",
                         fg="red", bg=config.DARK_BG).pack(pady=5)
                return


            config.save_config(
                DEVICE_NAME_CH1=new_ch1,
                DEVICE_NAME_CH2=new_ch2,
                DEVICE_NAME_BT=new_bt
            )
            # --- !! Reload names in config module immediately !! ---
            config.DEVICE_NAME_CH1 = new_ch1
            config.DEVICE_NAME_CH2 = new_ch2
            config.DEVICE_NAME_BT = new_bt
            # --- !! End Reload !! ---
            write_log("Save complete. Destroying setup popup.")
            popup.destroy()

        save_button = tk.Button(button_frame, text="Save and Continue", font=("Arial", 16),
                                bg="#2a8f44", fg="white", command=on_save)
        # Position Save button next to Refresh button
        save_button.grid(row=0, column=1, padx=20)


        write_log("Calling root.wait_window(popup) for device setup... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for device setup has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_initial_device_setup ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()

# --- END DEVICE SETUP POPUP ---


# --- SETLIST CHOOSER (Top Level) ---
# (Unchanged)
def show_setlist_chooser(root):
    write_log("show_setlist_chooser() called.")
    try:
        conf = config.load_config()
        write_log("Config loaded.")

        if conf.get("relaunch_on_monitor_fail"):
            write_log("Relaunch on fail detected. Skipping setlist prompt.")
            return
        write_log("Not a relaunch. Proceeding to create popup.")

        write_log("Creating Toplevel popup window...")
        popup = tk.Toplevel(root)
        write_log("Toplevel popup created.")
        
        popup.title("Load Setlist?")
        popup.configure(bg=config.DARK_BG)
        _add_version_label(popup) # <--- ADDED VERSION
        
        write_log("Calculating geometry...")
        win_width = 600
        win_height = 300
        popup.update_idletasks() 
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x}+{y}")
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
        write_log("Popup geometry set.")
        write_log("Skipping grab_set() and transient() to prevent crash.")

        def launch_with(file_path_for_csv, display_name):
            write_log(f"launch_with() called. Path: {file_path_for_csv}, Name: {display_name}")
            temp_path = config.CSV_FILE_DEFAULT
            if os.path.abspath(file_path_for_csv) != os.path.abspath(temp_path):
                write_log("Copying setlist file...")
                shutil.copyfile(file_path_for_csv, temp_path)
            
            write_log("Saving config...")
            config.save_config(csv_file_used=file_path_for_csv,
                                current_setlist_display_name=display_name)
            write_log("Destroying popup.")
            popup.destroy()

        def handle_default_launch():
            write_log("handle_default_launch() called.")
            launch_with(config.CSV_FILE_DEFAULT_SOURCE, "Default Songs")

        def choose_setlist_file():
            write_log("choose_setlist_file() called. Destroying this popup.")
            popup.destroy()
            write_log("Calling _show_setlist_file_picker().")
            _show_setlist_file_picker(root)

        write_log("Creating widgets for setlist chooser...")
        tk.Label(popup, text="Load Setlist or Default Songs?", font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=20)
        frame = tk.Frame(popup, bg=config.DARK_BG)
        frame.pack(pady=10)
        tk.Button(frame, text="Setlist", font=config.big_font, width=12, height=2,
                  command=choose_setlist_file, bg="#2a8f44", fg="white").grid(row=0, column=0, padx=10)
        tk.Button(frame, text="Default", font=config.big_font, width=12, height=2,
                  command=handle_default_launch, bg="#28578f", fg="white").grid(row=0, column=1, padx=10)
        write_log("Widgets created.")

        write_log("Calling root.wait_window(popup)... (Window should be visible NOW)")
        root.wait_window(popup) 
        write_log("root.wait_window(popup) has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_setlist_chooser ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()

# --- SETLIST FILE PICKER (Second Level) ---
# (Unchanged)
def _show_setlist_file_picker(root):
    write_log("_show_setlist_file_picker() called.")
    try:
        popup = tk.Toplevel(root)
        popup.title("Select Setlist File")
        popup.configure(bg=config.DARK_BG)
        _add_version_label(popup) # <--- ADDED VERSION
        
        write_log("Calculating geometry for setlist picker...")
        win_width = 600
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        x_offset = x + 40
        y_offset = y + 40
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x_offset}+{y_offset}")
        popup.geometry(f"{win_width}x{win_height}+{x_offset}+{y_offset}")
        
        write_log("Skipping grab_set() and transient() to prevent crash.")
        
        write_log("Setlist picker popup created and configured.")

        def process_selected_setlist(selected_setlist_path):
            write_log(f"process_selected_setlist() called with: {selected_setlist_path}")
            temp_csv = os.path.join(config.SCRIPT_PATH, "MidiList_Set.csv")
            write_log(f"Creating ordered CSV at: {temp_csv}")
            utils.create_ordered_setlist_csv(selected_setlist_path, config.CSV_FILE_DEFAULT_SOURCE, temp_csv)
            write_log("CSV created.")

            display_name = os.path.basename(selected_setlist_path).replace(".txt", "")
            try:
                with open(selected_setlist_path, "r", encoding="utf-8") as f:
                    first_line_content = f.readline().strip()
                    if first_line_content:
                        display_name = first_line_content
                write_log(f"Display name set to: {display_name}")
            except Exception as e:
                write_log(f"Error reading display name: {e}")

            config.save_config(csv_file_used=temp_csv,
                                current_setlist_display_name=display_name)
            write_log("Config saved. Destroying popup.")
            popup.destroy()


        tk.Label(popup, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=config.DARK_BG,
                 fg=config.DARK_FG).pack(pady=20)
        
        write_log("Creating canvas and scrollbar for setlist picker...")
        files_frame = tk.Frame(popup, bg=config.DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)
        canvas = tk.Canvas(files_frame, bg=config.DARK_BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(files_frame, orient="vertical", command=canvas.yview,
                                 bg=config.SCROLLBAR_COLOR, troughcolor=config.DARK_BG, highlightbackground=config.DARK_BG)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollable_buttons_frame = tk.Frame(canvas, bg=config.DARK_BG)
        canvas_frame = canvas.create_window((0, 0), window=scrollable_buttons_frame, anchor="nw")
        scrollable_buttons_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)),
                                                                      "units") if canvas.winfo_exists() else None)
        write_log("Canvas and scrollbar created.")

        if not os.path.exists(config.SETLIST_FOLDER):
            write_log(f"Setlist folder not found. Creating: {config.SETLIST_FOLDER}")
            os.makedirs(config.SETLIST_FOLDER)

        write_log("Reading setlist files...")
        setlist_files = [f for f in os.listdir(config.SETLIST_FOLDER) if f.endswith(".txt")]
        if not setlist_files:
            write_log("No setlist files found.")
            tk.Label(scrollable_buttons_frame, text="No setlist files found.", font=config.narrow_font_plain, bg=config.DARK_BG,
                     fg=config.DARK_FG).pack(pady=10)
        else:
            write_log(f"Found {len(setlist_files)} setlist files. Creating buttons...")
            for sl_file in setlist_files:
                file_path = os.path.join(config.SETLIST_FOLDER, sl_file)
                first_line = ""
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if not first_line:
                            first_line = sl_file
                except Exception as e:
                    first_line = f"Error reading {sl_file}"
                    write_log(f"Error reading first line of {sl_file}: {e}")

                btn = tk.Button(scrollable_buttons_frame, text=first_line, font=("Arial", 13),
                                width=65, pady=13,
                                command=lambda path=file_path: process_selected_setlist(path),
                                bg=config.BUTTON_BG, fg=config.DARK_FG, activebackground=config.BUTTON_HL, activeforeground=config.DARK_FG)
                btn.pack(pady=5, padx=10)
            write_log("Setlist buttons created.")

        write_log("Calling root.wait_window(popup) for setlist picker... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for setlist picker has finished.")
    
    except Exception as e:
        write_log(f"--- CRASH in _show_setlist_file_picker ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()


# --- DEVICE CHOOSER (Mode Selection) ---
# (Unchanged)
def show_device_chooser(root):
    write_log("show_device_chooser() called.")
    try:
        conf = config.load_config()
        write_log("Config loaded.")

        if conf.get("relaunch_on_monitor_fail"):
            write_log("Relaunch on fail detected. Skipping device prompt.")
            device = conf.get("device", config.DEVICE_NAME_BT)
            os.environ["MIDI_DEVICE"] = device

            if device == config.DEVICE_NAME_CH2:
                os.environ["MODE_TYPE"] = "USB_DIRECT"
            elif device == config.DEVICE_NAME_BT:
                os.environ["MODE_TYPE"] = "BT"
            else:
                os.environ["MODE_TYPE"] = "CUSTOM_NO_RX"
            write_log(f"Environment set from config: {device}, {os.environ['MODE_TYPE']}")
            return
        write_log("Not a relaunch. Proceeding to create device chooser.")

        popup = tk.Toplevel(root)
        popup.title("Select MIDI Device Mode") # Changed title
        popup.configure(bg=config.DARK_BG)
        _add_version_label(popup) # <--- ADDED VERSION

        write_log("Calculating geometry for device chooser...")
        win_width = 900
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x}+{y}")
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")

        write_log("Skipping grab_set() and transient() to prevent crash.")

        write_log("Device chooser popup created and configured.")

        list_devices_popup_instance = None

        def select_device(mode, device_name):
            write_log(f"select_device() called with mode: {mode}, device: {device_name}")

            os.environ["MIDI_DEVICE"] = device_name
            os.environ["MODE_TYPE"] = mode
            config.save_config(device=device_name) # Save the *selected* device for this session
            write_log(f"Device saved to config. Destroying popup.")
            popup.destroy()

        def timeout_default():
            write_log("timeout_default() called.")
            if popup.winfo_exists():
                select_device("BT", config.DEVICE_NAME_BT)

        def select_from_list(device_name, window):
            write_log(f"select_from_list() called with: {device_name}")
            nonlocal list_devices_popup_instance
            window.destroy()
            list_devices_popup_instance = None

            mode_type = "UNKNOWN"
            actual_device_to_set = device_name

            if device_name == config.DEVICE_NAME_CH2:
                mode_type = "USB_DIRECT"
            elif device_name == config.DEVICE_NAME_BT:
                mode_type = "BT"
            elif device_name == config.DEVICE_NAME_CH1:
                actual_device_to_set = config.DEVICE_NAME_CH2
                mode_type = "USB_DIRECT"

            if mode_type == "UNKNOWN": mode_type = "CUSTOM_NO_RX"

            os.environ["MIDI_DEVICE"] = actual_device_to_set
            os.environ["MODE_TYPE"] = mode_type
            config.save_config(device=actual_device_to_set)
            write_log(f"Device selected from list. Destroying main chooser popup.")
            popup.destroy()

        def list_devices():
            write_log("list_devices() called.")
            nonlocal list_devices_popup_instance
            if list_devices_popup_instance and list_devices_popup_instance.winfo_exists():
                list_devices_popup_instance.lift()
                return

            device_list = _get_device_list() # Use helper
            write_log(f"Found devices: {device_list}")

            if not device_list or "Error" in device_list[0]:
                write_log("No MIDI devices found or error.")
                # Maybe show a small error message here?
                return

            list_window = tk.Toplevel(popup)
            _add_version_label(list_window) # <--- ADDED VERSION
            list_devices_popup_instance = list_window

            def on_list_devices_popup_close():
                write_log("list_devices popup closed by user.")
                nonlocal list_devices_popup_instance
                list_devices_popup_instance = None
                list_window.destroy()

            list_window.protocol("WM_DELETE_WINDOW", on_list_devices_popup_close)

            list_window.title("Available MIDI Devices")
            list_window.configure(bg=config.DARK_BG)

            win_width_list = 400
            win_height_list = 600
            list_window.update_idletasks()
            screen_width_list = list_window.winfo_screenwidth()
            screen_height_list = list_window.winfo_screenheight()
            x_list = (screen_width_list // 2) - (win_width_list // 2)
            y_list = (screen_height_list // 2) - (win_height_list // 2)
            x_list_offset = x_list - 200
            y_list_offset = y_list + 50
            write_log(f"List_devices popup geometry: +{x_list_offset}+{y_list_offset}")
            list_window.geometry(f"{win_width_list}x{win_height_list}+{x_list_offset}+{y_list_offset}")

            tk.Label(list_window, text="Select a MIDI Device:", font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=10)
            
            # Simplified device display logic
            for dev in device_list:
                 tk.Button(list_window, text=dev, font=config.narrow_font_plain, width=40, pady=10,
                          bg=config.BUTTON_BG, fg=config.DARK_FG,
                          command=(lambda d=dev: select_from_list(d, list_window))).pack(pady=5)
            # No disabled list needed here as we filter in _get_device_list

            write_log("List devices popup created.")


        write_log("Creating main widgets for device chooser...")
        tk.Label(popup, text="Select MIDI Device Mode:", bg=config.DARK_BG, fg=config.DARK_FG, font=config.big_font).pack(pady=10)
        btn_frame = tk.Frame(popup, bg=config.DARK_BG)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="BT (Default)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("BT", config.DEVICE_NAME_BT), bg="#2a8f44", fg="white").grid(row=0, column=0, pady=5, padx=5)
        tk.Button(btn_frame, text="USB Direct\n(Uses receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("USB_DIRECT", config.DEVICE_NAME_CH2), bg="#b02f2f", fg="white").grid(row=1, column=0, pady=5, padx=5)
        tk.Button(btn_frame, text="Hybrid\n(No receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("HYBRID", config.DEVICE_NAME_CH2), bg="#28578f", fg="white").grid(row=2, column=0, pady=5, padx=5)

        initial_debug_state = conf.get("debug_enabled", False)
        debug_var = tk.BooleanVar(value=initial_debug_state)

        def toggle_debug_logging():
            write_log(f"Debug logging toggled to: {debug_var.get()}")
            config.save_config(debug_enabled=debug_var.get())

        tk.Checkbutton(popup, text="Enable MIDI Debug Logging (Prints commands to console)",
                       variable=debug_var, command=toggle_debug_logging, bg=config.DARK_BG,
                       fg=config.DARK_FG, selectcolor=config.DARK_BG, activebackground=config.DARK_BG,
                       activeforeground=config.DARK_FG, font=config.narrow_font_plain).pack(pady=(20, 10))

        tk.Button(popup, text="List MIDI Devices", font=config.narrow_font_plain, command=list_devices,
                  bg="#444444", fg=config.DARK_FG, bd=0, padx=6, pady=6, height=2).pack(pady=5)

        timer_label = tk.Label(popup, text="", bg=config.DARK_BG, fg=config.DARK_FG, font=config.narrow_font_plain)
        timer_label.pack(pady=5)
        timer_count = [15]
        write_log("Starting countdown timer...")
        def countdown():
            if popup.winfo_exists() and timer_count[0] > 0:
                timer_label.config(text=f"Defaulting to BT in {timer_count[0]}s")
                timer_count[0] -= 1
                popup.after(1500, countdown)
            elif popup.winfo_exists() and timer_count[0] == 0:
                write_log("Countdown finished. Timing out to default.")
                timeout_default()
        countdown()

        write_log("Calling root.wait_window(popup) for device chooser... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for device chooser has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_device_chooser ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()

