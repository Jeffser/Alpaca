# ollama_manager.py

from gi.repository import Adw, Gtk, GLib, Gio
from ...constants import is_ollama_installed, is_rocm_installed, OLLAMA_BINARY_PATH, CAN_SELF_MANAGE_OLLAMA, DEVICE_ARCH, cache_dir, data_dir
import requests, os, threading, tarfile, shutil
import zstandard as zstd
from pathlib import Path

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/instances/ollama_manager.ui')
class OllamaManager(Adw.Dialog):
    __gtype_name__ = 'AlpacaOllamaManager'

    toast_overlay = Gtk.Template.Child()
    navigation_view = Gtk.Template.Child()
    main_status_page = Gtk.Template.Child()
    gpu_row = Gtk.Template.Child()
    gpu_suffix = Gtk.Template.Child()
    logs_row = Gtk.Template.Child()
    update_row = Gtk.Template.Child()
    delete_row = Gtk.Template.Child()
    logs_el = Gtk.Template.Child()
    installer_statuspage = Gtk.Template.Child()
    delete_rocm_button = Gtk.Template.Child()
    update_status_page = Gtk.Template.Child()

    def __init__(self, instance):
        super().__init__()
        self.instance = instance

        #top 10 worst lines of code
        list(list(list(list(list(self.installer_statuspage)[0].get_child())[0])[0])[0])[2].add_css_class('monospace')

        if self.instance.version_number:
            self.main_status_page.set_description(_('Version') + ' ' + self.instance.version_number)

        self.logs_el.text_view.set_editable(False)
        self.gpu_row.set_visible(DEVICE_ARCH == "amd64")
        self.update_row.set_visible(CAN_SELF_MANAGE_OLLAMA)
        self.delete_row.set_visible(CAN_SELF_MANAGE_OLLAMA)

        if CAN_SELF_MANAGE_OLLAMA:
            gpu_status_strings = [
                _('ROCm is available for download (might not work with your GPU)'),
                _('GPU is using Vulkan'),
                _('ROCm is available for download'),
                _('ROCm is in use')
            ]
            if self.instance.rocm_status == 0 and is_rocm_installed():
                subtitle_string = _("Incompatible GPU, Vulkan might work")
                sensitive = False
            else:
                subtitle_string = gpu_status_strings[self.instance.rocm_status]
                sensitive = self.instance.rocm_status in (0, 2)
            self.gpu_row.set_subtitle(subtitle_string)
            self.gpu_row.set_sensitive(sensitive and CAN_SELF_MANAGE_OLLAMA)
            self.gpu_row.set_selectable(sensitive and CAN_SELF_MANAGE_OLLAMA)
            self.gpu_suffix.set_visible(sensitive and CAN_SELF_MANAGE_OLLAMA)

        if is_ollama_installed():
            self.navigation_view.replace_with_tags(["installed"])
        else:
            self.navigation_view.replace_with_tags(["not_installed"])

    @Gtk.Template.Callback()
    def logs_requested(self, row):
        self.logs_el.set_text(self.instance.log_raw)
        self.navigation_view.push_by_tag('logs')

    def format_bytes(self, size:int):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB" # Petabyte download lol

    # Call in different thread pls
    def start_download(self, title:str, url:str, dest_path:str) -> bool:
        # returns true if download went ok
        self.navigation_view.replace_with_tags(["installing"])
        self.installer_statuspage.set_title(title)

        def update_ui(downloaded, total):
            done = self.format_bytes(downloaded)
            remaining = self.format_bytes(total) if total > 0 else _("Unknown")

            self.installer_statuspage.set_description('{} / {}'.format(done, remaining))
            self.installer_statuspage.get_child().set_fraction(downloaded / total)

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        chunk_size = 8192

        try:
            with open(dest_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        GLib.idle_add(update_ui, downloaded_size, total_size)
                    if not self.get_root():
                        return False
        except:
            return False
        return True

    def remove_ollama(self):
        ollama_path = Path(os.path.join(data_dir, 'ollama_installation'))
        if ollama_path.exists():
            shutil.rmtree(ollama_path)

    def remove_rocm(self):
        rocm_path = Path(os.path.join(data_dir, 'ollama_installation', 'lib', 'ollama', 'rocm'))
        if rocm_path.exists():
            shutil.rmtree(rocm_path)

    # Call in different thread pls
    def install_latest_ollama(self) -> bool:
        # returns true if install went ok
        ollama_tag = get_latest_ollama_tag()
        url = "https://github.com/ollama/ollama/releases/download/{}/ollama-linux-{}.tar.zst".format(ollama_tag, DEVICE_ARCH)
        dest_path = os.path.join(cache_dir, 'OLLAMA_DOWNLOAD.tar.zst')

        result = self.start_download(
            title = _("Downloading Ollama"),
            url = url,
            dest_path = dest_path
        )

        if result:
            self.installer_statuspage.set_description(_("Installing…"))
            archive = Path(dest_path)
            out_dir = Path(os.path.join(data_dir, 'ollama_installation'))
            self.remove_ollama() # Delete existing installation
            out_dir.mkdir(parents=True, exist_ok=True)

            with archive.open("rb") as f:
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(f) as reader:
                    with tarfile.open(fileobj=reader, mode="r|") as tar:
                        tar.extractall(path=out_dir)

            archive.unlink(missing_ok=True)
            return True

    # Call in different thread pls
    def install_latest_rocm(self) -> bool:
        # returns true if install went ok
        ollama_tag = get_latest_ollama_tag()
        url = "https://github.com/ollama/ollama/releases/download/{}/ollama-linux-amd64-rocm.tar.zst".format(ollama_tag)
        dest_path = os.path.join(cache_dir, 'ROCM_DOWNLOAD.tar.zst')

        result = self.start_download(
            title = _("Downloading ROCm"),
            url = url,
            dest_path = dest_path
        )

        if result:
            self.installer_statuspage.set_description(_("Installing…"))
            archive = Path(dest_path)

            temp_dir = Path(os.path.join(cache_dir, 'rocm_temp'))
            temp_dir.mkdir(parents=True, exist_ok=True)

            out_dir = Path(os.path.join(data_dir, 'ollama_installation'))
            self.remove_rocm() # Delete existing installation
            out_dir.mkdir(parents=True, exist_ok=True)

            with archive.open("rb") as f:
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(f) as reader:
                    with tarfile.open(fileobj=reader, mode="r|") as tar:
                        tar.extractall(path=temp_dir)

            shutil.copytree(
                temp_dir,
                out_dir,
                dirs_exist_ok=True
            )

            shutil.rmtree(temp_dir)
            archive.unlink(missing_ok=True)
            return True

    @Gtk.Template.Callback()
    def initial_rocm_installation_requested(self, button):
        def run_install():
            result = self.install_latest_rocm()
            self.navigation_view.replace_with_tags(["installation_ok"] if result else ["error"])
            self.instance.stop()
        threading.Thread(target=run_install, daemon=True).start()

    @Gtk.Template.Callback()
    def initial_ollama_installation_requested(self, button):
        def run_install():
            result = self.install_latest_ollama()
            self.navigation_view.replace_with_tags(["installation_ok"] if result else ["error"])
            self.instance.stop()
            threading.Thread(target=self.instance.start).start()
        if CAN_SELF_MANAGE_OLLAMA:
            threading.Thread(target=run_install, daemon=True).start()
        else:
            self.navigation_view.replace_with_tags(["incompatible_installer"])

    @Gtk.Template.Callback()
    def delete_installation_requested(self, row):
        self.delete_rocm_button.set_visible(is_rocm_installed())
        self.navigation_view.push_by_tag('removing')

    @Gtk.Template.Callback()
    def delete_rocm(self, button):
        self.remove_rocm()
        self.instance.row.get_parent().unselect_all()
        self.close()

    @Gtk.Template.Callback()
    def delete_ollama(self, button):
        self.remove_ollama()
        self.instance.row.get_parent().unselect_all()
        self.close()

    @Gtk.Template.Callback()
    def update_check_requested(self, row):
        installed_tag = self.instance.version_number.strip('v').strip()
        available_tag = get_latest_ollama_tag()

        if available_tag:
            available_tag = available_tag.strip('v').strip()
            if installed_tag == available_tag:
                toast = Adw.Toast(
                    title=_("Latest Version Installed ({})").format(installed_tag)
                )
                self.toast_overlay.add_toast(toast)
            else:
                self.navigation_view.push_by_tag('update_available')
                self.update_status_page.set_description(_("Version") + " " + available_tag)
        else:
            self.navigation_view.push_by_tag('error')

    @Gtk.Template.Callback()
    def update_requested(self, button):
        def run_update():
            rocm_installed = is_rocm_installed()

            result = self.install_latest_ollama()
            if not result:
                self.navigation_view.replace_with_tags(["error"])
                self.instance.stop()
                threading.Thread(target=self.instance.start).start()
                return

            if rocm_installed: # if it was installed already, update it
                result = self.install_latest_rocm()

            self.navigation_view.replace_with_tags(["installation_ok"] if result else ["error"])
            self.instance.stop()
            threading.Thread(target=self.instance.start).start()


        threading.Thread(target=run_update).start()

def get_latest_ollama_tag() -> str or None:
    url = f"https://api.github.com/repos/ollama/ollama/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get('tag_name')
    except:
        return
