application_id = 'com.jeffser.Alpaca'

message('funny icon time')
scalable_dir = 'hicolor' / 'scalable' / 'apps'
install_data(
  scalable_dir / ('@0@.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / scalable_dir
)

symbolic_dir = 'hicolor' / 'symbolic' / 'apps'
install_data(
  symbolic_dir / ('@0@-symbolic.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / symbolic_dir
)

png_dir = 'hicolor' / '512x512' / 'apps'
install_data(
  png_dir / ('@0@.png').format(application_id),
  install_dir: get_option('datadir') / 'icons' / png_dir
)