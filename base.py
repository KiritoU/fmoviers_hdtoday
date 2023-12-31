import json
import logging
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from hdtoday import HDToday
from helper import helper
from settings import CONFIG

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)
Path(CONFIG.COVER_SAVE_PATH).mkdir(parents=True, exist_ok=True)


class Crawler:
    def crawl_soup(self, url):
        logging.info(f"Crawling {url}")

        html = helper.download_url(url)
        soup = BeautifulSoup(html.content, "html.parser")

        return soup

    def get_episode_link(self, href) -> str:
        soup = self.crawl_soup(href)
        playerMovie = soup.find("div", {"id": "playerMovie"})
        src = playerMovie.find("iframe").get("src")
        return src

    def get_server_episodes_links(self, href, server_data_id) -> dict:
        res = {}
        soup = self.crawl_soup(href)
        list_episodes = soup.find("ul", class_="list-episodes")
        lis = list_episodes.find_all("li", class_="episode-item")
        for li in lis:
            episode_name = li.text.strip()
            episode_href = li.find("a").get("href")

            if not f"&server={int(server_data_id) + 1}" in episode_href:
                matches = re.search(r"&server=(\d+)&", episode_href)
                if matches:
                    episode_href = episode_href.replace(
                        matches.group(0), f"&server={int(server_data_id) + 1}&"
                    )
                # episode_href = episode_href.replace(
                #     f"&server={server_data_id}", f"&server={int(server_data_id) + 1}"
                # )
            episode_link = self.get_episode_link(href=episode_href)
            res[episode_name] = episode_link
        return res

    def get_episodes_data(
        self, href: str, post_type: str = CONFIG.TYPE_TV_SHOWS
    ) -> dict:
        soup = self.crawl_soup(href)
        res = {}

        try:
            if post_type == CONFIG.TYPE_TV_SHOWS:
                servers_list = soup.find("ul", {"id": "servers-list"})
                lis = servers_list.find_all("li")
                for li in lis:
                    a_element = li.find("a")
                    data_id = a_element.get("data-id")
                    server_href = a_element.get("href")
                    server_name = (
                        a_element.text.lower()
                        .replace("server", "")
                        .strip()
                        .capitalize()
                    )
                    res[data_id] = {
                        "name": server_name,
                        "episodes": self.get_server_episodes_links(
                            href=server_href, server_data_id=data_id
                        ),
                    }
            else:
                list_episodes = soup.find("ul", class_="list-episodes")
                lis = list_episodes.find_all("li", class_="episode-item")
                for li in lis:
                    server_name = (
                        li.text.lower().replace("server", "").strip().capitalize()
                    )
                    episode_link = self.get_episode_link(href=li.find("a").get("href"))
                    data_id = li.find("a").get("data-id")
                    res[data_id] = {
                        "name": server_name,
                        "episodes": {"movie_episode": episode_link},
                    }

        except Exception as e:
            helper.error_log(
                f"Failed to get_episodes_data. Href: {href}",
                log_file="base.episodes.log",
            )

        return res

    def crawl_film(
        self,
        slug: str,
        href: str,
        post_type: str = CONFIG.TYPE_TV_SHOWS,
    ):
        soup = self.crawl_soup(href)
        detail_page_infor = soup.find("div", class_="detail_page-infor")

        title = helper.get_title(href=href, detail_page_infor=detail_page_infor)
        description = helper.get_description(
            href=href, detail_page_infor=detail_page_infor
        )

        cover_src = helper.get_cover_url(href=href, detail_page_infor=detail_page_infor)

        trailer_id = helper.get_trailer_id(soup)

        servers_link = helper.get_servers_link(soup)

        extra_info = helper.get_extra_info(detail_page_infor=detail_page_infor)

        if not title:
            helper.error_log(
                msg=f"No title was found. Href: {href}", log_file="base.no_title.log"
            )
            return

        film_data = {
            "title": title,
            "slug": slug,
            "description": description,
            "post_type": post_type,
            "trailer_id": trailer_id,
            "cover_src": cover_src,
            "servers_link": servers_link,
            "extra_info": extra_info,
        }

        episodes_data = []

        return film_data, episodes_data

    def crawl_ml_item(
        self, flw_item: BeautifulSoup, post_type: str = CONFIG.TYPE_TV_SHOWS
    ):
        try:
            href = flw_item.find("a").get("href")

            if not href.startswith("https://"):
                href = CONFIG.FMOVIERS_HOMEPAGE + href

            slug = href.strip("/").split("/")[-1]

            film_data, episodes_data = self.crawl_film(
                slug=slug,
                href=href,
                post_type=post_type,
            )

            film_data["episodes_data"] = episodes_data

            # with open("json/crawled.json", "w") as f:
            #     f.write(json.dumps(film_data, indent=4, ensure_ascii=False))

            HDToday(film=film_data, episodes=episodes_data).insert_film()
            # sys.exit(0)

        except Exception as e:
            helper.error_log(
                msg=f"Error crawl_flw_item\n{e}", log_file="base.crawl_flw_item.log"
            )

    def crawl_page(self, url, post_type: str = CONFIG.TYPE_TV_SHOWS):
        soup = self.crawl_soup(url)

        flw_items = soup.find_all("div", class_="flw-item")
        if not flw_items:
            return 0

        for flw_item in flw_items:
            self.crawl_ml_item(flw_item=flw_item, post_type=post_type)
            # break

        return 1


if __name__ == "__main__":
    Crawler().crawl_page(url=CONFIG.FMOVIERS_TVSHOWS_PAGE + "/page/2/")
    Crawler().crawl_page(
        url=CONFIG.FMOVIERS_MOVIES_PAGE + "/page/1/", post_type=CONFIG.TYPE_MOVIE
    )
    # Crawler().crawl_page(url=CONFIG.TINYZONETV_MOVIES_PAGE, post_type=CONFIG.TYPE_MOVIE)
