moduledir = get_option('prefix') / get_option('datadir') / meson.project_name() / 'alpaca' / 'widgets'

widgets = [
  '__init__.py',
  'message.py',
  'chat.py',
  'dialog.py',
  'attachments.py',
  'voice.py',
  'welcome.py',
  'preferences.py',
]

install_data(widgets, install_dir: moduledir)

subdir('activities')
subdir('blocks')
subdir('tools')
subdir('instances')
subdir('models')