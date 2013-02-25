from django.core.management.base import NoArgsCommand

from mirocommunity_saas.utils.mail import send_free_trial_ending


class Command(NoArgsCommand):
    """
    Command line interface for the send_welcome_email utility function.

    """
    def handle_noargs(self, **options):
        send_free_trial_ending()
