from __future__ import absolute_import
import random

from boto.s3.connection import OrdinaryCallingFormat
from storages.backends.s3boto import S3BotoStorage


class MultiCallingFormat(OrdinaryCallingFormat):
    """
    Calling formats generate URLs; by using multiple calling formats, it's
    possible to get browsers to download with higher concurrency.

    """
    def __init__(self, formats):
        self.formats = formats

    def build_url_base(self, connection, protocol, server, bucket, key=''):
        format = random.choice(self.formats)
        return format.build_url_base(connection, protocol, server, bucket,
                                     key)


class StaticBotoStorage(S3BotoStorage):
    """
    By default, uses 'static' as the location for this storage's instances.

    """
    def __init__(self, **kwargs):
        if 'location' not in kwargs:
            kwargs['location'] = 'static'
        super(StaticBotoStorage, self).__init__(**kwargs)


class CompressedBotoStorage(S3BotoStorage):
    """
    Adds 'compressed' to the location for this storage's instances.

    """
    def __init__(self, *args, **kwargs):
        super(CompressedBotoStorage, self).__init__(*args, **kwargs)
        self.location = '/'.join((self.location, 'compressed'))
