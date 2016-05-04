import lxml.html

from datetime import datetime

from aiohttp import get

from . import exceptions
from . import models


async def fetch_page(session, site):
    # TODO: If-Modified-Since: page.ctime
    # TODO: User-Agent

    async with await get(site.url, headers=site.headers) as response:
        # TODO: don't hardcode response size limit
        if response.content.total_bytes > 10 * 1024 * 1024:
            raise exceptions.TaskFailure('content-size too big')

        if response.status != 200:
            raise exceptions.TaskFailure('http error: {!r}'.format(response))

        #body = await response.read()
        # .text() メソッドを使うと、 chardet で自動で文字コード判定してくれるらしい。
        # XXX: HTTP header や html header 見て charset 探したほうが良いかも？
        body = await response.text()

    # XXX: encoding 判定
    #body = body.decode('utf-8')

    # XXX: これだと、 page 数分全部リストに持ってるっぽいし、
    #      取得履歴が増えていった時に破滅しそう。
    if site.pages:
        last_page = site.pages[-1]
        if last_page.url == response.url and body == site.pages[-1].body:
            return None

    # save Last-Modified for If-Modified-Since
    page = models.Page(
        site=site, url=response.url, body=body, ctime=datetime.now())
    session.add(page)

    return page


async def check_update(session, site):
    new_page = await fetch_page(session, site)

    if not new_page:
        return []

    current_links = set((link.title, link.href) for link in site.links)
    links = list(extract_links(new_page, site.css_selector))
    new_links = []

    if not links:
        raise exceptions.TaskFailure('no link found. check your css_selector.')

    for title, href in links:
        if (title, href) not in current_links:
            link = models.Link(site=site, title=title, href=href)
            session.add(link)
            new_links.append(link)

    return new_links


def extract_links(page, css_selector):
    doc = lxml.html.fromstring(page.body, base_url=page.url)
    doc.make_links_absolute()

    link_doms = doc.cssselect(css_selector)

    for dom in link_doms:
        if dom.tag != 'a':
            # TODO: warning log
            continue

        title = dom.text_content().strip()
        href = dom.attrib['href']

        yield (title, href)
