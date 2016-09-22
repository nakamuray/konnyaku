import asyncio

import click

from . import exceptions
from . import models
from . import tasks


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    url = models.get_default_url()

    engine = models.make_engine(url, echo=debug)
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
@click.pass_context
def check(ctx, site_id):
    '''check site updates
    '''
    session = ctx.obj['session']

    loop = asyncio.get_event_loop()

    sites = session.query(models.Site)

    if site_id:
        sites = sites.filter_by(id=site_id)

    tasks = [_check_and_print_site_update(session, site) for site in sites]
    loop.run_until_complete(asyncio.gather(*tasks))
    session.commit()


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

if __name__ == '__main__':
    cli()
