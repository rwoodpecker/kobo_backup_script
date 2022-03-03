import json
import os
import datetime
from pathlib import Path
import platform
import glob
import subprocess
import sys
import shutil
import platform

label = "KOBOeReader"  # volume label of kobo - this is the default across models but could change in the future.
backup_base_directory = str(
    os.path.join(os.path.expanduser("~"), "Backups", "kobo")
)  # the folder in which backups will be placed. This should be OS agnostic.

if len(sys.argv) > 1 and sys.argv[1] == "--setup_auto_backup":
    if platform.system() == "Linux":
        from utils import create_linux_autostart_script

        # Create the autostart script
        create_linux_autostart_script()
        sys.exit()
    else:
        print(
            "The automation feature is currently only supported on Linux. Exiting...."
        )
        sys.exit()
elif len(sys.argv) > 1 and sys.argv[1] == "--cancel_auto_backup":
    # Remove the autostart script
    if platform.system() == "Linux":
        autostart_path = os.path.expanduser("~/.config/autostart/")
        desktop_file_name = "auto_kobo_backup.desktop"
        try:
            os.remove(autostart_path + desktop_file_name)
            print(
                "Cancelled auto-backup (removed file in autostart called "
                + desktop_file_name
            )
        except FileNotFoundError:
            print("There was no auto backup set up.")
        sys.exit()
    else:
        print(
            "The automation feature is currently only supported on Linux. Exiting...."
        )
        sys.exit()

if platform.system() == "Windows":  # Get mount point on Windows
    import wmi

    # Set up WMI object for later
    c = wmi.WMI()
    kobos = []
    # Get all drives and their infos
    for drive in c.Win32_LogicalDisk():
        # If any drive is called the label, append it to the list
        if drive.VolumeName == label:
            kobos.append(drive.Name + os.sep)
    user_os = "Windows"
elif platform.system() == "Linux":  # Get mount point on Linux
    lsblk_check = subprocess.check_output(["lsblk", "-f", "--json"]).decode("utf8")
    lsblk_json = json.loads(lsblk_check)
    kobos = [
        device
        for device in lsblk_json["blockdevices"]
        if device.get("label", None) == label
    ]
    kobos = [kobo["mountpoint"] for kobo in kobos]
    user_os = "Linux"
elif platform.system() == "Darwin":  # Get mount point on MacOS
    df_output = subprocess.check_output(("df", "-Hl")).decode("utf8")
    output_parts = [o.split() for o in df_output.split("\n")]
    kobos = [o[-1] for o in output_parts if f"/Volumes/{label}" in o]
    user_os = "macOS"
else:
    raise Exception(f"Unsupported OS: {platform.system()=} {platform.release()=}")

if len(kobos) > 1:
    raise RuntimeError(f"Multiple Kobo devices detected: {kobos}.")
elif len(kobos) == 0:
    print("No kobos detected.")
    sys.exit()
else:
    [kobo] = kobos
    print(f"Kobo mountpoint is: {Path(kobo)} on {user_os}.")

backup_folder_exists = os.path.isdir(
    backup_base_directory
)  # check backup base directory exists locally, if not create it.
if not backup_folder_exists:
    print(f"No backup folder detected. Creating {backup_base_directory}.")
    os.makedirs(backup_base_directory)
else:
    print(f"An existing kobo backup folder was detected at {backup_base_directory}.")

try:
    previous_backup = max(
        glob.glob(os.path.join(backup_base_directory, "*/")), key=os.path.getmtime
    )  # get the folder of the previous backup that occured
except ValueError:
    pass

backup_path = os.path.join(
    backup_base_directory,
    "kobo_backup_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"),
)  # append datestamp to directory name.
if os.path.isdir(backup_path):
    print(
        f"A backup of the kobo was already completed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}. Try again in a minute."
    )
    sys.exit()

try:  # copy files
    shutil.copytree(Path(kobo), backup_path)
except OSError:  # some unrequired .Trashes will return 'operation not permitted'.
    pass


def get_directory_size(directory):  # figure out how much was backed up.
    total = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_directory_size(entry.path)
    except NotADirectoryError:
        return os.path.getsize(directory)
    except PermissionError:
        return 0
    return total


def get_size_format(
    b, factor=1024, suffix="B"
):  # convert bytes to something human readable.
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"


try:
    previous_backup
    print(
        f"The previous backup contained {sum(len(files) for _, _, files in os.walk(previous_backup))} files and was {get_size_format(get_directory_size(previous_backup))}."
    )
except NameError:
    pass

print(
    f"Backup complete. Copied {sum(len(files) for _, _, files in os.walk(backup_path))} files with a size of {get_size_format(get_directory_size(backup_path))} to {backup_path}."
)
try:
    # Only tested the below on Linux
    # Open a notification to say it was backed up
    subprocess.Popen(["notify-send", f"Backed up!"])
    # Open the file explorer to the backed up directory
    os.system(f"xdg-open {backup_path}")
except Exception:
    pass
