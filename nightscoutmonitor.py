# meta developer: @mypchikov
# requires: matplotlib

from .. import loader, utils
import aiohttp
from datetime import datetime
import matplotlib.pyplot as plt
import os
import io

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
                "mg/dL",  # или mmol/L
                doc="Формат глюкозы: mg/dL или mmol/L"
            ),
            loader.ConfigValue(
                "show_graph",
                True,
                doc="Показывать график глюкозы (True/False)"
            )
        )

    async def _fetch_data(self, count=1):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.config['nightscout_url'].rstrip('/')}/api/v1/entries.json?count={count}") as resp:
                if resp.status != 200:
                    raise Exception(f"Ошибка запроса: {resp.status}")
                return await resp.json()

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

    def _draw_graph(self, entries):
        times = [datetime.fromtimestamp(e["date"] / 1000) for e in entries]
        values = [self._convert_units(e["sgv"]) for e in entries]

        plt.figure(figsize=(8, 4))
        ax = plt.gca()

        # Основной график
        ax.plot(times, values, marker='o', linestyle='-', color='blue')

        # Настройки Y-оси
        if self.config["units"].lower() == "mmol/l":
            ymin, ymax = 2.2, 22.2
            norm_low, norm_high = 4, 9
        else:
            ymin, ymax = 40, 400
            norm_low, norm_high = 70, 160

        ax.set_ylim(ymin, ymax)
        ax.set_ylabel(self._format_units())

        # Подсветка безопасной зоны
        ax.axhspan(norm_low, norm_high, facecolor='green', alpha=0.1)

        # Пунктирные границы нормы
        ax.axhline(norm_low, color='red', linestyle='--', linewidth=1)
        ax.axhline(norm_high, color='orange', linestyle='--', linewidth=1)

        ax.grid(True, which='major', linestyle='--', alpha=0.3)
        ax.set_title("Глюкоза за последние измерения")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)
        return buf

    @loader.command()
    async def glucose(self, message):
        """Получить текущее значение глюкозы с графиком (если включено)"""
        try:
            data = await self._fetch_data(12)
            if not data:
                await utils.answer(message, "❌ Нет данных от сервера.")
                return

            entry = data[0]
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

            if self.config["show_graph"]:
                buf = self._draw_graph(data)
                await message.client.send_file(message.chat_id, buf, caption=info, reply_to=message.id)
            else:
                await utils.answer(message, info)

        except Exception as e:
            await utils.answer(message, f"⚠️ Ошибка: {e}")
