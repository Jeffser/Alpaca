# openai_instances.py

from gi.repository import Adw, GLib

import openai, requests, json, logging, threading, re
from pydantic import BaseModel

from .. import dialog, tools
from ...sql_manager import generate_uuid, Instance as SQL
from ...constants import MAX_TOKENS_TITLE_GENERATION, TITLE_GENERATION_PROMPT_OPENAI

logger = logging.getLogger(__name__)

# Base instance, don't use directly
class BaseInstance:
    instance_id = None
    description = None
    limitations = ()

    default_properties = {
        'name': _('Instances'),
        'api': '',
        'max_tokens': 2048,
        'override_parameters': True,
        'temperature': 0.7,
        'seed': 0,
        'default_model': None,
        'title_model': None
    }

    def __init__(self, instance_id:str, properties:dict):
        self.row = None
        self.instance_id = instance_id
        self.available_models = None
        self.properties = {}
        for key in self.default_properties:
            self.properties[key] = properties.get(key, self.default_properties.get(key))
        if 'no-seed' in self.limitations and 'seed' in self.properties:
            del self.properties['seed']
        self.properties['url'] = self.instance_url

        self.client = openai.OpenAI(
            base_url=self.properties.get('url').strip(),
            api_key=self.properties.get('api')
        )

    def stop(self):
        pass

    def start(self):
        pass

    def prepare_chat(self, bot_message):
        bot_message.chat.busy = True
        if bot_message.chat.chat_id:
            bot_message.chat.row.spinner.set_visible(True)
            bot_message.get_root().global_footer.toggle_action_button(False)
        bot_message.chat.set_visible_child_name('content')

        messages = bot_message.chat.convert_to_json()[:list(bot_message.chat.container).index(bot_message)]
        return bot_message.chat, messages

    def generate_message(self, bot_message, model:str):
        chat, messages = self.prepare_chat(bot_message)

        if chat.chat_id and [m.get('role') for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    '\n'.join([c.get('text') for c in messages[-1].get('content') if c.get('type') == 'text']),
                    model
                )
            ).start()

        self.generate_response(bot_message, chat, messages, model, None)

    def use_tools(self, bot_message, model:str, available_tools:dict, generate_message:bool):
        chat, messages = self.prepare_chat(bot_message)
        if bot_message.options_button:
            bot_message.options_button.set_active(False)
        GLib.idle_add(bot_message.block_container.add_css_class, 'dim-label')
        bot_message.block_container.prepare_generating_block()

        if chat.chat_id and [m.get('role') for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    '\n'.join([c.get('text') for c in messages[-1].get('content') if c.get('type') == 'text']),
                    model
                )
            ).start()

        tools_used = []

        try:
            tools.log_to_message(_("Selecting tool to use..."), bot_message, True)
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[v.get_tool() for v in available_tools.values()]
            )
            if completion.choices[0] and completion.choices[0].message:
                if completion.choices[0].message.tool_calls:
                    for call in completion.choices[0].message.tool_calls:
                        tools.log_to_message(_("Using {}").format(call.function.name), bot_message, True)
                        if available_tools.get(call.function.name):
                            response = str(available_tools.get(call.function.name).run(json.loads(call.function.arguments), messages, bot_message))
                            attachment_content = []

                            if len(json.loads(call.function.arguments)) > 0:
                                attachment_content += [
                                    '## {}'.format(_('Arguments')),
                                    '| {} | {} |'.format(_('Argument'), _('Value')),
                                    '| --- | --- |'
                                ]
                                attachment_content += ['| {} | {} |'.format(k, v) for k, v in json.loads(call.function.arguments).items()]

                            attachment_content += [
                                '## {}'.format(_('Result')),
                                response
                            ]

                            attachment = bot_message.add_attachment(
                                file_id = generate_uuid(),
                                name = available_tools.get(call.function.name).name,
                                attachment_type = 'tool',
                                content = '\n'.join(attachment_content)
                            )
                            SQL.insert_or_update_attachment(bot_message, attachment)
                        else:
                            response = ''

                        arguments = json.loads(call.function.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": response
                        })
                        tools_used.append({
                            "name": call.function.name,
                            "arguments": arguments,
                            "response": response
                        })

        except Exception as e:
            dialog.simple_error(
                parent = bot_message.get_root(),
                title = _('Tool Error'),
                body = _('An error occurred while running tool'),
                error_log = e
            )
            logger.error(e)

        if generate_message:
            tools.log_to_message(_("Generating message..."), bot_message, True)
            GLib.idle_add(bot_message.block_container.remove_css_class, 'dim-label')
            self.generate_response(bot_message, chat, messages, model, tools_used if len(tools_used) > 0 else None)
        else:
            GLib.idle_add(bot_message.block_container.clear)
            bot_message.finish_generation()

    def generate_response(self, bot_message, chat, messages:list, model:str, tools_used:list):
        if bot_message.options_button:
            bot_message.options_button.set_active(False)
        bot_message.block_container.prepare_generating_block()

        if 'no-system-messages' in self.limitations:
            for i in range(len(messages)):
                if messages[i].get('role') == 'system':
                    messages[i]['role'] = 'user'

        if 'text-only' in self.limitations:
            for i in range(len(messages)):
                for c in range(len(messages[i].get('content', []))):
                    if messages[i].get('content')[c].get('type') != 'text':
                        del messages[i]['content'][c]
                    else:
                        messages[i]['content'] = messages[i].get('content')[c].get('text')

        params = {
            "model": model,
            "messages": messages,
            "stream": True
        }

        if self.properties.get('max_tokens', 0) > 0:
            params["max_tokens"] = int(self.properties.get('max_tokens', 0))
        if tools_used:
            params["tools"] = tools_used
            params["tool_choice"] = "none"

        if self.properties.get("override_parameters"):
            params["temperature"] = self.properties.get('temperature', 0.7)
            if self.properties.get('seed', 0) != 0:
                params["seed"] = self.properties.get('seed')

        if chat.busy:
            try:
                GLib.idle_add(bot_message.block_container.clear)
                response = self.client.chat.completions.create(**params)
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            bot_message.update_message(delta.content)
                    if not chat.busy:
                        break
            except Exception as e:
                dialog.simple_error(
                    parent = bot_message.get_root(),
                    title = _('Instance Error'),
                    body = _('Message generation failed'),
                    error_log = e
                )
                logger.error(e)
                if self.row:
                    self.row.get_parent().unselect_all()
        bot_message.finish_generation()

    def generate_chat_title(self, chat, prompt:str, fallback_model:str):
        class ChatTitle(BaseModel): # Pydantic
            title: str
            emoji: str = ""

        messages = [
            {"role": "user" if 'no-system-messages' in self.limitations else "system", "content": TITLE_GENERATION_PROMPT_OPENAI},
            {"role": "user", "content": "Generate a title for this prompt:\n{}".format(prompt)}
        ]
        model = self.get_title_model()
        params = {
            "temperature": 0.2,
            "model": model if model else fallback_model,
            "messages": messages,
            "max_tokens": MAX_TOKENS_TITLE_GENERATION
        }
        new_chat_title = chat.get_name()

        try:
            completion = self.client.beta.chat.completions.parse(**params, response_format=ChatTitle)
            response = completion.choices[0].message
            if response.parsed:
                emoji = response.parsed.emoji if len(response.parsed.emoji) == 1 else ''
                new_chat_title = '{} {}'.format(emoji, response.parsed.title)
        except Exception as e:
            try:
                response = self.client.chat.completions.create(**params)
                new_chat_title = str(response.choices[0].message.content)
            except Exception as e:
                logger.error(e)
        
        new_chat_title = re.sub(r'<think>.*?</think>', '', new_chat_title).strip()

        if len(new_chat_title) > 30:
            new_chat_title = new_chat_title[:30].strip() + '...'

        chat.row.rename(new_chat_title)

    def get_default_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if not self.properties.get('default_model') or not self.properties.get('default_model') in [m.get('name') for m in local_models]:
                self.properties['default_model'] = local_models[0].get('name')
            return self.properties.get('default_model')

    def get_title_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if self.properties.get('title_model') and not self.properties.get('title_model') in [m.get('name') for m in local_models]:
                self.properties['title_model'] = local_models[0].get('name')
            return self.properties.get('title_model')

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                for m in self.client.models.list():
                    if all(s not in m.id.lower() for s in ['embedding', 'davinci', 'dall', 'tts', 'whisper', 'image']):
                        self.available_models[m.id] = {}
            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return {}

    def pull_model(self, model_name:str, callback:callable):
        SQL.append_online_instance_model_list(self.instance_id, model_name)
        callback({'status': 'success'})

    def get_local_models(self) -> list:
        local_models = []
        for model in SQL.get_online_instance_model_list(self.instance_id):
            local_models.append({'name': model})
        return local_models

    def delete_model(self, model_name:str) -> bool:
        SQL.remove_online_instance_model_list(self.instance_id, model_name)
        return True

    def get_model_info(self, model_name:str) -> dict:
        return {}

