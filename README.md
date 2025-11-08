# 🚀 MIDI Patch Sender GUI

REVISION: 2.1.2
DATE:     2025-11-02

This is a dynamic Python-based graphical user interface (GUI) designed for musicians to quickly send MIDI Program Change (PC) and Control Change (CC) messages to connected MIDI devices. It is built for high reliability during live performance, with a focus on seamless "smart" switching between **Bluetooth** and **USB** (e.g., Morningstar MC8/Quad Cortex) connections.

---

## ✨ Key Features

* **Multi-Mode Operation:** Choose from three distinct operating modes at launch:
    * **BT (Bluetooth):** A stable, wireless "failsafe" mode.
    * **USB_DIRECT:** A high-performance, dual-device mode with MIDI pass-thru.
    * **HYBRID:** A flexible USB mode that supports automatic rerouting.
* **Automatic Failover (USB to BT):** If a required USB device disconnects while in `USB_DIRECT` or `HYBRID` mode, the application shows a warning and automatically relaunches in the stable **Bluetooth** mode.
* **Smart Failback (BT to USB):** If stable USB connection is re-detected while in **Bluetooth** mode, the application prompts with a 3-way choice to switch back to **USB Direct**, **USB Hybrid**, or **Stay on Bluetooth**.
* **External App Monitoring:** In BT mode, the app monitors for a required external app (e.g., `MIDIberry.exe`) and displays a clear warning on the main screen if it's not running.
* **USB Failover Lock:** A checkbox in the main GUI to **disable** the automatic failover/failback prompts, allowing continuous USB monitoring without interrupting the current session.
* **Manual CH1 Reroute (Hybrid Mode):** A checkbox to manually force MIDI Channel 1 messages to reroute to the Channel 2 device, even when the primary Channel 1 device is detected.
* **Safe Patch Sending:** On patch selection, the app sends a master "select" command (PC 127 to CH2), waits one second for hardware to "settle," then sends the rest of the patch commands.
* **Dynamic Setlist Loading:** Loads MIDI patches from a master `MidiList-DEFAULT.csv` or a gig-specific `.txt` setlist file from the `Setlist` folder.
* **Full Re-Configuration:** A button in the "Switch Mode" popup allows for a full application restart, re-triggering the initial device setup and verification popups.

---

## 🛠️ Setup and Requirements

### Dependencies

1.  **Python 3:** The script requires a Python 3 installation.
2.  **`psutil` Library:** Required for monitoring the external Bluetooth app.
    ```bash
    pip install psutil
    ```
