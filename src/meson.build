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
  'ui/widgets/instances/preferences.blp',
  'ui/widgets/message/popup.blp',
  'ui/widgets/message/message.blp',
  'ui/widgets/chat/folder.blp',
  'ui/widgets/chat/template_selector.blp',
  'ui/widgets/chat/chat.blp',
  'ui/widgets/chat/folder_row.blp',
  'ui/widgets/chat/chat_row.blp',
  'ui/widgets/models/added_dialog.blp',
  'ui/widgets/models/basic_dialog.blp',
  'ui/widgets/models/basic_button.blp',
  'ui/widgets/models/pulling_dialog.blp',
  'ui/widgets/models/available_dialog.blp',
  'ui/widgets/models/creator_dialog.blp',
  'ui/widgets/models/info_box.blp',
  'ui/widgets/models/category_pill.blp',
  'ui/widgets/models/added_selector.blp',
  'ui/widgets/blocks/code.blp',
  'ui/widgets/blocks/latex_renderer.blp',
  'ui/widgets/blocks/table.blp',
  'ui/widgets/blocks/editing_text.blp',
  'ui/widgets/blocks/generating_text.blp',
  'ui/widgets/activities/web_browser.blp',
  'ui/widgets/activities/background_remover.blp',
  'ui/widgets/activities/background_remover_image.blp',
  'ui/widgets/activities/camera.blp',
  'ui/widgets/activities/code_editor.blp',
  'ui/widgets/activities/attachment_creator.blp',
  'ui/widgets/activities/terminal.blp',
  'ui/widgets/activities/code_runner.blp',
  'ui/widgets/activities/transcriber.blp',
  'ui/widgets/activities/image_viewer.blp',
  'ui/widgets/activities/file_viewer.blp',
  'ui/widgets/message/global_message_textview.blp',
  'ui/widgets/message/global_action_stack.blp',
  'ui/widgets/message/global_footer.blp',
  'ui/widgets/message/block_container.blp',
  'ui/widgets/attachments/attachment_container.blp',
  'ui/widgets/attachments/global_attachment_button.blp',
  'ui/widgets/attachments/image_attachment_container.blp',
  'ui/widgets/attachments/image_attachment.blp',
  'ui/widgets/attachments/attachment.blp',
  'ui/widgets/tools/selector.blp',
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