class ChatGPT(BaseInstance):
    instance_type = 'chatgpt'
    instance_type_display = 'OpenAI ChatGPT'
    instance_url = 'https://api.openai.com/v1/'

class Gemini(BaseInstance):
    instance_type = 'gemini'
    instance_type_display = 'Google Gemini'
    instance_url = 'https://generativelanguage.googleapis.com/v1beta/openai/'
    limitations = ('no-system-messages')

    def __init__(self, instance_id:str, properties:dict):
        super().__init__(instance_id, properties)
        if 'seed' in self.properties:
            del self.properties['seed']

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get('https://generativelanguage.googleapis.com/v1beta/models?key={}'.format(self.properties.get('api')))
                for model in response.json().get('models', []):
                    if "generateContent" in model.get("supportedGenerationMethods", []) and 'deprecated' not in model.get('description', ''):
                        model['name'] = model.get('name').removeprefix('models/')
                        self.available_models[model.get('name')] = model
            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
        return []

    def get_model_info(self, model_name:str) -> dict:
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models/{}?key={}'.format(model_name, self.properties.get('api')))
            data = response.json()
            data['capabilities'] = ['completion', 'vision']
            return data
        except Exception as e:
            logger.error(e)
        return {}

class Together(BaseInstance):
    instance_type = 'together'
    instance_type_display = 'Together AI'
    instance_url = 'https://api.together.xyz/v1/'

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get(
                    'https://api.together.xyz/v1/models',
                    headers={
                        'accept': 'application/json',
                        'authorization': 'Bearer {}'.format(self.properties.get('api'))
                    }
                )
                for model in response.json():
                    if model.get('id') and model.get('type') == 'chat':
                        self.available_models[model.get('id')] = {'display_name': model.get('display_name')}
            return self.available_models


            return models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()

