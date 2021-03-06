# -*- coding:utf-8 -*-
"""
    @author: harvey
    @time: 2018/1/18 17:18
    @subject: 晋江文学城 http://www.jjwxc.net
"""

import sys
import json
import time
from collections import Counter
from datetime import datetime
import cPickle as pickle

from scrapy import Request, Selector, FormRequest
from scrapy_redis.spiders import RedisSpider

from htfspider.items import BookDetailItem

reload(sys)
sys.setdefaultencoding('utf-8')


class JjwxcDetialSpider(RedisSpider):
    name = 'jjwxc_detail'
    redis_key = 'jjwxc:detail'
    today = datetime.strptime(time.strftime('%Y-%m-%d'), '%Y-%m-%d')

    def make_request_from_data(self, data):
        data = pickle.loads(data)
        url = data.pop('data_url', None)
        if url:
            req = FormRequest(
                url,
                meta={'data': data},
                formdata={'versionCode': '75'},
                callback=self.parse,
                dont_filter=True
            )
            return req

    def parse(self, response):
        detail_json = json.loads(response.body)
        item = BookDetailItem()
        data = response.meta['data']
        if 'code' in detail_json:
            item['status'] = 0
            item['source_id'] = data['source_id']
            item['book_id'] = data['book_id']
            yield item
            return
        item.update(response.meta['data'])
        item['source_id'] = 7
        item['total_word'] = int(detail_json['novelSize'].replace(',', ''))
        item['total_click'] = int(detail_json['novip_clicks'].replace(',', ''))
        item['total_recommend'] = int(detail_json['novelbefavoritedcount'].replace(',', ''))
        item['total_comment'] = int(detail_json['comment_count'].replace(',', ''))
        item['total_ticket'] = -1
        if u'暂无排名' in detail_json['ranking']:
            item['ticket_rank'] = 0
        else:
            item['ticket_rank'] = int(detail_json['ranking'][1: -1].replace(',', ''))
        item['reward'] = -1
        item['total_score'] = -1.0
        item['total_scored_user'] = -1
        item['book_status'] = (2 == detail_json['novelStep']) * 1
        item['book_updated_at'] = datetime.strptime(detail_json['renewDate'], '%Y-%m-%d %H:%M:%S')
        item['updated_at'] = self.today
        item['fans'] = []
        fans_page = 1
        fans_url = 'http://www.jjwxc.net/reader_kingticket.php?novelid={0}&page={1}'.format(item['book_id'], fans_page)
        yield Request(
            url=fans_url,
            meta={'item': item, 'fans_page': fans_page, 'fans_level': []},
            callback=self.parse_fans,
            dont_filter=True
        )

    def parse_fans(self, response):
        fans_page = response.meta['fans_page']
        fans_level = response.meta['fans_level']
        item = response.meta['item']
        if u'暂无霸王票' in response.body.decode('gbk', 'ignore'):
            item['fans'] = []
            if fans_level:
                counter = Counter(fans_level)
                item['fans'] = [{'name': k, 'value': counter[k]} for k in counter]
            yield item
            return
        sel = Selector(text=response.body.decode('gbk', 'ignore'))
        fans_level.extend(sel.xpath('//*[@id="rank"]/div[2]/table/tr/td[2]/text()').extract())
        fans_page += 1
        if fans_page > 5:
            counter = Counter(fans_level)
            item['fans'] = [{'name': k, 'value': counter[k]} for k in counter]
            yield item
        else:
            yield Request(
                url='http://www.jjwxc.net/reader_kingticket.php?novelid={0}&page={1}'.format(
                    item['book_id'], fans_page),
                meta={'item': item, 'fans_page': fans_page, 'fans_level': fans_level},
                callback=self.parse_fans,
                dont_filter=True
            )
