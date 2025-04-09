# meta developer: @mypchikov

from .. import loader, utils

@loader.tds
class InlineBioMod(loader.Module):
    """Инлайн био"""

    strings = {"name": "InlineBio"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "image_url",
                "https://http.cat/images/426.jpg",
                doc="URL картинки"
            ),
            loader.ConfigValue(
                "buttons",
                [
                    {"text": "🌟 GitHub", "url": "https://github.com/"},
                    {"text": "💬 Telegram", "url": "https://t.me/"},
                    {"text": "🌍 Сайт", "url": "https://example.com"}
                ],
                doc="Список кнопок."
            )
        )

    def get_markup(self):
        buttons = self.config["buttons"]
        return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    @loader.command(
        ru_doc="Отправляет сообщение с картинкой и кнопками из конфига"
    )
    async def inlinebio(self, message):
        """Send inline message with image and buttons from config"""
        await self.inline.form(
            message=message,
            text="",
            photo=self.config["image_url"],
            reply_markup=self.get_markup()
        )