class Venice(BaseInstance):
    instance_type = 'venice'
    instance_type_display = 'Venice'
    instance_url = 'https://api.venice.ai/api/v1/'
    limitations = ('no-system-messages')

    def __init__(self, instance_id:str, properties:dict):
        super().__init__(instance_id, properties)
        if 'seed' in self.properties:
            del self.properties['seed']

class Deepseek(BaseInstance):
    instance_type = 'deepseek'
    instance_type_display = 'Deepseek'
    instance_url = 'https://api.deepseek.com/v1/'
    limitations = ('text-only')

    def __init__(self, instance_id:str, properties:dict):
        super().__init__(instance_id, properties)
        if 'seed' in self.properties:
            del self.properties['seed']

class Groq(BaseInstance):
    instance_type = 'groq'
    instance_type_display = 'Groq Cloud'
    instance_url = 'https://api.groq.com/openai/v1'
    limitations = ('text-only')

class Anthropic(BaseInstance):
    instance_type = 'anthropic'
    instance_type_display = 'Anthropic'
    instance_url = 'https://api.anthropic.com/v1/'
    limitations = ('no-system-messages')

class OpenRouter(BaseInstance):
    instance_type = 'openrouter'
    instance_type_display = 'OpenRouter AI'
    instance_url = 'https://openrouter.ai/api/v1/'

    def get_available_models(self) -> list:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get('https://openrouter.ai/api/v1/models')
                for model in response.json().get('data', []):
                    if model.get('id'):
                        self.available_models[model.get('id')] = {'display_name': model.get('name')}

            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return []

class Qwen(BaseInstance):
    instance_type = 'qwen'
    instance_type_display = 'Qwen (DashScope)'
    instance_url = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    description = _('Alibaba Cloud Qwen large language models via DashScope')
    
