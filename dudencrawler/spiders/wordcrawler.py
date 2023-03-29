import logging

import scrapy
from scrapy.linkextractors import LinkExtractor
import string
from regex import search

def remove_formatting(text):
    removal_list = ['\u00AD', '\u00A0']
    if text is None:
        return None
    for removable_str in removal_list:
        text = text.replace(removable_str, '')
    return text

def get_synonyms(response):
    synonym_cluster = response.selector.css('div.xerox')
    indexed_synonyms = synonym_cluster.css('a::text').getall()
    not_indexed_synonyms = synonym_cluster.css('span.xerox__clicker::text').getall()
    return indexed_synonyms+not_indexed_synonyms


class WordcrawlerSpider(scrapy.spiders.CrawlSpider):
    name = "wordcrawler"
    allowed_domains = ["duden.de"]

    base_url = 'https://www.duden.de'

    # populate start website
    def start_requests(self):
        logging.getLogger('scrapy').setLevel(logging.WARNING)

        lexeme_base_url = 'https://www.duden.de/sitemap-lexeme/{}'
        #start_urls = [lexeme_base_url.format(letter) for letter in string.ascii_lowercase]
        start_urls = ['https://www.duden.de/sitemap-lexeme/a']
        for url in start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        links = LinkExtractor(restrict_css='tr.index__entry').extract_links(response)
        for link in links:
            yield response.follow(url=link.url, callback=self.parse_word)
        next_page = response.selector.css('a[rel="next"].pager__item::attr(href)').get()
        pattern = r'(https:\/\/www\.duden\.de\/sitemap-lexeme\/\w)'
        match = search(pattern=pattern, string=response.url)
        if next_page is not None and match is not None:
            yield response.follow(url='{}{}'.format(match.group(1), next_page), callback=self.parse)
        pass

    def parse_word(self, response):
        lemma_main = response.selector.css('span.lemma__main::text').get()
        lemma_delimiter = response.selector.css('span.lemma__determiner::text').get()
        frequency_full = response.selector.css('span.shaft__full::text').get()

        # get wordtype
        tuple_keys = response.selector.css('dt.tuple__key::text').getall()
        tuple_values = response.selector.css('dd.tuple__val::text').getall()
        word_type = None
        if 'Wortart: ' in tuple_keys:
            word_type_index = tuple_keys.index('Wortart: ')
            word_type = tuple_values[word_type_index] if word_type_index < len(tuple_values) and tuple_keys and tuple_values else None
        data_dict = {
                'dict_url': response.url,
                'lemma_main': remove_formatting(lemma_main),
                'lemma_delimiter': remove_formatting(lemma_delimiter),
                'word_type': word_type,
                'frequency': len(frequency_full) if frequency_full is not None else -1,
                'synonyms': []
        }

        # test for synonym website
        synonym_url = response.selector.css('a[id="synonyme"]').css('a::attr(href)').get()
        if synonym_url is not None:
            yield response.follow(url='{}{}'.format(self.base_url, synonym_url), callback=self.parse_synonyms, meta={'data_dict': data_dict})
        else:
            # try finding word cluster on current word website
            data_dict.update({'synonyms': get_synonyms(response)})
            yield data_dict


    def parse_synonyms(self, response):
        data_dict = response.meta['data_dict']
        synonyms = {'synonyms': get_synonyms(response), 'synonym_page_url': response.url}
        data_dict.update(synonyms)
        yield data_dict