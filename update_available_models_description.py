import json
with open('src/available_models.json', 'r') as f:
    data = json.load(f)
results = 'descriptions = {\n'
for key, value in data.items():
    results += f"   '{key}': _(\"{value['description']}\"),\n"
results += '}'
with open('src/available_models_descriptions.py', 'w+') as f:
    f.write(results)