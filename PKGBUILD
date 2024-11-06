# Maintainer: Your Name <your.email@example.com>
pkgname=gpu-passthrough-gtk
pkgver=1.0.0
pkgrel=1
pkgdesc="A GTK-based tool for configuring VFIO options on Linux"
arch=('any')
url="https://example.com"  # replace with a URL if you have one
license=('MIT')            # replace with the correct license
depends=('python' 'gtk4')
source=("gpu-passthrough-gtk.py"
        "gpu-passthrough-gtk.desktop"
        "vfio-icon.png")   # Add your icon file here if you have one
sha256sums=('SKIP'
            'SKIP'
            'SKIP')        # Replace 'SKIP' with actual checksums if needed

package() {
    # Install the main Python script
    install -Dm755 "$srcdir/gpu-passthrough-gtk.py" "$pkgdir/usr/bin/gpu-passthrough-gtk"
    
    # Install the .desktop file
    install -Dm644 "$srcdir/gpu-passthrough-gtk.desktop" "$pkgdir/usr/share/applications/gpu-passthrough-gtk.desktop"
    
    # Install the icon if you have one
    install -Dm644 "$srcdir/vfio-icon.png" "$pkgdir/usr/share/icons/vfio-icon.png"
}
