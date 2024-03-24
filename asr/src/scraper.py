from typing import List
from pathlib import Path
import requests
from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from icu_tokenizer import SentSplitter

class BibleScraper(Spider):
    name: str
    output_folder: str
    start_urls: List[str]
    splitter: SentSplitter

    def __init__(self,
                 output_folder: str,
                 start_urls: List[str],
                 splitter: SentSplitter,
                 *args, **kwargs):
        super(BibleScraper, self).__init__(*args, **kwargs)
        self.output_folder = output_folder
        self.start_urls = start_urls
        self.splitter = splitter

    def download_audio(self, audio_src, output_file):
        data = requests.get(audio_src)
        with open(output_file, 'wb') as out_mp3:
            out_mp3.write(data.content)
            return True, Path(output_file).stem

    def get_audio(self, audio_response, output_filename):
        audio = audio_response.css("audio")
        if "src" in audio.attrib:
            audio = audio.attrib["src"]
            self.download_audio(audio, f"{output_filename}.mp3")

    def parse(self, response):
        content_to_pass = {"ChapterContent_r___3KRx", "ChapterContent_label__R2PLt", "ChapterContent_note__YlDW0",
                           "ChapterContent_fr__0KsID", "ChapterContent_body__O3qjr", "ft", "w"}
        title = response.css("h1::text")
        title = title.get()
        book, chapter, code = response.url.split("/")[-1].split(".")[-3:]

        output_folder = Path(f"{self.output_folder}/raw/{self.name}")
        output_folder.mkdir(exist_ok=True, parents=True)
        output_filename = output_folder / f"{book}_{chapter}_{code}"

        with open(f"{output_folder}/{code}.books", "a+") as titles:
            titles.write(f"{book}\t{chapter}\t{title}\n")
        audio_url = "audio-bible".join(response.url.rsplit("bible", 1))
        yield Request(audio_url, cb_kwargs={"output_filename": output_filename}, callback=self.get_audio)
        with open(f"{output_filename}.txt", "w") as output_file:
            output_file.write(f"{title}\n")
            for content in response.css("div.ChapterContent_chapter__uvbXo div"):
                if content.attrib["class"] in content_to_pass:
                    continue
                verses = []
                for span in content.css("span.ChapterContent_content__RrUqA, span.ChapterContent_heading__xBDcs"):
                    if span.attrib["class"] in content_to_pass:
                        continue
                    for verse in span.css("*::text").getall():
                        verses.append(verse.strip())
                text = " ".join(verses).strip()
                text = text.strip()
                if not text:
                    continue
                for sent in self.splitter.split(text):
                    output_file.write(f"{sent}\n")
        next_page = response.css("div.\[pointer-events\:all\]:nth-child(2) > a:nth-child(1)")
        if next_page:
            yield Request(url=f"https://www.bible.com{next_page.attrib['href']}")

if __name__ == "__main__":
    process = CrawlerProcess()
    process.crawl(BibleScraper,
                  name="SeereerBible",
                  output_folder="SeereerBible",
                  start_urls=["https://www.bible.com/bible/3751/GEN.1.SRR23"],
                  splitter=SentSplitter())
    process.start()