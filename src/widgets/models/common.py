# common.py

from gi.repository import Gtk, Gio, Adw

available_models_data = {}

class CategoryPill(Adw.Bin):
    __gtype_name__ = 'AlpacaCategoryPillNEW'

    metadata = {
        'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
        'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
        'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
        'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
        'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
        'tools': {'name': _('Tools'), 'css': ['accent'], 'icon': 'wrench-wide-symbolic'},
        'reasoning': {'name': _('Reasoning'), 'css': ['accent'], 'icon': 'brain-augemnted-symbolic'},
        'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
        'medium': {'name': _('Medium'), 'css': ['brown'], 'icon': 'sprout-symbolic'},
        'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
        'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'},
        'language': {'css': [], 'icon': 'language-symbolic'}
    }

    def __init__(self, name_id:str, show_label:bool):
        if 'language:' in name_id:
            self.metadata['language']['name'] = name_id.split(':')[1]
            name_id = 'language'
        button_content = Gtk.Box(
            spacing=5,
            halign=3
        )
        button_content.append(Gtk.Image.new_from_icon_name(self.metadata.get(name_id, {}).get('icon', 'language-symbolic')))
        if show_label:
            button_content.append(Gtk.Label(
                label='<span weight="bold">{}</span>'.format(self.metadata.get(name_id, {}).get('name')),
                use_markup=True
            ))
        super().__init__(
            css_classes=['subtitle', 'category_pill'] + self.metadata.get(name_id, {}).get('css', []) + ([] if show_label else ['circle']),
            tooltip_text=self.metadata.get(name_id, {}).get('name'),
            child=button_content,
            halign=0 if show_label else 1,
            focusable=False,
            hexpand=True
        )

def get_local_models(root) -> dict:
    window = root.get_application().main_alpaca_window
    results = {}
    for model in [item.get_child() for item in list(window.local_model_flowbox) if item.get_child().__gtype_name__ == 'AlpacaAddedModelButton']:
        results[model.get_name()] = model
    return results
