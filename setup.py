from setuptools import setup, find_packages


setup(
    name='konnyaku',
    version='0.0.1',
    description='websites update checker',
    author='NAKAMURA Yoshitaka',
    author_email='arumakanoy@gmail.com',
    licence='BSD-2',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'konnyaku = konnyaku.cli:cli',
        ],
    },
    install_requires=[
        'aiohttp',
        'click',
        'cssselect',
        'lxml',
        'pyxdg',
        'sqlalchemy',
    ],
)
