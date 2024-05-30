desktop_file = i18n.merge_file(
        input: 'com.jeffser.Alpaca.desktop.in',
       output: 'com.jeffser.Alpaca.desktop',
         type: 'desktop',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'applications'
)

desktop_utils = find_program('desktop-file-validate', required: true)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

appstream_file = i18n.merge_file(
        input: 'com.jeffser.Alpaca.metainfo.xml.in',
       output: 'com.jeffser.Alpaca.metainfo.xml',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

appstreamcli = find_program('appstreamcli', required: true, disabler: true)
test('Validate appstream file', appstreamcli,
     args: ['validate', '--no-net', '--explain', appstream_file])

install_data('com.jeffser.Alpaca.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas'
)

compile_schemas = find_program('glib-compile-schemas', required: true, disabler: true)
test('Validate schema file',
     compile_schemas,
     args: ['--strict', '--dry-run', meson.current_source_dir()])

service_conf = configuration_data()
service_conf.set('appid', application_id)
service_conf.set('libexecdir', join_paths(get_option('prefix'), get_option('bindir')))
configure_file(
  input: 'com.jeffser.Alpaca.SearchProvider.service.in',
  output: '@0@.SearchProvider.service'.format(application_id),
  configuration: service_conf,
  install_dir: join_paths(join_paths(get_option('prefix'), get_option('datadir')), 'dbus-1', 'services')
)

search_provider_conf = configuration_data()
search_provider_conf.set('appid', application_id)
configure_file(
  configuration: search_provider_conf,
  input: files('com.jeffser.Alpaca.SearchProvider.ini.in'),
  install_dir: join_paths(get_option('datadir'), 'gnome-shell', 'search-providers'),
  output: '@0@.SearchProvider.ini'.format(application_id)
)


subdir('icons')