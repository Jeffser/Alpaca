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

configure_file(
  input: 'alpaca_search_provider.py.in',
  output: 'alpaca_search_provider',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

alpaca_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'available_models.json',
  'available_models_descriptions.py',
  'internal.py',
  'generic_actions.py',
  'sql_manager.py',
  'instance_manager.py'
]

custom_widgets = [
  'custom_widgets/table_widget.py',
  'custom_widgets/message_widget.py',
  'custom_widgets/chat_widget.py',
  'custom_widgets/terminal_widget.py',
  'custom_widgets/dialog_widget.py',
  'custom_widgets/model_manager_widget.py'
]

install_data(alpaca_sources, install_dir: moduledir)
install_data(custom_widgets, install_dir: moduledir / 'custom_widgets')
