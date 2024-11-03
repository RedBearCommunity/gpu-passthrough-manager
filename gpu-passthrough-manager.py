#!/usr/bin/env python3
import gi
import subprocess
import re
import os
import sys
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
os.environ["DBUS_SESSION_BUS_ADDRESS"] = ""


class VFIOConfigurator(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.VFIOConfigurator")
        self.connect("activate", self.on_activate)
        self.device_pairs = self.get_device_pairs()

    def on_activate(self, app):
        if not Gtk.init_check():
            print("Error: GTK could not be initialized. Ensure you are running in a graphical environment.")
            sys.exit(1)

        self.window = Gtk.ApplicationWindow(application=app)
        self.window.set_title("VFIO Configurator")
        self.window.set_default_size(400, 300)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_vbox.set_margin_top(10)
        main_vbox.set_margin_bottom(10)
        main_vbox.set_margin_start(10)
        main_vbox.set_margin_end(10)

        scrollable_area = Gtk.ScrolledWindow()
        scrollable_area.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollable_area.set_vexpand(True)

        device_button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for vga, audio, driver in self.device_pairs:
            vga_desc = f"{vga[0]} VGA: {vga[1]}:{vga[2]}"
            audio_desc = f"Audio: {audio[1]}:{audio[2]}"
            label = f"{driver.upper()} {vga_desc} {audio_desc}"
            button = Gtk.Button(label=label)
            button.connect("clicked", self.on_device_button_clicked, vga, audio, driver)
            device_button_box.append(button)

        scrollable_area.set_child(device_button_box)
        main_vbox.append(scrollable_area)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        delete_button = Gtk.Button(label="Delete /etc/modprobe.d/vfio.conf")
        delete_button.set_size_request(0, 40) 
        delete_button.set_hexpand(True)  
        delete_button.connect("clicked", self.on_delete_button_clicked)
        button_box.append(delete_button)

        reboot_button = Gtk.Button(label="Reboot")
        reboot_button.set_size_request(0, 40) 
        reboot_button.set_hexpand(True)  
        reboot_button.connect("clicked", self.on_reboot_button_clicked)
        button_box.append(reboot_button)

        main_vbox.append(button_box)
        self.window.set_child(main_vbox)
        self.window.present()

    def get_device_pairs(self):
        output = subprocess.run(["lspci", "-nn"], capture_output=True, text=True, check=True).stdout
        devices = re.findall(r"(\d{2}:\d{2}\.\d) (.*(?:Audio|VGA|3D).*) \[([a-f0-9]{4}):([a-f0-9]{4})\]", output)

        amd_devices, nvidia_devices, nouveau_devices = [], [], []

        for device in devices:
            slot, desc, vendor_id, device_id = device
            if "VGA" in desc or "3D" in desc:
                if "AMD" in desc:
                    amd_devices.append((slot, vendor_id, device_id, "vga"))
                elif "NVIDIA" in desc:
                    driver = "nouveau" if "nouveau" in subprocess.run(["lsmod"], capture_output=True, text=True).stdout else "nvidia"
                    (nouveau_devices if driver == "nouveau" else nvidia_devices).append((slot, vendor_id, device_id, "vga"))
            elif "Audio" in desc:
                if "AMD" in desc:
                    amd_devices.append((slot, vendor_id, device_id, "audio"))
                elif "NVIDIA" in desc:
                    driver = "nouveau" if "nouveau" in subprocess.run(["lsmod"], capture_output=True, text=True).stdout else "nvidia"
                    (nouveau_devices if driver == "nouveau" else nvidia_devices).append((slot, vendor_id, device_id, "audio"))

        device_pairs = []
        def pair_devices(devices, driver_name):
            vga_devices = [d for d in devices if d[3] == "vga"]
            audio_devices = [d for d in devices if d[3] == "audio"]
            for vga in vga_devices:
                audio = next((a for a in audio_devices if a[0].startswith(vga[0][:5])), None)
                if audio:
                    device_pairs.append((vga, audio, driver_name))

        pair_devices(amd_devices, "amdgpu")
        pair_devices(nvidia_devices, "nvidia")
        pair_devices(nouveau_devices, "nouveau")
        return device_pairs

    def on_device_button_clicked(self, button, vga, audio, driver):
        vga_id = f"{vga[1]}:{vga[2]}"
        audio_id = f"{audio[1]}:{audio[2]}"
        vfio_config = f"options vfio-pci ids={vga_id},{audio_id}\nsoftdep {driver} pre: vfio-pci\n"

        with open("/etc/modprobe.d/vfio.conf", "w") as f:
            f.write(vfio_config)
        self.update_initramfs()

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text="Configuration saved to /etc/modprobe.d/vfio.conf.\nInitramfs updated. Please reboot to apply changes."
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def on_delete_button_clicked(self, button):
        vfio_conf_path = "/etc/modprobe.d/vfio.conf"
        if os.path.exists(vfio_conf_path):
            os.remove(vfio_conf_path)
            print(f"{vfio_conf_path} deleted.")
        self.update_initramfs()

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text="VFIO configuration deleted. Initramfs updated. Please reboot to apply changes."
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def on_reboot_button_clicked(self, button):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            buttons=Gtk.ButtonsType.NONE,
            text="Are you sure you want to reboot?"
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Confirm", Gtk.ResponseType.OK
        )
        dialog.connect("response", self.handle_reboot_response)
        dialog.present()

    def handle_reboot_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            subprocess.run(["reboot"])
        dialog.close()

    def update_initramfs(self):
        try:
            with open("/etc/os-release") as f:
                os_release = f.read()
            if "arch" in os_release or "manjaro" in os_release:
                subprocess.run(["mkinitcpio", "-P"], check=True)
            elif "endeavouros" in os_release:
                if os.path.isfile("/usr/bin/dracut"):
                    subprocess.run(["update_dracut_image"], check=True)
                else:
                    subprocess.run(["mkinitcpio", "-P"], check=True)
            elif "ubuntu" in os_release or "debian" in os_release:
                subprocess.run(["update-initramfs", "-u"], check=True)
            elif "fedora" in os_release:
                subprocess.run(["update_dracut_image"], check=True)
            else:
                print("OS not recognized. Please update initramfs manually.")
        except Exception as e:
            print(f"Error updating initramfs: {e}")

def main():
    if os.geteuid() != 0:
        print("Requesting root privileges...")
        script_path = os.path.abspath(__file__)
        subprocess.call(["sudo", sys.executable, script_path] + sys.argv[1:])
        sys.exit(0)

    app = VFIOConfigurator()
    app.run()

if __name__ == "__main__":
    main()
