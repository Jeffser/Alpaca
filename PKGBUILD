# Maintainer: Jeffry Samuel Eduarte Rojas <jeffrysamuer@gmail.com>
pkgname=Alpaca
pkgver=2.0.1
pkgrel=1
pkgdesc="An Ollama client made with GTK4 and Adwaita"
arch=('any')
url="https://github.com/jeffser/Alpaca"
license=('GPL-3.0')
depends=('python-requests' 'python-pillow' 'python-pypdf' 'python-pytube' 'python-html2text')
source=("git+https://github.com/jeffser/Alpaca.git")
md5sums=('SKIP')

build() {
  cd "$srcdir/Alpaca"
  meson setup _build
  meson compile -C _build
}

package() {
  cd "$srcdir/Alpaca/_build"
  sudo meson install --destdir="$pkgdir"
}
