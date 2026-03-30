import subprocess
import time
import os

# --- Configuration ---
# Updated to the exact device name!
TARGET_DEVICE = "Morningstar MC6 Pro" 

# Assumes this script is in the same directory as your sendmidi folder
SENDMIDI_PATH = os.path.join("sendmidi", "sendmidi.exe") 

def send_midi_command(command_args):
    """Helper function to execute sendmidi.exe with the given arguments."""
    full_cmd = [SENDMIDI_PATH, "dev", TARGET_DEVICE] + command_args
    print(f"Sending: {' '.join(full_cmd)}")
    
    try:
        # creationflags=0x08000000 hides the console window popup on Windows
        subprocess.run(full_cmd, check=True, creationflags=0x08000000)
    except FileNotFoundError:
        print(f"\n[ERROR] Could not find sendmidi.exe at {SENDMIDI_PATH}")
        print("Make sure you are running this script from your main app folder.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Failed to send command. sendmidi returned error code {e.returncode}.")
    except Exception as e:
        print(f"\n[ERROR] Failed to send command: {e}")

def run_test_sequence():
    print(f"\n=== Triggering Dual Reset Test on '{TARGET_DEVICE}' ===")

    # The reset wave (PC 127)
    ch3_127 = ["ch", "3", "pc", "127"]
    ch4_127 = ["ch", "4", "pc", "127"]

    # The post-reset wave (PC 126)
    ch3_126 = ["ch", "3", "pc", "126"]
    ch4_126 = ["ch", "4", "pc", "126"]

    # --- WAVE 1 ---
    print(">>> WAVE 1: Sending PC 127...")
    send_midi_command(ch3_127)
    send_midi_command(ch4_127)

    print("...waiting 1.5 seconds...")
    time.sleep(1.5)

    # --- WAVE 2 ---
    print(">>> WAVE 2: Sending PC 127...")
    send_midi_command(ch3_127)
    send_midi_command(ch4_127)

    print("...waiting 1.5 seconds...")
    time.sleep(1.5)

    # --- WAVE 3 ---
    print(">>> WAVE 3: Sending PC 126...")
    send_midi_command(ch3_126)
    send_midi_command(ch4_126)

    print("=== Sequence Complete ===\n")

if __name__ == "__main__":
    print("Starting Interactive MIDI Test Mode...")
    print(f"Target Device: {TARGET_DEVICE}")
    print("-" * 40)
    
    while True:
        try:
            # Wait for the user to press Enter
            user_input = input("Press ENTER to trigger a 'Song Change' (or type 'q' to quit): ")
            
            # Check if the user wants to exit
            if user_input.lower() in ['q', 'quit', 'exit']:
                print("Exiting test script.")
                break
                
            # Fire the MIDI commands
            run_test_sequence()
        except KeyboardInterrupt:
            # Catches Ctrl+C so it exits cleanly without an ugly traceback
            print("\nExiting test script.")
            break