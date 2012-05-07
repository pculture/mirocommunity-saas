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

import logging
import datetime

from django.conf import settings
import django.contrib.auth.models
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import Context, loader

from localtv.models import SiteSettings, Video

from uploadtemplate.models import Theme

from mirocommunity_saas.management import commands

def user_warnings_for_downgrade(new_tier_name):
    import mirocommunity_saas.models
    warnings = set()

    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()

    current_tier = tier_info.get_tier()
    future_tier = Tier(new_tier_name)

    # How many admins do we have right now?
    current_admins_count = number_of_admins_including_superuser()
    # How many are we permitted to, in the future?
    future_admins_permitted = future_tier.admins_limit()

    if future_admins_permitted is not None:
        if current_admins_count > future_admins_permitted:
            warnings.add('admins')

    # Is there a custom theme? If so, check if we will have to ditch it.
    if (Theme.objects.filter(bundled=False) and
        current_tier.permit_custom_template()):
        # Does the future tier permit a custom theme? If not, complain:
        if not future_tier.permit_custom_template():
            warnings.add('customtheme')

    # If the old tier permitted advertising, and the new one does not,
    # then let the user know about that change.
    if (current_tier.permits_advertising() and
        not future_tier.permits_advertising()):
        warnings.add('advertising')

    # If the old tier permitted custom CSS, and the new one does not,
    # and the site has custom CSS in use, then warn the user.
    if (current_tier.permit_custom_css() and
        not future_tier.permit_custom_css() and
        tier_info.site_settings.css.strip()):
            warnings.add('css')

    # If the site has a custom domain, and the future tier doesn't permit it, then
    # we should warn the user.
    if (tier_info.enforce_tiers()
        and tier_info.site_settings.site.domain
        and not tier_info.site_settings.site.domain.endswith('mirocommunity.org')
        and not future_tier.permits_custom_domain()):
        warnings.add('customdomain')

    if current_videos_that_count_toward_limit().count() > future_tier.videos_limit():
        warnings.add('videos')

    return warnings

### Here, we listen for changes in the SiteSettings
def pre_save_set_payment_due_date(instance, signal, **kwargs):
    if not instance.pk:
        # not saved yet, don't bother checking
        return

    from mirocommunity_saas import models
    tier_info = models.TierInfo.objects.get_current()

    new_tier_name = instance.tier_name

    current_tier_obj = tier_info.get_tier()
    new_tier_obj= Tier(new_tier_name)

    # Two cases, here:
    # 1. The site was created, hoping to be set to a tier, and this is the
    # IPN event that makes that possible.
    #
    # 2. The site has been around a while, and we send an email because it
    # is an upgrade.

    # Either way, we only trigger any email sending if the tier cost is
    # changing.
    if new_tier_obj.dollar_cost() > current_tier_obj.dollar_cost():
        # Case 1 (this field is set by the site creation scripts)
        if instance.should_send_welcome_email_on_paypal_event:
            # Reset the flag...
            instance.should_send_welcome_email_on_paypal_event = False
            # ...enqueue the mail
            instance.add_queued_mail(
                ('send_welcome_email_hack', {}))
            # ...and stop processing at this point
            return

        # Case 2: Normal operation
        # Plan to send an email about the transition
        # but leave it queued up in the instance. We will send it post-save.
        # This eliminates a large source of possible latency.
        #
        # In theory, we should hold a lock on the TierInfo object.
        template_name = 'mirocommunity_saas/tiers_emails/welcome_to_tier.txt'
        subject = '%s has been upgraded!' % (
            instance.site_settings.site.name or
            instance.site_settings.site.domain)

        # Pass in the new, modified TierInfo instance. That way, it has
        # the new tier.
        instance.add_queued_mail(
            ((subject, template_name), {'tier_info': instance}))

