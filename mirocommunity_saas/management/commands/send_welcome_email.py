# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2011, 2012 Participatory Culture Foundation
# 
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

from django.core.management.base import BaseCommand

from mirocommunity_saas import tiers, models

class Command(BaseCommand):

    def handle(self, *args, **options):
        # We send this email to the person who owns the site. So we use
        # the tiers system's ability to send email.
        tier_info = models.TierInfo.objects.get_current()
        if tier_info.already_sent_welcome_email:
            return
        if 'temporarily_override_payment_due_date' in options:
            extra_context = {'next_payment_due_date': options['temporarily_override_payment_due_date'].strftime('%B %e, %Y'),
                             'in_free_trial': True}
        else:
            extra_context = {}
        self.actually_send(tier_info, extra_context)

    def actually_send(self, tier_info, extra_context):

        # If we haven't sent it, prepare the email

        # Now send the sucker
        subject = "%s: Welcome to Miro Community" % tier_info.site_settings.site.name
        if tier_info.tier_name == 'basic':
            template = 'mirocommunity_saas/tiers_emails/welcome_to_your_site_basic.txt'
        else:
            template = 'mirocommunity_saas/tiers_emails/welcome_to_your_site.txt'
        tiers.send_tiers_related_multipart_email(subject, template, tier_info, extra_context=extra_context)

        # Finally, save a note saying we sent it.
        tier_info.already_sent_welcome_email = True
        tier_info.save()
