moduledir = get_option('prefix') / get_option('datadir') / meson.project_name() / 'alpaca' / 'widgets' / 'instances'

instances = [
  '__init__.py',
  'openai_instances.py',
  'ollama_instances.py',
  'ollama_manager.py'
]

install_data(instances, install_dir: moduledir)