def pre_save_adjust_resource_usage(instance, signal, raw, **kwargs):
    if raw: # if we are loading data from a fixture, skip these checks
        return

    import mirocommunity_saas.models
    if not mirocommunity_saas.models.TierInfo.objects.exists():
        return

    ### Check if tiers enforcement is disabled. If so, bail out now.
    if not mirocommunity_saas.models.TierInfo.enforce_tiers():
        return

    # When transitioning between any two site tiers, make sure that
    # the number of admins there are on the site is within the tier.
    new_tier_name = instance.tier_name
    new_tier_obj = Tier(new_tier_name)
    push_number_of_admins_down(new_tier_obj.admins_limit(),
                               actually_demote_people=True)

    # When transitioning down from a tier that permitted custom domains, and if
    # the user had a custom domain, then this website should automatically file
    # a support request to have the site's custom domain disabled.
    if 'customdomain' in user_warnings_for_downgrade(new_tier_name):
        message = send_tiers_related_email(
            subject="Remove custom domain for %s" % (
                instance.site_settings.site.domain,),
            template_name=("mirocommunity_saas/tiers_emails/"
                           "disable_my_custom_domain.txt"),
            tier_info=instance,
            override_to=['mirocommunity@pculture.org'],
            just_rendered_body=True)

        # If the site is configured to, we can send notifications of
        # tiers-related changes to ZenDesk, the customer support ticketing
        # system used by PCF.
        #
        # A non-PCF deployment of localtv would not want to set the
        # LOCALTV_USE_ZENDESK setting.
        if instance.use_zendesk():
            import mirocommunity_saas.zendesk
            mirocommunity_saas.zendesk.create_ticket(
                "Remove custom domain for %s" % (
                    instance.site_settings.site.domain,),
                message,
                use_configured_assignee=False)

    # Push the published videos into something within the limit
    hide_videos_above_limit(new_tier_obj, actually_do_it=True)

    # Also change the theme, if necessary.
    switch_to_a_bundled_theme_if_necessary(new_tier_obj, actually_do_it=True)

def send_tiers_related_email(subject, template_name, tier_info, override_to=None, extra_context=None, just_rendered_body=False):
    site_settings = tier_info.site_settings

    # Send it to the site superuser with the lowest ID
    first_one = get_main_site_admin()
    if not first_one:
        logging.error("Hah, there is no site admin. Screw email.")
        return

    if not first_one.email:
        logging.error("Hah, there is a site admin, but that person has no email address set. Email is hopeless.")
        return

    if tier_info.payment_due_date:
        next_payment_due_date = tier_info.payment_due_date.strftime('%B %e, %Y')
    else:
        next_payment_due_date = None

    # Generate the email
    t = loader.get_template(template_name)
    data = {'site': site_settings.site,
            'in_free_trial': tier_info.in_free_trial,
            'tier_obj': tier_info.get_tier(),
            'tier_name_capitalized': tier_info.tier_name.title(),
            'site_name': site_settings.site.name or site_settings.site.domain,
            'video_count': current_videos_that_count_toward_limit().count(),
            'short_name': first_one.first_name or first_one.username,
            'next_payment_due_date': next_payment_due_date,
            }
    if extra_context:
        data.update(extra_context)

    c = Context(data)
    message = t.render(c)
    if just_rendered_body:
        return message

    recipient_list = [first_one.email]
    if override_to:
        assert type(override_to) in (list, tuple)
        recipient_list = override_to

    # Send the sucker
    from django.conf import settings
    EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL,
                 recipient_list).send(fail_silently=False)

def send_tiers_related_multipart_email(subject, template_name, tier_info,
                                       override_to=None, extra_context=None,
                                       just_rendered_body=False,
                                       override_text_template=None,
                                       override_html_template=None):
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()

    # Send it to the site superuser with the lowest ID
    first_one = get_main_site_admin()
    if not first_one:
        logging.error("No site admins; can't send %r", subject)
        return

    if not first_one.email:
        logging.error("First admin doesn't have email; can't send %r", subject)
        return

    if tier_info.payment_due_date:
        next_payment_due_date = tier_info.payment_due_date.strftime('%B %e, %Y')
    else:
        next_payment_due_date = None

    # Generate the email
    if override_text_template:
        t = override_text_template
    else:
        t = loader.get_template(template_name)

    data = {'site': tier_info.site_settings.site,
            'in_free_trial': tier_info.in_free_trial,
            'tier_obj': tier_info.get_tier(),
            'tier_name_capitalized': tier_info.tier_name.title(),
            'site_name': (tier_info.site_settings.site.name or
                          tier_info.site_settings.site.domain),
            'video_count': current_videos_that_count_toward_limit().count(),
            'short_name': first_one.first_name or first_one.username,
            'next_payment_due_date': next_payment_due_date,
            }
    if extra_context:
        data.update(extra_context)

    c = Context(data)
    message = t.render(c)
    if just_rendered_body:
        return message

    recipient_list = [first_one.email]
    if override_to:
        assert type(override_to) in (list, tuple)
        recipient_list = override_to

    # So, let's jam the above text into a multipart email. Soon, we'll render
    # an HTML version of the same template and stick that into the message.
    msg = EmailMultiAlternatives(subject, message, settings.DEFAULT_FROM_EMAIL,
            recipient_list)

    if override_html_template:
        html_t = override_html_template
    else:
        html_t = loader.get_template(template_name.replace('.txt', '.html'))

    message_html = html_t.render(c)
    msg.attach_alternative(message_html, "text/html")
    msg.send(fail_silently=False)
