# Maintainer: Jeffry Samuel Eduarte Rojas <jeffrysamuer@gmail.com>
pkgname=com.jeffser.alpaca
pkgver=2.0.1
pkgrel=1
pkgdesc="An Ollama client made with GTK4 and Adwaita"
arch=('any')
url="https://github.com/jeffser/Alpaca"
license=('GPL-3.0')
depends=('python-requests' 'python-pillow' 'python-pypdf' 'python-pytube' 'python-html2text')
source=("https://github.com/Jeffser/Alpaca/archive/refs/tags/${pkgver}.tar.gz")
md5sums=('SKIP')

prepare() {
  cd "$srcdir/Alpaca-${pkgver}"
}

build() {
  cd "$srcdir/Alpaca-${pkgver}"
  meson setup _build
  meson compile -C _build
}

package() {
  cd "$srcdir/Alpaca-${pkgver}/_build"
  sudo meson install --destdir="$pkgdir"
}
