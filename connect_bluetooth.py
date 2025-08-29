import sys
import dwarf_python_api.lib.my_logger as log

from dwarf_ble_connect.connect_bluetooth import connect_bluetooth
from dwarf_ble_connect.lib.connect_direct_bluetooth import connect_ble_direct_dwarf, connect_ble_dwarf_win
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_psd
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_ssid
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_pwd

def connect_bluetooth_web():

    return connect_bluetooth()

def connect_bluetooth_cmd(ble_psd, ble_STA_ssid, ble_STA_pwd, auto_select):

    return connect_ble_direct_dwarf(ble_psd, ble_STA_ssid, ble_STA_pwd, auto_select)

def connect_bluetooth_win(ble_psd, ble_STA_ssid, ble_STA_pwd):

    return connect_ble_dwarf_win(ble_psd, ble_STA_ssid, ble_STA_pwd)

if __name__ == "__main__":

    # If command-line parameters are provided
    win = True
    cmd = False
    ble_psd = read_bluetooth_ble_psd() or "DWARF_12345678"
    ble_STA_ssid = read_bluetooth_ble_STA_ssid() or ""
    ble_STA_pwd = read_bluetooth_ble_STA_pwd() or ""
    print("##############")
    print("Config Values:")
    print("Wifi PSD:", ble_psd)
    print("Wifi STAT SSID:", ble_STA_ssid)
    if ble_STA_pwd:
      print("Wifi STAT PWD: *******")
    else:
      print("Wifi STAT PWD: empty!")

    if len(sys.argv) > 1:
        
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--cmd":
                win = False
                cmd = True
            elif sys.argv[i] == "--web":
                win = False
                cmd = False
            elif sys.argv[i] == "--psd":
                if i + 1 < len(sys.argv):
                    ble_psd = sys.argv[i + 1]
                    i += 1
                else:
                    print("Error: --psd parameter requires an argument.")
                    sys.exit(1)
            elif sys.argv[i] == "--ssid":
                if i + 1 < len(sys.argv):
                    ble_STA_ssid = sys.argv[i + 1]
                    i += 1
                else:
                    print("Error: --ssid parameter requires an argument.")
                    sys.exit(1)
            elif sys.argv[i] == "--pwd":
                if i + 1 < len(sys.argv):
                    ble_STA_pwd = sys.argv[i + 1]
                    i += 1
                else:
                    print("Error: --pwd parameter requires an argument.")
                    sys.exit(1)
            elif sys.argv[i] == "--select":
                if i + 1 < len(sys.argv):
                    auto_select = sys.argv[i + 1]
                    i += 1
                else:
                    print("Error: --select parameter requires an argument.")
                    sys.exit(1)
            else:
                print(f"Error: Unknown parameter '{sys.argv[i]}'.")
                sys.exit(1)
            i += 1

    print("##############")
    print("Final Values:")
    print("Wifi PSD:", ble_psd)
    print("Wifi STAT SSID:", ble_STA_ssid)
    if ble_STA_pwd:
      print("Wifi STAT PWD: *******")
    else:
      print("Wifi STAT PWD: empty!")
    print("##############")

    if win:
        connect_bluetooth_win(ble_psd, ble_STA_ssid, ble_STA_pwd)
    elif cmd:
        connect_bluetooth_cmd(ble_psd, ble_STA_ssid, ble_STA_pwd, auto_select)
    else:
        connect_bluetooth_web()

