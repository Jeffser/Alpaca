pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'alpaca'
gnome = import('gnome')

gnome.compile_resources('alpaca',
  'alpaca.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'alpaca.in',
  output: 'alpaca',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

#configure_file(
  #input: 'alpaca_search_provider.in',
  #output: 'alpaca_search_provider',
  #configuration: conf,
  #install: true,
  #install_dir: get_option('bindir'),
  #install_mode: 'r-xr-xr-x'
#)

alpaca_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'connection_handler.py',
  'available_models.py',
  'dialogs.py',
  'local_instance.py',
  'update_history.py'
]

install_data(alpaca_sources, install_dir: moduledir)
