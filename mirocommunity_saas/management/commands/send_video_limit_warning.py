from django.core.management.base import NoArgsCommand

from mirocommunity_saas.utils.mail import send_video_limit_warning


class Command(NoArgsCommand):
    """
    Command line interface for the send_video_limit_warning utility function.

    """
    def handle_noargs(self, **options):
        send_video_limit_warning()
