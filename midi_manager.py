import subprocess
import os
import time
import threading
import config
import traceback # Import traceback

# --- !! NEW: Import psutil for process checking !! ---
try:
    import psutil
    PSUTIL_AVAILABLE = True
    print("psutil loaded. Process monitoring enabled.")
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: 'psutil' library not found. Run 'pip install psutil' to enable app monitoring.")
# --- !! END NEW !! ---

class MidiManager:
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback
        # Use the flexible config variable
        self.midi_device = config.DEVICE_NAME_BT 
        self.mode_type = "BT"
        self.debug_enabled = False # Initial state

        self._receivemidi_process = None
        self._receivemidi_stdout_thread = None
        self._receivemidi_stderr_thread = None

        # Persistent sendmidi.exe -- process (used in HYBRID & BT modes to avoid ~140ms process startup per song)
        self._sendmidi_proc = None
        self._sendmidi_lock = threading.Lock()
        self._sendmidi_current_device = None
        self._sendmidi_current_channel = None

        # Use the flexible config variable
        self._ch1_override_active = False
        self._qc_midi_target_device = config.DEVICE_NAME_CH1

        self._usb_stable_start_time = None
        self._user_declined_usb_switch = False
        self._usb_disconnect_warning_shown = False
        self._bt_disconnect_warning_shown = False # <-- ADDED
        self._monitor_in_flight = False
        self._root = None

    def set_root(self, root):
        self._root = root

    def set_mode(self, device, mode, debug_state, ch1_override_active=None):
        self.close_persistent_sendmidi()
        self.midi_device = device
        self.mode_type = mode
        self.debug_enabled = debug_state # Set initial debug state here
        if ch1_override_active is not None:
            self._ch1_override_active = bool(ch1_override_active)
        print(f"MidiManager Mode Set: {mode} (Device: {device}, Debug: {debug_state})")

        # Respect CH1 override immediately in HYBRID mode instead of waiting for the 5s monitor poll
        if self.mode_type == "HYBRID" and self._ch1_override_active:
            self._qc_midi_target_device = config.DEVICE_NAME_CH2
        else:
            self._qc_midi_target_device = config.DEVICE_NAME_CH1

        if self.mode_type == "USB_DIRECT" or self.mode_type == "HYBRID":
            self._user_declined_usb_switch = False
            self._usb_disconnect_warning_shown = False
            
        self._bt_disconnect_warning_shown = False # <-- ADDED

        # Pre-warm persistent sendmidi in background for HYBRID/BT so the very first song click is instant
        if self._should_use_persistent_sendmidi():
            threading.Thread(target=self.warm_persistent_sendmidi, daemon=True).start()

    def set_ch1_override(self, enabled):
        """Immediately updates CH1 rerouting target when the Hybrid override checkbox is toggled."""
        self._ch1_override_active = bool(enabled)
        if self.mode_type == "HYBRID":
            self._qc_midi_target_device = config.DEVICE_NAME_CH2 if self._ch1_override_active else config.DEVICE_NAME_CH1
        else:
            self._qc_midi_target_device = config.DEVICE_NAME_CH1

    # --- !! ADDED THIS METHOD !! ---
    def set_debug_state(self, enabled):
        """Allows the GUI to update the debug state dynamically."""
        self.debug_enabled = enabled
        print(f"MidiManager debug state set to: {enabled}")
    # --- !! END ADDITION !! ---

    # --- !! NEW: Helper function to check for running process !! ---
    def _is_process_running(self, process_name):
        """
        Checks if a process with the given name is currently running.
        (Requires psutil to be installed)
        """
        if not PSUTIL_AVAILABLE:
            return None # Should be handled before calling, but as a safeguard
            
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'].lower() == process_name.lower():
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass # Process may have died as we were iterating
        except Exception as e:
            print(f"Error checking process list: {e}") # Log other errors
        return False
    # --- !! END NEW !! ---

    def _resolve_target_device(self, command):
        """Determines which MIDI output device should receive a given command."""
        target_device = self.midi_device
        if self.midi_device == config.DEVICE_NAME_CH2: # Covers both USB_DIRECT and HYBRID
            if len(command) > 1 and command[0] == "ch":
                channel_str = str(command[1])
                if channel_str == "2":
                    target_device = self.midi_device
                elif channel_str == "1":
                    target_device = self._qc_midi_target_device
        return target_device

    @staticmethod
    def _format_sendmidi_delay(delay_ms):
        """Formats milliseconds as a SendMIDI relative timestamp (+SS.MIL)."""
        total_ms = max(0, int(round(delay_ms)))
        seconds, ms = divmod(total_ms, 1000)
        return f"+{seconds:02d}.{ms:03d}"

    def build_sendmidi_batch_cmd(self, steps):
        """
        Compiles a list of MIDI commands and ['wait_ms', N] delays into a single
        sendmidi.exe command line, avoiding per-message process startup overhead.
        """
        full_cmd = [config.SENDMIDI_PATH]
        current_device = None
        current_channel = None
        has_midi_cmd = False

        for step in steps:
            if not step:
                continue

            if step[0] == "wait_ms":
                delay_ms = int(round(step[1])) if len(step) > 1 else 0
                if delay_ms > 0 and has_midi_cmd:
                    full_cmd.append(self._format_sendmidi_delay(delay_ms))
                continue

            target_device = self._resolve_target_device(step)
            if target_device != current_device:
                full_cmd.extend(["dev", target_device])
                current_device = target_device
                current_channel = None # Always re-declare channel after switching device

            if len(step) >= 2 and step[0] == "ch":
                ch_str = str(step[1])
                if ch_str != current_channel:
                    full_cmd.extend(["ch", ch_str])
                    current_channel = ch_str
                full_cmd.extend([str(arg) for arg in step[2:]])
            else:
                full_cmd.extend([str(arg) for arg in step])

            has_midi_cmd = True

        return full_cmd if has_midi_cmd else []

    def _should_use_persistent_sendmidi(self):
        """Persistent sendmidi -- is safe whenever receivemidi.exe is not holding MIDI ports."""
        return self.mode_type != "USB_DIRECT"

    def _drain_stream(self, stream, label):
        try:
            for line in stream:
                text = line.strip()
                if text and self.debug_enabled:
                    print(f"[sendmidi {label}]: {text}")
        except Exception:
            pass

    def _ensure_persistent_sendmidi_locked(self):
        """Starts persistent sendmidi.exe -- if not running. Must hold self._sendmidi_lock."""
        if self._sendmidi_proc is not None and self._sendmidi_proc.poll() is None:
            return self._sendmidi_proc

        self._sendmidi_current_device = None
        self._sendmidi_current_channel = None
        proc = subprocess.Popen(
            [config.SENDMIDI_PATH, "--"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._sendmidi_proc = proc
        if proc.stderr:
            threading.Thread(
                target=self._drain_stream,
                args=(proc.stderr, "stderr"),
                daemon=True,
            ).start()
        return proc

    def warm_persistent_sendmidi(self):
        """Pre-starts persistent sendmidi and opens the default target port."""
        if not self._should_use_persistent_sendmidi():
            return
        with self._sendmidi_lock:
            try:
                proc = self._ensure_persistent_sendmidi_locked()
                if self.midi_device:
                    proc.stdin.write(f'{self._quote_sendmidi_arg("dev")} {self._quote_sendmidi_arg(self.midi_device)}\n')
                    proc.stdin.flush()
                    self._sendmidi_current_device = self.midi_device
                    self._sendmidi_current_channel = None
            except Exception as e:
                if self.debug_enabled:
                    print(f"[MIDI DEBUG] Warmup of persistent sendmidi failed: {e}")
                self._close_persistent_sendmidi_locked()

    def _close_persistent_sendmidi_locked(self):
        proc = self._sendmidi_proc
        self._sendmidi_proc = None
        self._sendmidi_current_device = None
        self._sendmidi_current_channel = None
        if proc is not None:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def close_persistent_sendmidi(self):
        """Cleanly stops persistent sendmidi.exe -- so Windows releases MIDI port handles."""
        with self._sendmidi_lock:
            self._close_persistent_sendmidi_locked()

    @staticmethod
    def _quote_sendmidi_arg(arg):
        s = str(arg)
        if not s or any(ch.isspace() for ch in s) or '"' in s:
            return '"' + s.replace('"', '\\"') + '"'
        return s

    def _send_via_persistent_sendmidi(self, steps, guard=None):
        """
        Streams MIDI commands through the persistent sendmidi.exe -- process,
        handling ['wait_ms', N] pauses directly in Python so the call completes
        precisely when the last message has been dispatched.
        """
        # Split steps into contiguous chunks separated by wait_ms pauses
        chunks = []
        current_chunk = []
        for step in steps:
            if not step:
                continue
            if step[0] == "wait_ms":
                delay_ms = int(round(step[1])) if len(step) > 1 else 0
                if current_chunk:
                    chunks.append(("cmd", current_chunk))
                    current_chunk = []
                if delay_ms > 0:
                    chunks.append(("wait", delay_ms))
            else:
                current_chunk.append(step)
        if current_chunk:
            chunks.append(("cmd", current_chunk))

        if not any(kind == "cmd" for kind, _ in chunks):
            return False

        with self._sendmidi_lock:
            if guard is not None and not guard():
                return False
            proc = self._ensure_persistent_sendmidi_locked()
            debug_parts = []
            for kind, payload in chunks:
                if kind == "wait":
                    if debug_parts:
                        debug_parts.append(self._format_sendmidi_delay(payload))
                    time.sleep(payload / 1000.0)
                    continue

                if guard is not None and not guard():
                    return False

                tokens = []
                for step in payload:
                    target_device = self._resolve_target_device(step)
                    if target_device != self._sendmidi_current_device:
                        tokens.extend(["dev", self._quote_sendmidi_arg(target_device)])
                        self._sendmidi_current_device = target_device
                        self._sendmidi_current_channel = None

                    if len(step) >= 2 and step[0] == "ch":
                        ch_str = str(step[1])
                        if ch_str != self._sendmidi_current_channel:
                            tokens.extend(["ch", ch_str])
                            self._sendmidi_current_channel = ch_str
                        tokens.extend([self._quote_sendmidi_arg(arg) for arg in step[2:]])
                    else:
                        tokens.extend([self._quote_sendmidi_arg(arg) for arg in step])

                if tokens:
                    line = " ".join(tokens)
                    debug_parts.append(line)
                    proc.stdin.write(line + "\n")
                    proc.stdin.flush()

            if self.debug_enabled and debug_parts:
                print(f"[MIDI DEBUG] Persistent batch: {' '.join(debug_parts)}")
        return True

    def send_midi_batch(self, steps, guard=None):
        """
        Sends an entire sequence of MIDI messages + delays (persistent pipe in HYBRID/BT,
        one-shot in USB_DIRECT). Optional guard() is checked under the send lock to
        prevent stale background sends from racing with newer song clicks.
        Returns True if MIDI was actually dispatched, False if skipped by guard/empty steps.
        """
        if not steps:
            return False

        if guard is not None and not guard():
            return False

        if self._should_use_persistent_sendmidi():
            try:
                sent = self._send_via_persistent_sendmidi(steps, guard=guard)
                if sent:
                    if self.debug_enabled:
                        print("DEBUG: Sending MIDI_ACTIVITY signal (SENDING)")
                    self.gui_callback("MIDI_ACTIVITY", {"status": "SENDING"})
                return sent
            except Exception as e:
                print(f"[MIDI WARNING] Persistent sendmidi failed ({e}); respawning and falling back to one-shot.")
                self.close_persistent_sendmidi()

        if guard is not None and not guard():
            return False

        full_cmd = self.build_sendmidi_batch_cmd(steps)
        if not full_cmd:
            return False

        if self.debug_enabled:
            print(f"[MIDI DEBUG] Executing batch: {' '.join(full_cmd)}")
            print("DEBUG: Sending MIDI_ACTIVITY signal (SENDING)")

        self.gui_callback("MIDI_ACTIVITY", {"status": "SENDING"})
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        return True

    def send_midi(self, command_list):
        for command in command_list:
            target_device = self._resolve_target_device(command)

            full_cmd = [config.SENDMIDI_PATH, "dev", target_device]
            full_cmd.extend([str(arg) for arg in command])

            # This print is already conditional
            if self.debug_enabled:
                print(f"[MIDI DEBUG] Executing: {' '.join(full_cmd)}")

            # --- !! MADE THIS CONDITIONAL !! ---
            if self.debug_enabled:
                print("DEBUG: Sending MIDI_ACTIVITY signal (SENDING)")
            # --- !! END CHANGE !! ---
            self.gui_callback("MIDI_ACTIVITY", {"status": "SENDING"})

            # Use CREATE_NO_WINDOW to hide console flash for sendmidi
            subprocess.run(full_cmd, creationflags=subprocess.CREATE_NO_WINDOW)


    def _read_receivemidi_output(self, pipe, stream_name):
        while self._receivemidi_process and self._receivemidi_process.poll() is None:
            line = pipe.readline()
            if line:
                # --- !! MADE THIS CONDITIONAL !! ---
                if self.debug_enabled:
                    print("DEBUG: Sending MIDI_ACTIVITY signal (RECEIVING)")
                # --- !! END CHANGE !! ---
                self.gui_callback("MIDI_ACTIVITY", {"status": "RECEIVING"})
                print(f"[receivemidi {stream_name}]: {line.strip()}") # Keep this one always
            else:
                time.sleep(0.01)
        # Read remaining lines after process ends
        for line in pipe.readlines():
             # --- !! MADE THIS CONDITIONAL !! ---
            if self.debug_enabled:
                print("DEBUG: Sending MIDI_ACTIVITY signal (RECEIVING - final read)")
            # --- !! END CHANGE !! ---
            self.gui_callback("MIDI_ACTIVITY", {"status": "RECEIVING"})
            print(f"[receivemidi {stream_name}]: {line.strip()}") # Keep this one always
        print(f"receivemidi {stream_name} reader thread finished.")


    def kill_receivemidi(self):
        if self._receivemidi_process and self._receivemidi_process.poll() is None:
            try:
                print("Attempting to terminate receivemidi process...")
                self._receivemidi_process.terminate()
                self._receivemidi_process.wait(timeout=2)
                print("receivemidi process terminated.")
            except Exception as e:
                print(f"Error terminating receivemidi process: {e}")

        self._receivemidi_process = None

        if self._receivemidi_stdout_thread and self._receivemidi_stdout_thread.is_alive():
            self._receivemidi_stdout_thread.join(timeout=1)
        if self._receivemidi_stderr_thread and self._receivemidi_stderr_thread.is_alive():
            self._receivemidi_stderr_thread.join(timeout=1)

        self._receivemidi_stdout_thread = None
        self._receivemidi_stderr_thread = None
        print("receivemidi cleanup complete.")

    def start_receivemidi(self):
        if self.mode_type != "USB_DIRECT":
            return

        self.kill_receivemidi()

        try:
            # Use the flexible config variables
            receivemidi_cmd = [
                config.RECEIVEMIDI_PATH,
                "dev", config.DEVICE_NAME_CH2,
                "pass", config.DEVICE_NAME_CH1
            ]
            print(f"Launching receivemidi: {' '.join(receivemidi_cmd)}")
            self._receivemidi_process = subprocess.Popen(receivemidi_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                        text=True, creationflags=subprocess.CREATE_NO_WINDOW) # Hide console window

            self._receivemidi_stdout_thread = threading.Thread(target=self._read_receivemidi_output,
                                                              args=(self._receivemidi_process.stdout, "stdout"))
            self._receivemidi_stderr_thread = threading.Thread(target=self._read_receivemidi_output,
                                                              args=(self._receivemidi_process.stderr, "stderr"))
            self._receivemidi_stdout_thread.daemon = True
            self._receivemidi_stderr_thread.daemon = True
            self._receivemidi_stdout_thread.start()
            self._receivemidi_stderr_thread.start()

            print(f"receivemidi process started with PID: {self._receivemidi_process.pid}")

        except FileNotFoundError:
            self.gui_callback("TOAST", {"message": f"Error: {config.RECEIVEMIDI_PATH} not found.", "color": "red"})
        except Exception as e:
            self.gui_callback("TOAST", {"message": f"Error launching receivemidi: {e}", "color": "red"})

    def list_devices(self):
        try:
            # Use CREATE_NO_WINDOW to prevent flash
            result = subprocess.run([config.SENDMIDI_PATH, "list"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip().splitlines()
        except Exception as e:
            print(f"Error listing devices: {e}")
            self.gui_callback("TOAST", {"message": f"Error listing devices: {e}", "color": "red"})
            return []

    def start_monitoring(self):
        if not self._root:
            print("Error: Root window not set in MidiManager. Cannot start monitor.")
            return

        print("Starting device monitor...")
        if self._root and self._root.winfo_exists():
            self._root.after(0, self._monitor_midi_device)

    def _monitor_midi_device(self):
        if not self._root or not self._root.winfo_exists():
            print("Monitor: Root window destroyed, stopping monitor.")
            return

        if self._monitor_in_flight:
            self._root.after(5000, self._monitor_midi_device)
            return

        self._monitor_in_flight = True
        ch1_override_active = self.gui_callback("GET_CH1_OVERRIDE_STATE")
        usb_lock_active = self.gui_callback("GET_USB_LOCK_STATE")
        mode_snapshot = self.mode_type

        def _poll_worker():
            try:
                devices = self.list_devices()
                bt_monitor_app_running = None
                if mode_snapshot == "BT":
                    if PSUTIL_AVAILABLE:
                        bt_monitor_app_running = self._is_process_running(config.BT_PROCESS_MONITOR_NAME)
                    else:
                        bt_monitor_app_running = "psutil_missing"

                if self._root and self._root.winfo_exists():
                    self._root.after(
                        0,
                        lambda: self._process_monitor_results(
                            devices, bt_monitor_app_running, ch1_override_active, usb_lock_active
                        ),
                    )
            except Exception as e:
                print(f"Device check failed: {e}")
                traceback.print_exc()
                if self._root and self._root.winfo_exists():
                    self._root.after(0, lambda err=e: self._handle_monitor_error(err))

        threading.Thread(target=_poll_worker, daemon=True).start()

    def _handle_monitor_error(self, err):
        self._monitor_in_flight = False
        if self._root and self._root.winfo_exists():
            self.gui_callback("TOAST", {"message": f"Device check failed: {err}", "color": "red"})
            self._root.after(5000, self._monitor_midi_device)

    def _process_monitor_results(self, devices, bt_monitor_app_running, ch1_override_active, usb_lock_active):
        self._monitor_in_flight = False
        if not self._root or not self._root.winfo_exists():
            print("Monitor: Root window destroyed, stopping monitor.")
            return
        try:
            # Use the flexible config variables
            morningstar_present = config.DEVICE_NAME_CH2 in devices
            quad_cortex_present = config.DEVICE_NAME_CH1 in devices
            # Keep the definition of both devices needed for full USB functionality
            both_usb_devices_present = morningstar_present and quad_cortex_present

            mode_label_text = f"Current Mode: {self.mode_type}"
            if self.mode_type == "HYBRID":
                # --- !! MODIFIED: Added ch1_override_active check !! ---
                if ch1_override_active or not quad_cortex_present:
                    # Reroute if QC (CH1) is missing OR override is checked
                    self._qc_midi_target_device = config.DEVICE_NAME_CH2
                    
                    # Update label text based on *why* it's rerouted
                    if ch1_override_active:
                        mode_label_text = f"Current Mode: {self.mode_type} (QC OVERRIDE to MC8)"
                    else:
                        mode_label_text = f"Current Mode: {self.mode_type} (QC REROUTED to MC8)"
                # --- !! END MODIFICATION !! ---
                else:
                    # Use QC (CH1) directly if present and not overridden
                    self._qc_midi_target_device = config.DEVICE_NAME_CH1
                    mode_label_text = f"Current Mode: {self.mode_type} (QC DIRECT)"
            else:
                # In BT or USB_DIRECT, CH1 always targets the configured CH1 device
                self._qc_midi_target_device = config.DEVICE_NAME_CH1

            # --- !! MODIFIED: Use 'both_usb_devices_present' for status !! ---
            status_data = {
                "mode_label_text": mode_label_text,
                "usb_devices_present": both_usb_devices_present, # Status reflects if *both* are OK
                "current_mode": self.mode_type,
                "ch1_override_active": ch1_override_active, # --- !! NEW: Pass state to GUI !! ---
                "bt_monitor_app_running": bt_monitor_app_running # --- !! NEW: Pass BT app status !! ---
            }
            # --- !! END MODIFICATION !! ---

            self.gui_callback("USB_STATUS_UPDATE", status_data)

            # --- !! NEW: CRITICAL BT FAILURE CHECK !! ---
            # Check if we are in BT mode and the BT device is missing
            bt_present = config.DEVICE_NAME_BT in devices
            if self.mode_type == "BT" and not bt_present:
                self.close_persistent_sendmidi()
                if not self._bt_disconnect_warning_shown:
                    self._bt_disconnect_warning_shown = True # Set flag to prevent spamming
                    print("CRITICAL: Bluetooth device not found!")
                    self._root.after(0, lambda: self.gui_callback("TRIGGER_BT_FAILURE_POPUP"))
                return # Stop this monitor cycle; wait for user action
            elif self.mode_type == "BT" and bt_present:
                # If device reappears, reset the flag
                self._bt_disconnect_warning_shown = False
            # --- !! END OF NEW CHECK !! ---

            # --- !! MODIFIED FAILOVER LOGIC !! ---
            trigger_failover = False
            if self.mode_type == "USB_DIRECT":
                # In USB_DIRECT mode, failover if *either* device is missing
                if not both_usb_devices_present:
                    trigger_failover = True
            elif self.mode_type == "HYBRID":
                # In HYBRID mode, failover *only* if the main CH2 device (MC8) is missing
                if not morningstar_present:
                    trigger_failover = True
            # No failover trigger needed for BT mode

            if trigger_failover:
                self.close_persistent_sendmidi()
                if usb_lock_active:
                    if not self._usb_disconnect_warning_shown:
                        # Slightly adjust message based on mode
                        msg = "USB Device(s) disconnected! Switch to BT prevented by lock." \
                              if self.mode_type == "USB_DIRECT" else \
                              f"{config.DEVICE_NAME_CH2} disconnected! Switch to BT prevented by lock."
                        self.gui_callback("TOAST", {"message": msg, "color": "red"})
                        self._usb_disconnect_warning_shown = True
                else:
                    # Proceed with failover if not locked
                    self._user_declined_usb_switch = False
                    self._usb_disconnect_warning_shown = False
                    self.kill_receivemidi()

                    self._root.after(0, lambda: self.gui_callback("TRIGGER_FAILOVER"))
                    return # Stop monitoring as relaunch is pending
            else:
                # If no failover is triggered, reset the warning flag
                self._usb_disconnect_warning_shown = False
            # --- !! END MODIFIED FAILOVER LOGIC !! ---


            # --- Failback Logic (BT Mode check) ---
            if self.mode_type == "BT":
                if both_usb_devices_present: # Only check for failback if *both* are back
                    if self._usb_stable_start_time is None:
                        self._usb_stable_start_time = time.time()
                        self.gui_callback("TOAST", {"message": "USB devices detected. Checking for stability...", "color": "#303030"})
                    elif (time.time() - self._usb_stable_start_time) >= 10: # Stability threshold
                        self._usb_stable_start_time = None # Reset timer

                        if usb_lock_active or self._user_declined_usb_switch:
                            self.gui_callback("TOAST", {"message": "USB devices available, but switch declined/locked.", "color": "#303030"})
                        else:
                            # Trigger the popup for user confirmation
                            self._root.after(0, lambda: self.gui_callback("TRIGGER_FAILBACK_POPUP"))
                            return # Stop monitoring as relaunch *might* be pending
                else:
                    # If devices disappear while checking stability, reset timer
                    self._usb_stable_start_time = None
                    self._user_declined_usb_switch = False # Reset decline flag if devices gone

        except Exception as e:
            print(f"Device check failed: {e}")
            traceback.print_exc()
            if self._root and self._root.winfo_exists():
                self.gui_callback("TOAST", {"message": f"Device check failed: {e}", "color": "red"})

        # Schedule next check if the root window still exists
        if self._root and self._root.winfo_exists():
            self._root.after(5000, self._monitor_midi_device)

    def set_user_declined_switch(self, value):
        self._user_declined_usb_switch = value