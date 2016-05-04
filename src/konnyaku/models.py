import json

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class Site(Base):
    __tablename__ = 'site'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    url = Column(String)
    css_selector = Column(String)
    # optional HTTP request headers
    headers_json = Column(String, default='{}')
    #last_checked = Column(DateTime)

    def __repr__(self):
        return u'<Site(id={id}, name={name!r}, url={url!r}, css_selector={css_selector!r}, headers={headers_json!r})>'.format(**vars(self))

    @property
    def headers(self):
        return json.loads(self.headers_json)

    @headers.setter
    def headers(self, headers):
        self.headers_json = json.dumps(headers)


class Page(Base):
    __tablename__ = 'page'

    id = Column(Integer, primary_key=True)

    site_id = Column(Integer, ForeignKey('site.id', ondelete='CASCADE'))
    site = relationship('Site', back_populates='pages')

    # XXX: site.url が redirect 返した場合とか、必ずしも page の URL と一致するとは限らないので、
    #      一応こちらにも url 持たせるけど、不要かもしれない。
    url = Column(String)

    # XXX: text じゃなくて bytes なのかも？
    body = Column(Text)
    ctime = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return u'<Page(id={id}, site={site!r}, ctime={ctime!r})>'.format(
            id=self.id, site=self.site, ctime=self.ctime)

Site.pages = relationship('Page', order_by=Page.ctime, back_populates='site')


class Link(Base):
    __tablename__ = 'link'

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey('site.id', ondelete='CASCADE'))
    site = relationship('Site', back_populates='links')

    title = Column(String)
    href = Column(String)

    ctime = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return u'<Link(id={id}, site={site!r}, title={title!r}, href={href!r})>'.format(
            id=self.id, site=self.site, title=self.title, href=self.href)

Site.links = relationship('Link', order_by=Link.id, back_populates='site')


def make_engine(*args, **kwargs):
    if not args:
        args = ('sqlite:///:memory:', )

    from sqlalchemy import create_engine
    engine = create_engine(*args, **kwargs)

    if engine.name == 'sqlite':
        from sqlalchemy import event

        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        event.listen(engine, 'connect', set_sqlite_pragma)

    Base.metadata.create_all(engine)

    return engine


def make_session(engine):
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)

    return Session


def get_default_url():
    import os
    import xdg.BaseDirectory

    data_dir = xdg.BaseDirectory.save_data_path('konnyaku')
    db_path = os.path.join(data_dir, 'db.sqlite')

    return 'sqlite:///' + db_path
