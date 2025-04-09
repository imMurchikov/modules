# meta developer: @mypchikov

from .. import loader, utils
import aiohttp
from datetime import datetime

@loader.tds
class NightscoutMonitorMod(loader.Module):
    """Показывает текущий уровень глюкозы с сервера Nightscout"""

    strings = {"name": "NightscoutMonitor"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "nightscout_url",
                "https://your-nightscout.herokuapp.com",
                doc="URL Nightscout-сервера"
            ),
            loader.ConfigValue(
                "units",
                "mg/dL",  #  mmol/L
                doc="Формат глюкозы: mg/dL или mmol/L (без проверки)"
            )
        )

    async def _fetch_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.config['nightscout_url'].rstrip('/')}/api/v1/entries.json?count=1") as resp:
                if resp.status != 200:
                    raise Exception(f"Ошибка запроса: {resp.status}")
                data = await resp.json()
                return data[0] if data else None

    def _convert_units(self, sgv):
        if self.config["units"].lower() == "mmol/l":
            return round(sgv / 18.0182, 1)
        return sgv

    def _format_units(self):
        return "mmol/L" if self.config["units"].lower() == "mmol/l" else "mg/dL"

    def _trend_emoji(self, direction):
        trends = {
            "DoubleUp": "⬆️⬆️",
            "SingleUp": "⬆️",
            "FortyFiveUp": "↗️",
            "Flat": "➡️",
            "FortyFiveDown": "↘️",
            "SingleDown": "⬇️",
            "DoubleDown": "⬇️⬇️",
            "NOT COMPUTABLE": "❓",
            "RATE OUT OF RANGE": "⚠️"
        }
        return trends.get(direction, "❔")

    @loader.command()
    async def glucose(self, message):
        """Получить текущее значение глюкозы с сервера Nightscout"""
        try:
            entry = await self._fetch_data()
            if not entry:
                await utils.answer(message, "❌ Нет данных от сервера.")
                return

            sgv = self._convert_units(entry["sgv"])
            units = self._format_units()
            direction = self._trend_emoji(entry.get("direction", ""))
            device = entry.get("device", "неизвестно")
            date = datetime.fromtimestamp(entry["date"] / 1000)
            time_str = date.strftime('%H:%M:%S')
            ago = (datetime.now() - date).seconds // 60

            raw = entry.get("unfiltered", None)
            noise = entry.get("noise", None)
            delta = entry.get("delta", None)

            # Состояние
            status = "🟢 Норма"
            if self.config["units"].lower() == "mmol/l":
                if sgv < 4:
                    status = "🔴 Гипо"
                elif sgv > 10:
                    status = "🟡 Гипер"
            else:
                if sgv < 70:
                    status = "🔴 Гипо"
                elif sgv > 180:
                    status = "🟡 Гипер"

            info = (
                f"🩸 <b>Глюкоза:</b> <code>{sgv} {units}</code> {direction}\n"
                f"{status}\n"
                f"🕒 Время: <code>{time_str}</code> ({ago} мин назад)\n"
                f"📡 Устройство: <code>{device}</code>\n"
            )

            if raw:
                info += f"📊 Raw: <code>{raw}</code>\n"
            if noise is not None:
                info += f"🔧 Шум: <code>{noise}</code>\n"
            if delta:
                delta_conv = self._convert_units(delta)
                info += f"↕️ Delta: <code>{delta_conv} {units}</code>\n"

            await utils.answer(message, info)

        except Exception as e:
            await utils.answer(message, f"⚠️ Ошибка: {e}")