class Fireworks(BaseInstance):
    instance_type = 'fireworks'
    instance_type_display = 'Fireworks AI'
    instance_url = 'https://api.fireworks.ai/inference/v1/'
    description = _('Fireworks AI inference platform')

    def get_available_models(self) -> list:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get(
                    'https://api.fireworks.ai/inference/v1/models',
                    headers={
                        'Authorization': f'Bearer {self.properties.get("api")}'
                    }
                )
                for model in response.json().get('data', []):
                    if model.get('id') and 'chat' in model.get('capabilities', []):
                        self.available_models[model.get('id')] = {'display_name': model.get('name')}

            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return []

class LambdaLabs(BaseInstance):
    instance_type = 'lambda_labs'
    instance_type_display = 'Lambda Labs'
    instance_url = 'https://api.lambdalabs.com/v1/'
    description = _('Lambda Labs cloud inference API')

    def get_available_models(self) -> list:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = []
                response = requests.get(
                    'https://api.lambdalabs.com/v1/models',
                    headers={
                        'Authorization': f'Bearer {self.properties.get("api")}'
                    }
                )
                for model in response.json().get('data', []):
                    if model.get('id'):
                        self.available_models[model.get('id')] = {'display_name': model.get('name')}

            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent = self.row.get_root() if self.row else None,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return []

class Cerebras(BaseInstance):
    instance_type = 'cerebras'
    instance_type_display = 'Cerebras AI'
    instance_url = 'https://api.cerebras.ai/v1/'
    description = _('Cerebras AI cloud inference API')

class Klusterai(BaseInstance):
    instance_type = 'klusterai'
    instance_type_display = 'Kluster AI'
    instance_url = 'https://api.kluster.ai/v1/'
    description = _('Kluster AI cloud inference API')

class Kimi(BaseInstance):
    instance_type = 'kimi'
    instance_type_display = 'Kimi (Moonshot AI)'
    instance_url = 'https://api.moonshot.ai/v1/'
    description = _('Kimi large language models by Moonshot AI')
    limitations = ('no-seed',)

class Mistral(BaseInstance):
    instance_type = 'mistral'
    instance_type_display = 'Mistral AI'
    instance_url = 'https://api.mistral.ai/v1/'
    description = _('Mistral AI large language models')
    limitations = ('text-only')

class LlamaAPI(BaseInstance):
    instance_type = 'llama-api'
    instance_type_display = 'Llama API'
    instance_url = 'https://api.llama.com/compat/v1/'
    description = _('Meta AI Llama API')

class NovitaAI(BaseInstance):
    instance_type = 'novitaai'
    instance_type_display = 'Novita AI'
    instance_url = 'https://api.novita.ai/v3/openai/'
    description = _('Novita AI cloud inference API')
    limitations = ('no-seed',)

class DeepInfra(BaseInstance):
    instance_type = 'deepinfra'
    instance_type_display = 'DeepInfra'
    instance_url = 'https://api.deepinfra.com/v1/openai'
    description = _('DeepInfra cloud inference API')

class CompactifAI(BaseInstance):
    instance_type = 'compactifai'
    instance_type_display = 'CompactifAI'
    instance_url = 'https://your-compactifai-api-endpoint/v1'
    description = _('CompactifAI inference platform')

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get(
                    f'{self.instance_url}/models',
                    headers={
                        'Authorization': f'Bearer {self.properties.get("api")}'
                    }
                )
                for model in response.json().get('data', []):
                    if model.get('id'):
                        self.available_models[model.get('id')] = {
                            'display_name': model.get('name', model.get('id'))
                        }
            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent=self.row.get_root() if self.row else None,
                title=_('Instance Error'),
                body=_('Could not retrieve CompactifAI models'),
                error_log=e
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return {}


class GenericOpenAI(BaseInstance):
    instance_type = 'openai:generic'
    instance_type_display = _('OpenAI Compatible Instance')
    instance_url = ''
    description = _('AI instance compatible with OpenAI library')

    def __init__(self, instance_id:str, properties:dict):
        self.instance_url = properties.get('url', '')
        super().__init__(instance_id, properties)
