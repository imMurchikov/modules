# meta developer: @mypchikov
# requires: matplotlib

from .. import loader, utils
import aiohttp
from datetime import datetime
import matplotlib.pyplot as plt
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

    async def _fetch_data(self, count=12):
        async with aiohttp.ClientSession() as session:
            url = f"{self.config['nightscout_url'].rstrip('/')}/api/v1/entries.json?count={count}"
            async with session.get(url) as resp:
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

        fig, ax = plt.subplots(figsize=(8, 4))

        if self.config["units"].lower() == "mmol/l":
            ymin, ymax = 2.2, 22.2
            norm_low, norm_high = 4, 9
        else:
            ymin, ymax = 40, 400
            norm_low, norm_high = 70, 160

        ax.axhspan(norm_low, norm_high, facecolor='green', alpha=0.1)
        ax.axhline(norm_low, color='red', linestyle='--', linewidth=1)
        ax.axhline(norm_high, color='orange', linestyle='--', linewidth=1)
        ax.set_ylim(ymin, ymax)
        ax.set_ylabel(self._format_units())

        for i in range(1, len(times)):
            t1, t2 = times[i - 1], times[i]
            v1, v2 = values[i - 1], values[i]
            if norm_low <= v1 <= norm_high and norm_low <= v2 <= norm_high:
                color = 'black'
            elif v1 < norm_low or v2 < norm_low:
                color = 'red'
            else:
                color = 'orange'
            ax.plot([t1, t2], [v1, v2], color=color, linewidth=2)

        ax.scatter(times, values, color='blue', s=6)
        ax.set_title("Глюкоза за последние измерения")
        ax.grid(True, which='major', linestyle='--', alpha=0.3)
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
            # Удаляем командное сообщение
            await message.delete()

            data = await self._fetch_data(12)
            if not data:
                return  # message удалено, дополнительный ответ не нужен

            entry = data[0]
            sgv = self._convert_units(entry["sgv"])
            units = self._format_units()
            direction = self._trend_emoji(entry.get("direction", ""))
            device = entry.get("device", "неизвестно")
            date = datetime.fromtimestamp(entry["date"] / 1000)
            time_str = date.strftime('%H:%M:%S')
            ago = (datetime.now() - date).seconds // 60

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
                f"📡 Устройство: <code>{device}</code>"
            )

            if self.config["show_graph"]:
                buf = self._draw_graph(data)
                await message.client.send_file(message.chat_id, buf, caption=info)
            else:
                await utils.answer(message, info)

        except Exception as e:
            await utils.answer(message, f"⚠️ Ошибка: {e}")