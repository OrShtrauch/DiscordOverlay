from tempfile import gettempdir
from tkinter import *
from tkinter import font
from tkinter.simpledialog import askstring
from requests import get, patch
from requests.exceptions import RequestException
from logging import getLogger, basicConfig, DEBUG

HTTP_200_OK: int = 200
GUILD_VOICE_TYPE: int = 2

TMP_FILE: str = "./user_id.txt"
LOG_FILE: str = "./log.txt"
TOKEN_FILE: str = "./token.txt"

SERVER_ID: str = "1244748455885410355"
with open(TOKEN_FILE, 'r') as fd:
    TOKEN: str = fd.read()


basicConfig(filename=LOG_FILE,
                filemode='a',
                format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                datefmt='%H:%M:%S',
                level=DEBUG)

class GetVoiceChannelsError(Exception):
    pass

class ChangeVoiceChannelError(Exception):
    pass

class UpdateUserIDInStorageError(Exception):
    pass

class NoUserIDInStorageError(Exception):
    pass

class Channel:
    def __init__(self, channel_id: str, channel_name: str) -> None:
        self.channel_id = channel_id
        self.channel_name = channel_name

    def __repr__(self) -> str:
        return f"<Channel {self.channel_name} - {self.channel_id}>"

class StorageManager:
    def __init__(self, temp_file_path: str) -> None:
        self.temp_file_path: str = temp_file_path
        self._logger = getLogger("storage_manager")

    @property
    def user_id(self) -> str:
        self._logger.info("Trying to get user_id from storage_manager")

        try:
            with open(self.temp_file_path, "r") as f:
                user_id: str = f.read()
        except IOError as e:
            self._logger.exception(f"Could not find any user_id in storage - {str(e)}")
            raise NoUserIDInStorageError("Could not find any user_id in storage") from e

        self._logger.info(f"Got user_id from storage_manager - {user_id}")
        return user_id

    @user_id.setter
    def user_id(self, user_id: str) -> None:
        self._logger.info(f"Trying to set user_id to {user_id} from storage_manager")

        try:
            with open(self.temp_file_path, "w") as f:
                f.write(user_id)
        except IOError as e:
            self._logger.exception(f"Could not update user_id {user_id} in storage - {str(e)}")
            raise UpdateUserIDInStorageError(f"Could not update user_id {user_id} in storage") from e

class Discord:
    def __init__(self, server_id: str, token: str, user_id: str) -> None:
        self.server_id: str = server_id
        self.user_id: str = user_id
        self._logger = getLogger("discord_client")
        self.headers: dict[str, str] = {"Authorization": token}
        self.base_url: str = "https://discord.com/api/v10/guilds"
        self.channels: list[Channel] = self._get_voice_channels()

    def _get_voice_channels(self) -> list[Channel]:
        url: str = f"{self.base_url}/{self.server_id}/channels"
        self._logger.info(f"Running HTTP GET to {url}")
        
        try:
            response = get(url, headers=self.headers)
            self._logger.info(f"GET Response: {response.status_code} - {str(response)}")
        except RequestException as e:
            self._logger.exception(f"Failed to get voice channels - {str(e)}")
            raise GetVoiceChannelsError(f"Failed to get voice channels - {str(e)}") from e

        if response.status_code is not HTTP_200_OK:
            self._logger.exception("Error fetching channels", response.status_code)
            raise GetVoiceChannelsError(f"Failed to get voice channels, status - {response.status_code}") from e

        try:
            channels = response.json()
        except ValueError as e:
            self._logger.exception(f"Failed to parse channels response - {str(e)}")
            raise GetVoiceChannelsError(f"Failed to parse channels response - {str(e)}") from e

        return [
            Channel(ch.get("id"), ch.get("name"))
            for ch in channels 
            if ch.get("type") is GUILD_VOICE_TYPE and ch.get("name")
        ]            

    def change_voice_channel(self, channel_id: str) -> None:
        url: str = f"{self.base_url}/{self.server_id}/members/{self.user_id}"
        body: dict[str, str] = {"channel_id": channel_id}
        self._logger.info(f"Running HTTP PATCH to {url} with body {body}")

        try:
            response = patch(url, headers=self.headers, json=body)
            self._logger.info(f"PATCH Response: {response.status_code} - {str(response)}")
        except RequestException as e:
            self._logger.exception(f"Failed to change {self.user_id} to channel {channel_id} - {str(response)} - {str(e)}")
            raise ChangeVoiceChannelError(f"Failed to change {self.user_id} to channel {channel_id} - {str(response)}") from e

        if response.status_code is not HTTP_200_OK:
            raise ChangeVoiceChannelError(f"Failed to change {self.user_id} to channel {channel_id} - {response.status_code} - {str(response)}")

class UIManager:
    def __init__(self):
        self.storage_manager = StorageManager(TMP_FILE)
        self.buttons: set[Button] = set()
        self.discord_client: Discord | None = None
        self.button_frame: Frame | None = None
        self.root = self._get_root_window()


    def _get_root_window(self):
        root = Tk()
        root.title("overlay") 

        root.overrideredirect(True) 
        root.attributes("-transparent") 

        self.button_frame = Frame(root)
        self.button_frame.pack(fill=X, expand=True)

        try:
            user_id: str = self.storage_manager.user_id
        except NoUserIDInStorageError:
            self.storage_manager.user_id = askstring('user_id', "Enter user id")

        self.discord_client = Discord(SERVER_ID, TOKEN, self.storage_manager.user_id)
        print(self.storage_manager.user_id)

        self._render_channel_buttons(self.discord_client.channels)
        root.wm_attributes("-topmost", 1)

        return root

    def _render_channel_buttons(self, channels):
        default_font = font.nametofont("TkDefaultFont")
        
        for index, ch in enumerate(channels):
            print(ch)
            text_width = default_font.measure(ch.channel_name) + 20
            button = Button(self.button_frame, text=ch.channel_name, bg="white", fg="black",
                            width=text_width // default_font.measure("0"), padx=5)
            button.config(command=lambda channel=ch: self._on_click(channel))
            button.pack(side=LEFT)
            
            self.buttons.add(button)

    def _on_click(self, channel: Channel) -> None:
        try:
            self.discord_client.change_voice_channel(channel.channel_id)
        except ChangeVoiceChannelError as e:
            print(str(e))

        self.highlight_button(channel.channel_name)

    def highlight_button(self, text) -> None:
        for b in self.buttons:
            if b.cget("text") == text:
                b.config(bg="white", fg="red")
            else:
                b.config(bg="white", fg="black")


    def start_loop(self) -> None:
        self.root.mainloop()

def on_click(ch: Channel, buttons: list[Button]) -> None:
    print("on_click", ch)

    if not move_user_to_channel(SERVER_ID, TOKEN, ch.channel_id, get_user_id()):
        return

    for b in buttons:
        if b.cget("text") == ch.channel_name:
            b.config(bg="white", fg="red")
        else:
            b.config(bg="white", fg="black")

if __name__ == "__main__":
    UIManager().start_loop()