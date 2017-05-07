import asyncio
import logging
import sys
import urllib.parse

import click

from . import exceptions
from . import models
from . import tasks
from .concurrentutils import throttling_per


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.option('--db-debug/--no-db-debug', default=False)
@click.pass_context
def cli(ctx, debug, db_debug):
    if debug:
        # TODO: apply these settings for konnyaku.* logger only
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelno)s %(name)s:'
            ' %(module)s:%(lineno)d:%(funcName)s %(message)s'
        ))
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.DEBUG)

    url = models.get_default_url()

    engine = models.make_engine(url, echo=db_debug)
    Session = models.make_session(engine)
    ctx.obj = {'session': Session()}


@cli.command()
@click.option('--verbose/--quiet', default=False)
@click.pass_context
def list(ctx, verbose):
    '''list sites
    '''
    session = ctx.obj['session']

    sites = session.query(models.Site).all()

    for site in sites:
        _print_site(site, verbose)

        if verbose:
            click.echo()


@cli.command()
@click.argument('site-id')
@click.pass_context
def show(ctx, site_id):
    '''show site information
    '''
    session = ctx.obj['session']

    site = session.query(models.Site).get(site_id)

    if not site:
        raise click.UsageError('no site found')

    _print_site(site, verbose=True)


@cli.command()
@click.option('--site-id', help='site id to list links')
@click.pass_context
def links(ctx, site_id):
    '''list links
    '''
    session = ctx.obj['session']

    sites = session.query(models.Site)

    if site_id:
        sites = sites.filter_by(id=site_id)

    for site in sites:
        _print_links(site, site.links)


@cli.command()
@click.argument('name')
@click.argument('url')
@click.argument('css-selector')
@click.option('--header', type=(str, str), multiple=True,
              help='optional headers')
@click.pass_context
def add(ctx, name, url, css_selector, header):
    '''add site
    '''
    session = ctx.obj['session']

    site = models.Site(
        name=name, url=url, css_selector=css_selector, headers=dict(header))
    session.add(site)
    session.commit()


@cli.command()
@click.argument('site-id')
@click.option('--name')
@click.option('--url')
@click.option('--css-selector')
@click.option('--header', type=(str, str), multiple=True)
@click.pass_context
def modify(ctx, site_id, name, url, css_selector, header):
    '''modify site
    '''
    session = ctx.obj['session']

    site = session.query(models.Site).get(site_id)

    if not site:
        raise click.UsageError('no site found')

    if name:
        site.name = name

    if url:
        site.url = url

    if css_selector:
        site.css_selector = css_selector

    if header:
        site.headers = dict(header)

    session.commit()


@cli.command()
@click.argument('site-id')
@click.pass_context
def remove(ctx, site_id):
    '''remove site
    '''
    session = ctx.obj['session']

    session.query(models.Site).filter_by(id=site_id).delete()

    session.commit()


@cli.command()
@click.option('--site-id', help='site name to check')
@click.option('--concurrency', type=int, default=2,
              help='concurrency for fetching site')
@click.option('--wait', type=int, default=1,
              help='wait between fetching site within each concurrency')
@click.pass_context
def check(ctx, site_id, concurrency, wait):
    '''check site updates
    '''
    session = ctx.obj['session']

    loop = asyncio.get_event_loop()

    sites = session.query(models.Site)

    if site_id:
        sites = sites.filter_by(id=site_id)

    throttled_check_and_print_site_update = \
        throttling_per(wait, concurrency, _per_domain)(
            _check_and_print_site_update)
    tasks = [throttled_check_and_print_site_update(session, site)
             for site in sites]

    if sys.stderr.isatty():
        # run tasks while showing progress message
        pending = tasks
        num_tasks = len(tasks)
        num_done = 0

        while pending:
            click.echo('checking ... [{}/{}]\r'.format(num_done, num_tasks),
                       nl=False, err=True)
            done, pending = loop.run_until_complete(
                asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED))
            num_done += len(done)

        click.echo('checking ... [{}/{}]\r'.format(num_done, num_tasks),
                   err=True)

    else:
        # just run tasks
        loop.run_until_complete(asyncio.wait(tasks))

    session.commit()


def _per_domain(_, site):
    return urllib.parse.urlparse(site.url).hostname


async def _check_and_print_site_update(session, site):
    try:
        new_links = await tasks.check_update(session, site)
        if new_links:
            _print_links(site, new_links)
    except exceptions.TaskFailure as e:
        click.echo('error on {0}: {1}'.format(site.id, site.name), err=True)
        click.echo(e.args[0], err=True)


def _print_links(site, links):
    click.echo('=' * 78)
    click.echo(site.name)
    click.echo()

    for link in links:
        click.echo('{}:'.format(link.title))
        click.echo('  {}'.format(link.href))


def _print_site(site, verbose=False):
    click.echo('{0}: {1}'.format(site.id, site.name))

    if verbose:
        click.echo('url: {0}'.format(site.url))
        click.echo('css_selector: {0}'.format(site.css_selector))
        click.echo('headers: {0}'.format(site.headers_json))


@cli.command()
@click.argument('name')
@click.argument('url')
@click.argument('css-selector')
@click.option('--header', type=(str, str), multiple=True,
              help='optional headers')
@click.pass_context
def oneshot(ctx, name, url, css_selector, header):
    '''add & check but not save
    '''
    session = ctx.obj['session']

    site = models.Site(
        name=name, url=url, css_selector=css_selector, headers=dict(header))
    session.add(site)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_check_and_print_site_update(session, site))

    session.rollback()


if __name__ == '__main__':
    cli()
