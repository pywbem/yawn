#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
        name = "yawn",
        version = "0.1.4",
        packages = find_packages(),
        package_data = { 'pywbem_yawn' :
            ['templates/*.mako', 'templates/*.txt'
            , 'static/*.css', 'static/*.js'] },
        scripts = ['scripts/yawn.py'],
        author = "Michal Minar",
        author_email = "miminar@redhat.com",
        license = "GPL",
        description = "Yet Another WBEM Navigator for Apache's mod_wsgi",
        install_requires=['distribute', 'werkzeug', 'mako']
)
