import lxml.html

from datetime import datetime

from aiohttp import get, ClientError

from . import exceptions
from . import models


async def fetch_page(session, site):
    # TODO: If-Modified-Since: page.ctime
    # TODO: User-Agent

    try:
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
    except ClientError as e:
        raise exceptions.TaskFailure('http error: {!r}'.format(e))

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

    current_links = set(link.href for link in site.links)
    links = list(extract_links(new_page, site.css_selector))
    new_links = []

    if not links:
        raise exceptions.TaskFailure('no link found. check your css_selector.')

    for title, href in links:
        if href not in current_links:
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

        set_text_for_imgs(dom)

        title = dom.text_content().strip()
        href = dom.attrib['href']

        yield (title, href)


# XXX: doesn't lxml have the way to do that itself?
def set_text_for_imgs(dom):
    '''set text for img tags within the dom

    If img tag has title or alt attribute, use it as a text content.
    This function modify the dom object.
    '''
    for img in dom.cssselect('img'):
        if not img.text_content().strip():
            if img.get('title'):
                img.text = img.get('title')
            elif img.get('alt'):
                img.text = img.get('alt')
