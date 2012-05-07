# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2010, 2011, 2012 Participatory Culture Foundation
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

import markdown

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.defaultfilters import striptags
from django.template.loader import render_to_string

from mirocommunity_saas.models import SiteTierInfo


def send_mail(subject_template, body_template, users, from_email=None,
              extra_context=None, fail_silently=False):
    """
    Send mail to the given recipients by rendering the given templates.

    Default context for the templates is:

    * site: The current Site instance.
    * tier_info: The SiteTierInfo instance for the current site.
    * tier: The currently selected Tier.

    A dictionary containing additional context variables can be passed in as
    ``extra_context``. These will override the default context.

    The current user to be emailed will be added to the context as ``user``.

    The subject template should be a plaintext file; it will have any HTML
    tags stripped. The body template should be a markdown file; it will have
    HTML tags stripped, then be run through a markdown filter to generate an
    HTML version of the email.

    """
    tier_info = SiteTierInfo.objects.select_related('tier', 'site'
                                   ).get(site=settings.SITE_ID)
    c = {
        'tier_info': tier_info,
        'site': tier_info.site,
        'tier': tier_info.tier
    }
    c.update(extra_context or {})
    for user in users:
        if not user.email:
            continue
        c['user'] = user
        subject = striptags(render_to_string(subject_template, c))
        body = striptags(render_to_string(body_template, c))
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        msg = EmailMultiAlternatives(subject, body, from_email, [user.email])

        html_body = markdown.markdown(body, output_format="html5")
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=fail_silently)


def send_welcome_email():
    tier_info = SiteTierInfo.objects.get(site=settings.SITE_ID)
    if tier_info.welcome_email_sent:
        return
    send_mail('mirocommunity_saas/mail/welcome/subject.txt',
              'mirocommunity_saas/mail/welcome/body.txt',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True))
    tier_info.welcome_email_sent = True
    tier_info.save()
