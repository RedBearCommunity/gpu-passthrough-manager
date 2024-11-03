#!/usr/bin/env python3
import gi
import subprocess
import re
import os
import sys
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio
os.environ["DBUS_SESSION_BUS_ADDRESS"] = ""

class VFIOConfigurator(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.VFIOConfigurator")
        self.connect("activate", self.on_activate)
        self.device_pairs = self.get_device_pairs()

    def on_activate(self, app):
        # Check if GTK can initialize properly
        if not Gtk.init_check():
            print("Error: GTK could not be initialized. Ensure you are running in a graphical environment.")
            sys.exit(1)

        # Set up the main application window
        self.window = Gtk.ApplicationWindow(application=app)
        self.window.set_title("VFIO Configurator")
        self.window.set_default_size(400, 300)


        # Create a vertical box to hold buttons
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)

        # Add buttons for each device pair with detailed labels
        for vga, audio, driver in self.device_pairs:
            vga_desc = f"{vga[0]} VGA: {vga[1]}:{vga[2]}"
            audio_desc = f"Audio: {audio[1]}:{audio[2]}"
            label = f"{driver.upper()} {vga_desc} {audio_desc}"
            button = Gtk.Button(label=label)
            button.connect("clicked", self.on_button_clicked, vga, audio, driver)
            vbox.append(button)

        # Add vbox to window and display it
        self.window.set_child(vbox)
        self.window.present()

    def get_device_pairs(self):
        # Run lspci command to get device information
        output = subprocess.run(
            ["lspci", "-nn"], capture_output=True, text=True, check=True
        ).stdout
        devices = re.findall(
            r"(\d{2}:\d{2}\.\d) (.*(?:Audio|VGA|3D).*) \[([a-f0-9]{4}):([a-f0-9]{4})\]",
            output,
        )

        # Initialize lists for different types of devices
        amd_devices = []
        nvidia_devices = []
        nouveau_devices = []

        # Classify devices as VGA or Audio and group by vendor
        for device in devices:
            slot, desc, vendor_id, device_id = device
            if "VGA" in desc or "3D" in desc:
                if "AMD" in desc:
                    amd_devices.append((slot, vendor_id, device_id, "vga"))
                elif "NVIDIA" in desc:
                    if "nouveau" in subprocess.run(["lsmod"], capture_output=True, text=True).stdout:
                        nouveau_devices.append((slot, vendor_id, device_id, "vga"))
                    else:
                        nvidia_devices.append((slot, vendor_id, device_id, "vga"))
            elif "Audio" in desc:
                if "AMD" in desc:
                    amd_devices.append((slot, vendor_id, device_id, "audio"))
                elif "NVIDIA" in desc:
                    if "nouveau" in subprocess.run(["lsmod"], capture_output=True, text=True).stdout:
                        nouveau_devices.append((slot, vendor_id, device_id, "audio"))
                    else:
                        nvidia_devices.append((slot, vendor_id, device_id, "audio"))

        # Pair VGA with corresponding Audio devices based on slot numbers
        device_pairs = []

        def pair_devices(devices, driver_name):
            vga_devices = [d for d in devices if d[3] == "vga"]
            audio_devices = [d for d in devices if d[3] == "audio"]

            for vga in vga_devices:
                audio = next((a for a in audio_devices if a[0].startswith(vga[0][:5])), None)
                if audio:
                    device_pairs.append((vga, audio, driver_name))

        # Pair AMD, NVIDIA (proprietary), and NVIDIA (nouveau) devices separately
        pair_devices(amd_devices, "amdgpu")
        pair_devices(nvidia_devices, "nvidia")
        pair_devices(nouveau_devices, "nouveau")

        return device_pairs

    def on_button_clicked(self, button, vga, audio, driver):
        vga_id = f"{vga[1]}:{vga[2]}"
        audio_id = f"{audio[1]}:{audio[2]}"
        vfio_config = f"options vfio-pci ids={vga_id},{audio_id}\nsoftdep {driver} pre: vfio-pci\n"

        # Write configuration to /etc/modprobe.d/vfio.conf
        with open("/etc/modprobe.d/vfio.conf", "w") as f:
            f.write(vfio_config)

        # Update initramfs
        self.update_initramfs()

        # Show a message dialog
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text="Configuration saved to /etc/modprobe.d/vfio.conf.\nInitramfs updated. Please reboot to apply changes."
        )

        # Set up the dialog with a reboot option
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        dialog.set_child(box)

        label = Gtk.Label(label="Configuration saved to /etc/modprobe.d/vfio.conf.\nInitramfs updated. Please reboot to apply changes.")
        label.set_wrap(True)
        box.append(label)

        reboot_button = Gtk.Button(label="Reboot Now")
        reboot_button.connect("clicked", self.reboot_system)
        box.append(reboot_button)

        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def update_initramfs(self):
        try:
            with open("/etc/os-release") as f:
                os_release = f.read()

            if "arch" in os_release or "manjaro" in os_release:
                subprocess.run(["mkinitcpio", "-P"], check=True)
            elif "endeavouros" in os_release:
                if os.path.isfile("/usr/bin/dracut"):
                    subprocess.run(["dracut", "--force"], check=True)
                else:
                    subprocess.run(["mkinitcpio", "-P"], check=True)
            elif "ubuntu" in os_release or "debian" in os_release:
                subprocess.run(["update-initramfs", "-u"], check=True)
            elif "fedora" in os_release:
                subprocess.run(["dracut", "--force"], check=True)
            else:
                print("OS not recognized. Please update initramfs manually.")
        except Exception as e:
            print(f"Error updating initramfs: {e}")

    def reboot_system(self, button):
        subprocess.run(["reboot"])

def main():
    # Check for root privileges; use sudo if not running as root
    if os.geteuid() == 0 and "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
    dbus_address = subprocess.check_output(
        "echo $DBUS_SESSION_BUS_ADDRESS", shell=True, text=True).strip()
    if dbus_address:
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address        
        print("Requesting root privileges...")
        script_path = os.path.abspath(__file__)
        subprocess.call(["sudo", sys.executable, script_path] + sys.argv[1:])
        sys.exit(0)

    # Run the application
    app = VFIOConfigurator()
    app.run()

if __name__ == "__main__":
    main()
