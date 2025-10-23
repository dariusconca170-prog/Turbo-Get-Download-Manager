# turbo_get/native_host.py
import sys
import json
import struct
import requests

# The port must match the one the main GUI is listening on
GUI_SERVER_URL = "http://127.0.0.1:9876/add_download"

def get_message():
    """Read a message from stdin and decode it."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        sys.exit(0)
    message_length = struct.unpack('@I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def main():
    try:
        message = get_message()
        url = message.get("url")
        if url:
            # Send the URL to the running TurboGet GUI
            requests.post(GUI_SERVER_URL, json={"url": url})
    except Exception as e:
        # It's good practice to log errors, but be careful not to write
        # anything to stdout, as it will break the Native Messaging protocol.
        # You can write to a log file for debugging.
        with open("native_host_errors.log", "a") as f:
            f.write(f"Error: {e}\n")

if __name__ == '__main__':
    main()