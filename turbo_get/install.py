import sys
import os
import json
import platform

# This script should be in the root directory of the project
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Configuration ---
# This MUST match the name in your manifest template
HOST_NAME = "io.github.dariusconca170-prog.turboget"
NATIVE_HOST_SCRIPT_NAME = "native_host.py"
TEMPLATE_NAME = "native_host_manifest_template.json"
APP_SUBFOLDER = "turbo_get"

def get_chrome_path(os_platform):
    """Gets the path to the Chrome NativeMessagingHosts directory."""
    if os_platform == "win32":
        # Registry key is handled separately for Windows
        return None
    elif os_platform == "darwin": # macOS
        return os.path.expanduser('~/Library/Application Support/Google/Chrome/NativeMessagingHosts')
    elif os_platform.startswith("linux"):
        return os.path.expanduser('~/.config/google-chrome/NativeMessagingHosts')
    else:
        raise RuntimeError(f"Unsupported platform: {os_platform}")

def install():
    """Generates the manifest and registers it with the browser."""
    print("Starting TurboGet Native Host installation...")
    
    os_platform = sys.platform
    
    # 1. Construct the absolute path to the native host script
    native_host_path = os.path.join(PROJECT_ROOT, APP_SUBFOLDER, NATIVE_HOST_SCRIPT_NAME)
    if not os.path.exists(native_host_path):
        print(f"Error: Could not find '{native_host_path}'. Make sure this script is in the project root.")
        return

    print(f"Native host script found at: {native_host_path}")

    # 2. Read the template and replace the path placeholder
    template_path = os.path.join(PROJECT_ROOT, APP_SUBFOLDER, TEMPLATE_NAME)
    with open(template_path, 'r') as f:
        manifest = json.load(f)
    
    manifest['path'] = native_host_path
    
    # 3. Write the final manifest file and register it
    manifest_filename = f"{HOST_NAME}.json"
    
    if os_platform == "win32":
        # For Windows, we write the manifest file in the app dir and point the registry to it
        import winreg
        
        manifest_path = os.path.join(PROJECT_ROOT, APP_SUBFOLDER, manifest_filename)
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"Generated manifest file at: {manifest_path}")

        try:
            # Create the registry key under HKEY_CURRENT_USER
            key_path = fr"SOFTWARE\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValue(key, '', winreg.REG_SZ, manifest_path)
            winreg.CloseKey(key)
            print("Successfully created registry key.")
        except Exception as e:
            print(f"Error: Failed to create registry key. You may need to run this script as an administrator.")
            print(f"Details: {e}")
            return
            
    else: # macOS and Linux
        target_dir = get_chrome_path(os_platform)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"Created directory: {target_dir}")
        
        manifest_path = os.path.join(target_dir, manifest_filename)
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"Manifest file created at: {manifest_path}")

    print("\nInstallation complete! Restart your browser for the changes to take effect.")

if __name__ == "__main__":
    install()