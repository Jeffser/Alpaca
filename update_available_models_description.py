"""
Moves the descriptions of models to src/available_models_descriptions.py
so they can be translated
"""
import json

if __name__ == "__main__":
    with open('src/available_models.json', 'r', encoding="utf-8") as f:
        data = json.load(f)
    RESULTS = 'descriptions = {\n'
    for key, value in data.items():
        RESULTS += f"   '{key}': _(\"{value['description']}\"),\n"
    RESULTS += '}'
    with open('src/available_models_descriptions.py', 'w+', encoding="utf-8") as f:
        f.write(RESULTS)
