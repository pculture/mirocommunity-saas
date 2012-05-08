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

import datetime
import markdown

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.defaultfilters import striptags
from django.template.loader import render_to_string
from localtv.models import Video

from mirocommunity_saas.models import SiteTierInfo


#: The minimum number of days between video limit warnings.
VIDEO_LIMIT_MIN_DAYS = 5
#: The minimum ratio of videos which must be used before a warning is sent
#: to the site owners.
VIDEO_LIMIT_MIN_RATIO = .66
#: The minimum change to the remaining number of videos, as a ratio. For
#: example, a value of .5 would mean that half of the remaining videos must
#: be used up before a new warning will be sent.
VIDEO_LIMIT_MIN_CHANGE_RATIO = .5
#: Number of days before the end of the free trial to warn the site's owners.
FREE_TRIAL_WARNING_DAYS = 5


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
              'mirocommunity_saas/mail/welcome/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True))
    tier_info.welcome_email_sent = datetime.datetime.now()
    tier_info.save()


def send_video_limit_warning():
    tier_info = SiteTierInfo.objects.get(site=settings.SITE_ID
                                   ).select_related('tier')

    # Don't send an email if there is no limit.
    if tier_info.tier.video_limit is None:
        return

    # Don't send an email if one was sent recently.
    resend = datetime.timedelta(VIDEO_LIMIT_MIN_DAYS)
    last_sent = tier_info.video_limit_warning_sent
    if last_sent is not None and datetime.datetime.now() - last_sent < resend:
        return

    # Don't send an email if the ratio of used videos is too low.
    video_limit = tier_info.tier.video_limit
    video_count = Video.objects.filter(status=Video.ACTIVE,
                                       site=settings.SITE_ID).count()
    ratio = float(video_count) / video_limit
    if ratio < VIDEO_LIMIT_MIN_RATIO:
        return

    # Don't send an email if the ratio hasn't changed noticeably since the
    # last email was sent.
    old_video_count = tier_info.video_count_when_warned
    if old_video_count is not None:
        old_ratio = float(old_video_count) / video_limit
        ratio_change = VIDEO_LIMIT_MIN_CHANGE_RATIO * (1 - old_ratio)
        next_ratio = old_ratio + ratio_change
        if ratio < next_ratio:
            return

    send_mail('mirocommunity_saas/mail/video_limit/subject.txt',
              'mirocommunity_saas/mail/video_limit/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True),
              extra_context={'ratio': ratio})
    tier_info.video_limit_warning_sent = datetime.datetime.now()
    tier_info.video_count_when_warned = video_count
    tier_info.save()


def send_free_trial_ending():
    tier_info = SiteTierInfo.objects.get(site=settings.SITE_ID)
    # Only one free trial, so this can only be sent once.
    if tier_info.free_trial_ending_sent:
        return

    # If they haven't started a free trial, don't send.
    end = tier_info.get_free_trial_end()
    if end is None:
        return

    # If it is not exactly within the right timespan, don't send the email.
    warn_after = end - datetime.timedelta(FREE_TRIAL_WARNING_DAYS)
    now = datetime.datetime.now()
    if not (now < end and now > warn_after):
        return

    send_mail('mirocommunity_saas/mail/free_trial/subject.txt',
              'mirocommunity_saas/mail/free_trial/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True))
    tier_info.free_trial_ending_sent = datetime.datetime.now()
    tier_info.save()
