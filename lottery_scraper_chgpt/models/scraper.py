
import requests
from bs4 import BeautifulSoup
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

URL = "https://floridalottery.com/es/games/draw-games/pick-3"

class LotteryScraper(models.Model):
    _name = "lottery.scraper.simple"
    _description = "Scraper simple sin Selenium"

    @api.model
    def run_scraper(self):
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(URL, headers=headers, timeout=30)

        if res.status_code != 200:
            raise Exception("Error cargando página")

        soup = BeautifulSoup(res.text, "html.parser")

        draws = []
        for container in soup.select(".game-numbers--pick3"):
            nums = [li.text.strip() for li in container.find_all("li") if li.text.strip().isdigit()]
            if len(nums) >= 3:
                draws.append(nums[:3])

        _logger.info("Resultados: %s", draws)
        return draws
