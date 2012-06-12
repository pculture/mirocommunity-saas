import random

from boto.s3.connection import OrdinaryCallingFormat


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
