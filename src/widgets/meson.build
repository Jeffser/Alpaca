moduledir = get_option('prefix') / get_option('datadir') / meson.project_name() / 'alpaca' / 'widgets'

widgets = [
  '__init__.py',
  'message.py',
  'chat.py',
  'terminal.py',
  'dialog.py',
  'attachments.py',
  'voice.py',
  'camera.py',
  'welcome.py',
  'preferences.py'
]

install_data(widgets, install_dir: moduledir)

subdir('blocks')
subdir('tools')
subdir('instances')
subdir('models')