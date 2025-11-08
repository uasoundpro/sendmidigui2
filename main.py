import sys
import os
import time
import traceback

# --- !! FIX: Set Working Directory !! ---
try: SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__)); os.chdir(SCRIPT_DIRECTORY)
except Exception as e: print(f"FATAL: Could not change working directory: {e}"); input("Press ENTER to exit."); sys.exit()

# --- !! DEBUGGER v3 !! ---
LOG_FILE_PATH = os.path.join(SCRIPT_DIRECTORY, "debug_log.txt")
if os.path.exists(LOG_FILE_PATH): os.remove(LOG_FILE_PATH)
def write_log(message):
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()); f.write(f"[{timestamp}] [main.py] {message}\n")
    except Exception as e: print(f"FATAL: Could not write log: {e}\n{message}")

# --- SCRIPT EXECUTION STARTS NOW ---
write_log("--- SCRIPT LAUNCHED ---")
# (Log basic info - kept for brevity)

try:
    write_log("Importing modules...")
    import tkinter as tk
    import config
    from gui import app, popups
    write_log("Imports successful.")

    def main():
        write_log("--- main() FUNCTION STARTED ---")

        # --- !! MODIFIED: Parse relaunch argument for MODE !! ---
        is_relaunch = False
        relaunch_mode = None
        relaunch_device = None # Get device from env var set by old instance

        for arg in sys.argv[1:]: # Check arguments after the script name
            if arg.startswith("--relaunch="):
                is_relaunch = True
                try:
                    relaunch_mode = arg.split("=", 1)[1] # Get mode (e.g., "USB_DIRECT" or "BT")
                    # Get the target device from the environment variable set by the previous instance
                    relaunch_device = os.environ.get("RELAUNCH_MIDI_DEVICE")
                    write_log(f"main(): --relaunch flag detected. Target Mode='{relaunch_mode}', Target Device='{relaunch_device}'")
                except IndexError:
                    write_log("main(): ERROR - --relaunch flag found but mode is missing. Defaulting to BT.")
                    relaunch_mode = "BT" # Fallback
                    relaunch_device = config.DEVICE_NAME_BT # Fallback
                break # Stop checking args once found
        # --- !! END MODIFICATION !! ---

        # 1. Load config
        write_log("main(): 1. Loading config...")
        conf = config.load_config()
        write_log(f"main(): Config loaded.")

        # 2. Set debug state
        write_log("main(): 2. Setting debug state in environment...")
        debug_state = conf.get("debug_enabled", False)
        os.environ["MIDI_DEBUG_ENABLED"] = str(debug_state)
        write_log(f"main(): MIDI_DEBUG_ENABLED set to: {debug_state}")

        # 3. Create root window and hide it
        write_log("main(): 3. Creating and hiding root window...")
        root = tk.Tk(); root.withdraw()
        write_log("main(): Root window hidden.")

        # 4a. Load device names (essential even on relaunch)
        config.reload_device_names(conf)
        write_log(f"main(): Device names loaded: CH1={config.DEVICE_NAME_CH1}, CH2={config.DEVICE_NAME_CH2}, BT={config.DEVICE_NAME_BT}")

        # 4b. Skip all setup/verification if this is a relaunch
        if not is_relaunch:
            write_log("main(): Not a relaunch. Proceeding with standard startup popups...")
            # First-time setup check
            if not config.DEVICE_NAME_CH1 or not config.DEVICE_NAME_CH2: # Check loaded names
                write_log("main(): Core device names MISSING. Running initial device setup...")
                popups.show_initial_device_setup(root)
                conf = config.load_config(); config.reload_device_names(conf)
            # Verification popup
            write_log("main(): Calling popups.show_device_verification()...")
            popups.show_device_verification(root)
            conf = config.load_config(); config.reload_device_names(conf) # Reload in case of changes
            write_log(f"main(): Device names after verification: CH1={config.DEVICE_NAME_CH1}, CH2={config.DEVICE_NAME_CH2}, BT={config.DEVICE_NAME_BT}")
            # Setlist Chooser
            write_log("main(): Calling popups.show_setlist_chooser()...")
            popups.show_setlist_chooser(root)
            # Mode Chooser
            write_log("main(): Calling popups.show_device_chooser()...")
            popups.show_device_chooser(root)
        else:
            write_log("main(): Relaunch detected, skipping ALL setup/chooser popups.")
            # --- !! MODIFIED: Set environment based on relaunch args !! ---
            if relaunch_mode and relaunch_device:
                 os.environ["MODE_TYPE"] = relaunch_mode
                 os.environ["MIDI_DEVICE"] = relaunch_device
                 write_log(f"main(): Setting environment for relaunch: MODE={relaunch_mode}, DEVICE={relaunch_device}")
            else:
                 # Fallback if args were somehow malformed (shouldn't happen with app.py changes)
                 os.environ["MODE_TYPE"] = "BT"
                 os.environ["MIDI_DEVICE"] = config.DEVICE_NAME_BT
                 write_log(f"main(): Relaunch args missing/invalid. Defaulting to BT mode.")
            # --- !! END MODIFICATION !! ---

        # 5. Un-hide root
        write_log("main(): 5. De-iconifying (showing) root window...")
        root.deiconify()
        write_log("main(): Root window is now visible.")

        # 6. Create main app
        write_log("main(): 6. Initializing gui.app.MidiSenderApp()...")
        main_app = app.MidiSenderApp(root)
        write_log("main(): MidiSenderApp initialized successfully.")

        # 7. Run main loop
        write_log("main(): 7. Starting root.mainloop()...")
        root.mainloop()
        write_log("main(): root.mainloop() finished.")
        write_log("--- SCRIPT FINISHED NORMALLY ---")

    if __name__ == "__main__":
        write_log("Script is __main__. Calling main()...")
        main()

except Exception as e:
    # (Crash handler unchanged - kept for brevity)
    write_log("--- SCRIPT CRASHED! ---")
    write_log(traceback.format_exc())
    print("--- SCRIPT CRASHED! ---")
    print(f"Error details written to debug_log.txt")
    traceback.print_exc()
    input("Press ENTER to close...")