3.  **sendmidi and receivemidi:** The external command-line tools `sendmidi.exe` and "receivemidi.exe" are required. These fantastic programs are the core of the app's MIDI communication.
    * Find them here: [gbevin/SendMIDI](https://github.com/gbevin/SendMIDI) and [gbevin/ReceiveMIDI](https://github.com/gbevin/ReceiveMIDI)
    * Place the executables in their respective folders (`/sendmidi/sendmidi.exe` and `/receivemidi/receivemidi.exe`).

### Recommended File Structure

Place all files in a dedicated folder, ensuring the following structure:

/Midi-Sender-App/ ├── main.py <-- The main script ├── config.py <-- Main configuration file ├── midi_manager.py <-- Core logic for modes & monitoring ├── utils.py <-- Setlist generation helper ├── gui/ │ ├── app.py <-- Main application GUI class │ └── popups.py <-- All startup/config popups ├── sendmidi/ │ └── sendmidi.exe <-- The external MIDI sender tool ├── receivemidi/ │ └── receivemidi.exe <-- The external MIDI receiver tool ├── MidiList-DEFAULT.csv <-- Master list of all available patches ├── config.json <-- (Auto-generated) Stores device names & settings ├── sendmidi.ico <-- (Optional) Window icon ├── Setlist/ <-- Folder for custom setlist files │ └── Your_Gig_Setlist.txt ├── Images/ │ └── setup-diagram-hybrid-mode.jpg └── MidiList_Set.csv <-- (Auto-generated) The currently active setlist

---

## ⚙️ Configuration

### 1. Main Configuration (`config.py`)

This file contains the primary variables for your setup.

* `DEVICE_NAME_CH1`: The exact name of your Channel 1 device (e.g., `"Quad Cortex MIDI Control"`).
* `DEVICE_NAME_CH2`: The exact name of your Channel 2 device (e.g., `"Morningstar MC8 Pro"`).
* `DEVICE_NAME_BT`: The exact name of your Bluetooth/virtual port (e.g., `"loopMIDI Port"`).
* `BT_PROCESS_MONITOR_NAME`: The process name of the app to monitor in BT mode (e.g., `"MIDIberry.exe"`).

*Note: The device names are set via a popup on first launch and stored in `config.json`.*

### 2. MIDI Commands (`MidiList-DEFAULT.csv`)

The core functionality relies on this master CSV file. Each row defines a patch button.

| Column | Description | Example Value |
| :--- | :--- | :--- |
| **Patch Label** | Name displayed on the button. | `DRIVE (JCM800)` |
| **PC Ch1 (QC)** | Program Change number for MIDI Channel 1. | `3` |
| **PC Ch2 (MC8)**| Program Change number for MIDI Channel 2. | `5` |
| **CC Ch1** | Optional: CC Channel. | `1` |
| **CC Num** | Optional: CC Number. | `47` |
| **CC Val** | Optional: CC Value. | `1` |

*Additional CC commands can be appended in sets of three (Ch, Num, Val).*

### 3. Setlist Files (`Setlist/*.txt`)

Create a plain text file (`.txt`) in the `Setlist` folder for each gig.

1.  The **first line** is used as the display name for the setlist (e.g., `STF @ Tiki Bar | 10-28-2025`).
2.  Subsequent lines are the **exact patch labels** (case-insensitive) from `MidiList-DEFAULT.csv`, in the desired order.

---

## 🏃 Usage

1.  **Run the script:** Run `main.py`.
2.  **Verify Devices:** A popup will show your configured devices. Click **"OK (Use These)"** or **"Change Devices"** to re-run the setup.
3.  **Load Setlist:** A prompt will appear asking to load a **Setlist** (from the `Setlist/` folder) or the **Default** songs (from `MidiList-DEFAULT.csv`).
4.  **Select Mode:** Choose your connection mode. This will default to **BT (Default)** after 15 seconds.
5.  **Main GUI:** The main application window will appear.
6.  **Click to Send:** Click a patch button. The app will send PC 127 (CH2), wait 1 second, and then send the rest of the patch data.
7.  **Switch Mode:** Click this to open a popup and switch modes on-the-fly. This popup also contains the **"Relaunch Full Device Configuration"** button.
8.  **USB Failover Lock:** Check this to **disable** the automatic failover/failback popups.
9.  **Force CH1 Reroute (Hybrid Only):** Check this to manually force Channel 1 messages to the Channel 2 device.

---

## 🚦 Operating Modes & Reliability

### 1. BT (Bluetooth) Mode
* **What it is:** The "failsafe" mode. All MIDI commands (CH1 and CH2) are sent to the single `DEVICE_NAME_BT` port.
* **Monitoring:**
    * **App Status:** Continuously checks if `BT_PROCESS_MONITOR_NAME` (e.g., `MIDIberry.exe`) is running. A warning is displayed on the GUI if it is not.
    * **Device Status:** If the `DEVICE_NAME_BT` port itself disappears, a critical error popup appears.
* **Smart Failback:** If *both* `DEVICE_NAME_CH1` and `DEVICE_NAME_CH2` are detected via USB for 10 seconds, a popup will ask if you want to switch to **USB Direct**, **USB Hybrid**, or **Stay on Bluetooth**.

### 2. USB_DIRECT Mode
* **What it is:** High-performance mode for a fully wired rig.
* **Routing:** Sends CH1 commands to the CH1 device and CH2 commands to the CH2 device. It also runs `receivemidi.exe` to allow MIDI data to pass *from* your CH2 controller *to* your CH1 device.
* **Failover:** Monitors *both* CH1 and CH2 devices. If **either** device disconnects, the app will (if not locked) trigger the failover sequence and restart in **BT Mode**.

### 3. HYBRID Mode
* **What it is:** A flexible USB mode that does **not** use `receivemidi.exe`.
* **Routing:**
    * Sends CH2 commands to the CH2 device.
    * Sends CH1 commands to the CH1 device *if it's connected*.
    * If the CH1 device is *not* connected, it **automatically reroutes** CH1 commands to the CH2 device.
* **Failover:** Monitors *only* the `DEVICE_NAME_CH2` device. If it disconnects, the app will (if not locked) restart in **BT Mode**. It does not failover if only CH1 disconnects, as it can reroute.