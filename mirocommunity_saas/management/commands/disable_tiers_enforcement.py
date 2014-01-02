from django.core.management.base import NoArgsCommand

from mirocommunity_saas.models import SiteTierInfo


class Command(NoArgsCommand):
    """
    Command line interface for the send_winddown_email utility function.

    """
    def handle_noargs(self, **options):
        SiteTierInfo.objects.all().update(enforce_payments=False)
