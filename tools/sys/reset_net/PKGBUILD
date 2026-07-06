# Maintainer: Dr. Abdulmalek Al-Husseini <ضع بريدك هنا>
pkgname=reset-net
pkgver=1.3.0
pkgrel=1
pkgdesc="Enterprise-grade network reset tool for Manjaro/Arch Linux — fixes internet after Outline VPN disconnect (iptables, DNS, routes, TUN, system tray icon)"
arch=('any')
url="https://github.com/DrAbdulmalek/reset-net"
license=('MIT')
depends=('iproute2' 'networkmanager' 'systemd' 'polkit')
optdepends=(
    'iptables-nft: تنظيف قواعد IPv4/IPv6'
    'nftables: مسح nftables'
    'firewalld: إعادة تشغيل جدار الحماية'
    'yad: أيقونة علبة النظام reset-net-tray'
    'libnotify: إشعارات سطح المكتب من الأيقونة'
)
makedepends=('git')
source=("$pkgname-$pkgver.tar.gz::https://github.com/DrAbdulmalek/reset-net/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')  # ضع الـ hash الحقيقي بعد إصدار التاغ عبر: makepkg -g

# الحزمة الأصلية مصمَّمة للتثبيت اليدوي في /usr/local/bin، بينما حزم
# Arch/AUR يجب أن تثبَّت في /usr/bin. هذه الدالة تُعدّل المسارات تلقائياً
# داخل السكربتات وملفات .desktop/.policy قبل التغليف.
prepare() {
    cd "$srcdir/$pkgname-$pkgver"
    sed -i 's#/usr/local/bin/#/usr/bin/#g' \
        reset-net-gui \
        reset-net-tray \
        reset-net-tray.desktop \
        com.drabdulmalek.reset-net.desktop
}

package() {
    cd "$srcdir/$pkgname-$pkgver"

    install -Dm755 reset-net      "$pkgdir/usr/bin/reset-net"
    install -Dm755 reset-net-gui  "$pkgdir/usr/bin/reset-net-gui"
    if [[ -f reset-net-tray ]]; then
        install -Dm755 reset-net-tray "$pkgdir/usr/bin/reset-net-tray"
        install -Dm644 reset-net-tray.desktop \
            "$pkgdir/etc/xdg/autostart/reset-net-tray.desktop"
    fi

    install -Dm644 com.drabdulmalek.reset-net.desktop \
        "$pkgdir/usr/share/applications/com.drabdulmalek.reset-net.desktop"
    install -Dm644 com.drabdulmalek.reset-net.policy \
        "$pkgdir/usr/share/polkit-1/actions/com.drabdulmalek.reset-net.policy"

    install -Dm644 LICENSE   "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}

# ملاحظة: لا يُنشئ هذا الـPKGBUILD قاعدة sudoers تلقائياً (NOPASSWD)
# لأن حزم AUR لا يجب أن تُعدّل /etc/sudoers.d دون علم صريح من المستخدم —
# هذا قد يُرفض في مراجعة AUR. الاستخدام عبر GUI/tray يعمل بدون ذلك أصلاً
# لأنه يعتمد على Polkit (pkexec) لا على sudoers.
# من يريد تشغيل "reset-net" من الطرفية بدون كلمة مرور، ينفّذ يدوياً:
#   echo "$USER ALL=(root) NOPASSWD: /usr/bin/reset-net" | sudo tee /etc/sudoers.d/reset-net
#   sudo chmod 440 /etc/sudoers.d/reset-net
