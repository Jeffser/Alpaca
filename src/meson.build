pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'alpaca'
gnome = import('gnome')

blueprints = files(
  'ui/notice.blp',
  'ui/preferences.blp',
  'ui/quick_ask.blp',
  'ui/shortcuts.blp',
  'ui/welcome.blp',
  'ui/window.blp',
)

blueprints = custom_target('blueprints',
  input: blueprints,
  output: '.',
  command: [
    find_program('blueprint-compiler', version: '>= 0.18.0'),
    'batch-compile',
    '@OUTPUT@',
    '@CURRENT_SOURCE_DIR@',
    '@INPUT@'
  ],
)

gnome.compile_resources(
  'alpaca',
  'alpaca.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
  source_dir: meson.current_source_dir(),
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'alpaca.py.in',
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
  'main.py',
  'window.py',
  'quick_ask.py',
  'constants.py',
  'ollama_models.py',
  'sql_manager.py'
]

install_data(alpaca_sources, install_dir: moduledir)

subdir('widgets')