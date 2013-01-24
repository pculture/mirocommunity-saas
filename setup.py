from setuptools import setup, find_packages

__version__ = __import__('mirocommunity_saas').__version__

description = ("Public Miro Community files specific to the service PCF "
               "provides.")

setup(name='mirocommunity-saas',
      version='.'.join([str(v) for v in __version__]),
      description=description,
      long_description=description,
      author='Participatory Culture Foundation',
      author_email='dev@mirocommunity.org',
      url='http://www.mirocommunity.org/',
      packages=find_packages(),
      include_package_data=True,
      classifiers=[
          'Environment :: Web Environment',
          'Framework :: Django',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: GNU Affero General Public License v3',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Multimedia :: Sound/Audio',
          'Topic :: Multimedia :: Video',
      ],
      platforms=['OS Independent'],)
