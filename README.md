not based off of https://github.com/uwzis/GPU-Passthrough-Manager ; i just stole his icon violently, and his program no longer works so i made mine

![Screenshot_2024-11-03_02-33-46](https://github.com/user-attachments/assets/6984902e-ac94-4365-bbc7-e8ea7b6514ef)

supposed to pair vga groups and audio groups from lspci and show an output of them

supposed to also work closed source nvidia drivers and open source nvidia drivers

no idea if it works with other distros, i have no idea at all for most of it.

only tested on cachyos / arch. 

dracut = untested |
initramfs = untested |
mkinitcpio = tested |

please write if you have issues

run makepkg -si
