#!/usr/bin/env python3
import subprocess
import gi
import sys
import os
import re

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class GPUDevice:
    def __init__(self, pci_id, description, vendor_id, device_id, driver, model_name):
        self.pci_id = pci_id
        self.description = description
        self.vendor_id = vendor_id
        self.device_id = device_id
        self.driver = driver
        self.model_name = model_name

def run_command(command):
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
        return output.decode().strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.output.decode()}")
        return ""

def detect_devices():
    raw_output = run_command("lspci -nn | grep -E 'VGA|Audio'")
    devices = []
    if raw_output:
        for line in raw_output.splitlines():
            parts = line.split(" ")
            pci_id = parts[0]
            description = " ".join(parts[1:])
            match = re.search(r'\[(\w{4}):(\w{4})\]', line)
            if match:
                vendor_id, device_id = match.groups()
                driver = (
                    "amdgpu" if "AMD" in description else
                    "nvidia" if "NVIDIA" in description else
                    "nouveau" if "NOUVEAU" in description else
                    "unknown"
                )

                # Extract model name
                description_after_colon = description.split(":", 1)[1].strip() if ":" in description else description
                square_bracket_contents = re.findall(r'\[([^\]]+)\]', description_after_colon)
                # Exclude vendor_id:device_id and any numeric IDs
                model_names = [
                    s for s in square_bracket_contents
                    if s != f"{vendor_id}:{device_id}" and not re.match(r'^\d+$', s) and not re.match(r'^\d{4}$', s)
                ]
                if model_names:
                    model_name = model_names[-1]
                else:
                    # If no square brackets, perhaps use the text after the colon
                    model_name = description_after_colon.strip()

                devices.append(GPUDevice(pci_id, description, vendor_id, device_id, driver, model_name))
            else:
                print(f"Skipping line with unexpected format: {line}")

    paired_devices = []
    for gpu in devices:
        if "VGA" in gpu.description:
            for audio in devices:
                if "Audio" in audio.description and gpu.pci_id[:2] == audio.pci_id[:2] and gpu.vendor_id == audio.vendor_id:
                    paired_devices.append((gpu, audio))
                    break
    return paired_devices

def write_vfio_conf(vga_id, audio_id, driver):
    vfio_conf_content = f"options vfio-pci ids={vga_id},{audio_id}\nsoftdep {driver} pre: vfio-pci\n"
    try:
        subprocess.run(["sudo", "tee", "/etc/modprobe.d/vfio.conf"], input=vfio_conf_content, text=True, check=True)
        print("Configuration written to /etc/modprobe.d/vfio.conf.")
    except subprocess.CalledProcessError:
        print("Error: Could not write to /etc/modprobe.d/vfio.conf.")

class GPUPassthroughManager(Gtk.Window):
    def __init__(self):
        super().__init__(title="GPU Passthrough Manager")
        self.set_default_size(400, 400)
        self.paired_devices = detect_devices()

        main_vbox = Gtk.VBox(spacing=5, margin=10)

        scrollable_area = Gtk.ScrolledWindow()
        scrollable_area.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        device_button_box = Gtk.VBox(spacing=5)

        if not self.paired_devices:
            device_button_box.pack_start(Gtk.Label(label="No GPU-Audio pairs detected."), False, False, 0)
        else:
            for gpu, audio in self.paired_devices:
                button_label = f"{gpu.model_name} [{gpu.vendor_id}:{gpu.device_id}] [{audio.vendor_id}:{audio.device_id}]"
                button = Gtk.Button(label=button_label)
                button.connect("clicked", self.on_device_button_clicked, gpu, audio)
                device_button_box.pack_start(button, False, False, 0)

        scrollable_area.add(device_button_box)
        main_vbox.pack_start(scrollable_area, True, True, 0)

        button_box = Gtk.HBox(spacing=10)

        delete_button = Gtk.Button(label="Delete /etc/modprobe.d/vfio.conf")
        delete_button.set_size_request(0, 40)
        delete_button.connect("clicked", self.on_delete_button_clicked)
        button_box.pack_start(delete_button, True, True, 0)

        reboot_button = Gtk.Button(label="Reboot")
        reboot_button.set_size_request(0, 40)
        reboot_button.connect("clicked", self.on_reboot_button_clicked)
        button_box.pack_start(reboot_button, True, True, 0)

        main_vbox.pack_start(button_box, False, False, 0)
        self.add(main_vbox)

    def on_device_button_clicked(self, button, gpu, audio):
        write_vfio_conf(gpu.vendor_id + ":" + gpu.device_id, audio.vendor_id + ":" + audio.device_id, gpu.driver)
        print(f"Configuration for {gpu.description} written to /etc/modprobe.d/vfio.conf.")
        self.update_initramfs()

    def on_delete_button_clicked(self, button):
        vfio_conf_path = "/etc/modprobe.d/vfio.conf"
        if os.path.exists(vfio_conf_path):
            os.remove(vfio_conf_path)
            print(f"{vfio_conf_path} deleted.")
            self.update_initramfs()

            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                buttons=Gtk.ButtonsType.OK,
                text="VFIO configuration deleted. Initramfs updated. Please reboot to apply changes."
            )
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.show_all()

    def on_reboot_button_clicked(self, button):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            buttons=Gtk.ButtonsType.NONE,
            text="Are you sure you want to reboot?"
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Confirm", Gtk.ResponseType.OK
        )
        dialog.connect("response", self.handle_reboot_response)
        dialog.show_all()

    def handle_reboot_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            subprocess.run(["reboot"])
        dialog.destroy()

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

    window = GPUPassthroughManager()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()

    Gtk.main()

if __name__ == "__main__":
    main()
