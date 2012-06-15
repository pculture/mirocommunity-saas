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

import datetime
from optparse import make_option
import urllib

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand
from localtv.models import SiteSettings
from localtv.tasks import CELERY_USING

from mirocommunity_saas.admin.forms import PayPalSubscriptionForm
from mirocommunity_saas.models import Tier, SiteTierInfo
from mirocommunity_saas.tasks import welcome_email_task
from mirocommunity_saas.utils.mail import send_welcome_email


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--username'),
        make_option('--email'),
        make_option('--password'),
        make_option('--tier', default='basic', type='choice',
                    choices=['basic', 'plus', 'premium', 'max']),
    )
    help = ("Initializes the database objects for the site, sends the site's "
            "welcome email, and prints a url to stdout which the site owner "
            "should be redirected to in order to complete registration.")

    def handle(self, site_name, domain, **options):
        call_command('loaddata',
                     'tiers.json')
        available_tiers = Tier.objects.filter(slug__in=('basic',
                                                        'plus',
                                                        'premium',
                                                        'max'))
        tier = available_tiers.get(slug=options['tier'])
        site = Site.objects.get_current()
        # Make sure this site hasn't already been set up.
        try:
            SiteTierInfo.objects.get(site=site)
        except SiteTierInfo.DoesNotExist:
            tier_info = SiteTierInfo.objects.create(
                                site=site,
                                tier=tier,
                                tier_changed=datetime.datetime.now(),
                                enforce_payments=True,
                                site_name=site_name)
            tier_info.available_tiers = available_tiers
        else:
            self.stderr.write('Site already initialized.\n')
            return
        site.name = site_name
        site.domain = domain
        site.save()

        SiteSettings.objects.get_or_create(site=site)

        if options['username']:
            user = User.objects.create_user(options['username'],
                                            options['email'],
                                            options['password'])
            user.is_superuser = True
            user.save()

        if tier.slug == 'basic':
            send_welcome_email()
            self.stdout.write('http://{0}/'.format(site.domain))
        else:
            # Send the welcome email in ~30 minutes if they haven't gotten
            # back from paypal by then.
            welcome_email_task.apply_async(countdown=30*60,
                                           kwargs={'using': CELERY_USING})
            form = PayPalSubscriptionForm(tier)
            data = form.initial

            # Here we make use of the fact that paypal subscriptions can use
            # GET as well as POST. A bit hackish.
            self.stdout.write("{0}?{1}".format(form.action,
                                               urllib.urlencode(data)))
