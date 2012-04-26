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

def nightly_warnings():
    import mirocommunity_saas.models
    '''This returns a dictionary, mapping English-language reasons to
    localtv.admin.tiers functions to call.'''
    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()
    current_tier = tier_info.get_tier()
    ret = set()
    if should_send_video_allotment_warning(current_tier):
        ret.add('video_allotment_warning_sent')
    if should_send_five_day_free_trial_warning():
        ret.add('free_trial_warning_sent')
    #if should_send_inactive_site_warning(site_settings, current_tier):
    #    ret.add('inactive_site_warning_sent')
    # NOTE: Commented out the inactive site warning because the
    # text is not fully-baked.
    return ret

def get_main_site_admin():
    superusers = django.contrib.auth.models.User.objects.filter(is_superuser=True)
    first_ones = superusers.order_by('pk')
    if first_ones:
        return first_ones[0]
    return None # eek, any callers had better check for this.

def should_send_inactive_site_warning(current_tier):
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()
    # If we have already sent the warning, refuse to send it again.
    if tier_info.inactive_site_warning_sent:
        return False

    # Grab the time the main site admin last logged in. If it is greater
    # than six weeks, then yup, the admin gets a warning.
    SIX_WEEKS = datetime.timedelta(days=7 * 6)
    main_site_admin = get_main_site_admin()
    if not main_site_admin:
        raise ValueError, "Uh, this site has no admin. Something has gone horribly wrong."
    if (datetime.datetime.utcnow() - main_site_admin.last_login) > SIX_WEEKS:
        return True

def should_send_video_allotment_warning(current_tier):
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()
    # Check for the video warning having already been sent
    if tier_info.video_allotment_warning_sent:
        return False

    if current_tier.remaining_videos_as_proportion() < (1/3.0):
        return True

def should_send_five_day_free_trial_warning():
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()

    time_remaining = tier_info.time_until_free_trial_expires()
    if time_remaining is None:
        return False
    if tier_info.free_trial_warning_sent:
        return False

    if time_remaining < datetime.timedelta():
        raise ValueError, "Well, that sucks, the trial is negative."

    if time_remaining <= datetime.timedelta(days=5):
        return True
    return False

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

### XXX Merge all these functions into one tidy little thing.

def current_videos_that_count_toward_limit():
    import localtv.models
    return localtv.models.Video.objects.filter(
                                status=localtv.models.Video.ACTIVE)

def hide_videos_above_limit(future_tier_obj, actually_do_it=False):
    import localtv.models
    new_limit = future_tier_obj.videos_limit()
    current_count = current_videos_that_count_toward_limit().count()
    if current_count <= new_limit:
        count = 0
    count = (current_count - new_limit)
    if not actually_do_it:
        return count

    if count <= 0:
        return

    disable_these_videos = current_videos_that_count_toward_limit().order_by('pk')
    disable_these_pks = list(disable_these_videos.values_list('id', flat=True)[:count])

    # Use a bulk .update() call so it's all done in one SQL query.
    disable_these_videos = localtv.models.Video.objects.filter(pk__in=disable_these_pks)
    return disable_these_videos.update(status=localtv.models.Video.UNAPPROVED)

def switch_to_a_bundled_theme_if_necessary(future_tier_obj, actually_do_it=False):
    if Theme.objects.filter(default=True):
        current_theme = Theme.objects.get_default()
        if not current_theme.bundled:
            if not future_tier_obj.permit_custom_template():
                # Grab the bundled theme with the lowest ID, and make it the default.
                # If there is no such theme, log an error, but do not crash.
                bundleds = Theme.objects.filter(bundled=True).order_by('pk')
                if bundleds:
                    first = bundleds[0]
                    if actually_do_it:
                        first.set_as_default()
                    return first.name
                else:
                    logging.error("Hah, there are no bundled themes left.")
                    return None

def push_number_of_admins_down(new_limit, actually_demote_people=False):
    import localtv.models
    '''Return a list of usernames that will be demoted.

    If you pass actually_demote_people in as True, then the function will actually
    remove people from the admins set.'''
    # None is the special value indicating there is no limit.
    if new_limit is None:
        return

    # No matter what, the super-user is going to still be an admin.
    # Therefore, any limit has to be greater than or equal to one.
    assert new_limit >= 1

    # grab hold of the current SiteSettings
    try:
        site_settings = localtv.models.SiteSettings.objects.get_current()
    except localtv.models.SiteSettings.DoesNotExist:
        return # well okay, there is no current SiteSettings.

    # We have this many right now
    initial_admins_count = number_of_admins_including_superuser()

    # If we do not have excess admins, we can quit early.
    demote_this_many = initial_admins_count - new_limit
    if demote_this_many <= 0:
        return

    # Okay, we have to actually demote some users from admin.
    # Well, uh, sort them by user ID.
    demotees = site_settings.admins.order_by('-pk')[:demote_this_many]
    demotee_usernames = set([x.username for x in demotees])
    if actually_demote_people:
        for demotee in demotees:
            site_settings.admins.remove(demotee)
    return demotee_usernames


def number_of_admins_including_superuser():
    try:
        site_settings = SiteSettings.objects.get_current()
    except SiteSettings.DoesNotExist:
        return 0

    normal_admin_ids = set([k.id for k in
                            site_settings.admins.filter(is_active=True)])
    super_user_ids = set(
        [k.id for k in
         django.contrib.auth.models.User.objects.filter(
                is_superuser=True)])
    normal_admin_ids.update(super_user_ids)
    num_admins = len(normal_admin_ids)
    return num_admins

## These "CHOICES" are used in the SiteSettings model.
## They describe the different account types.
CHOICES = [
    ('basic', 'Free account'),
    ('plus', 'Plus account'),
    ('premium', 'Premium account'),
    ('max', 'Max account')]

class Tier(object):

    @staticmethod
    def NAME_TO_COST():
        prices = {'basic': 0,
                   'plus': 79,
                   'premium': 149,
                   'max': 299}
        overrides = getattr(settings, "LOCALTV_COST_OVERRIDE", None)
        if overrides:
            for key in overrides:
                # So, uh, don't override the price of
                # 'basic'. Assumptions that 'basic' is the
                # free-of-cost tier might be sprinkled through the
                # code.
                assert key != 'basic'

                # Okay, great. Accept the override.
                prices[key] = overrides[key]

        # Note: the prices dict should really be a one-to-one mapping,
        # and all the values should be integers. Anything else is crazy,
        # so I will take this moment to assert these properties.
        for key in prices:
            # Make sure the value is an integer.
            assert type(prices[key]) == int

        prices_as_sorted_list = sorted(list(prices.values()))
        prices_as_sorted_dedup = sorted(set(prices.values()))
        assert prices_as_sorted_dedup == prices_as_sorted_list

        return prices

    def __init__(self, tier_name, site_settings=None):
        self.tier_name = tier_name
        self.site_settings = site_settings

    @staticmethod
    def get(log_warnings=False, using='default'):
        import mirocommunity_saas.models
        DEFAULT = None

        # Iterative sanity checks
        # We have a settings.SITE_ID, right?
        site_id = getattr(settings, 'SITE_ID', None)
        if site_id is None and log_warnings:
            logging.warn("Eek, SITE_ID is None.")
            return DEFAULT
        tier_info = mirocommunity_saas.models.TierInfo.objects.get_current()

        # We have a tier set, right?
        if tier_info.tier_name:
            # Good, then just call get_tier() and return the result.
            return tier_info.get_tier()
        else:
            if log_warnings:
                logging.warn("Eek, we have no tier set.")
            return DEFAULT

    @staticmethod
    def get_by_cost(cost):
        cost = int(cost)
        reverse_mapping = dict([(value, key) for (key, value) in Tier.NAME_TO_COST().items()])
        if cost in reverse_mapping:
            return reverse_mapping[cost]
        raise ValueError, "Hmm, no such cost."

    def permits_advertising(self):
        special_cases = {'premium': True,
                         'max': True}
        return special_cases.get(self.tier_name, False)

    def permits_custom_domain(self):
        special_cases = {'basic': False}
        return special_cases.get(self.tier_name, True)

    def videos_limit(self):
        special_cases = {'basic': 500,
                         'plus': 1000,
                         'premium': 5000,
                         'max': 25000}
        return special_cases[self.tier_name]

    def can_add_more_videos(self):
        import mirocommunity_saas.models
        '''Returns True if tiers enforcement is disabled, or if we have fewer
        videos than the tier limits us to.

        Returns False if it is *not* okay to add more videos to the site.'''
        if self.site_settings:
            enforce = self.site_settings.tierinfo.enforce_tiers(
                using=self.site_settings._state.db)
        else:
            enforce = mirocommunity_saas.models.TierInfo.enforce_tiers()
        if not enforce:
            return True

        remaining_video_count = self.remaining_videos()
        return (remaining_video_count > 0)

    def remaining_videos(self):
        return (self.videos_limit() -
                current_videos_that_count_toward_limit().count())

    def remaining_videos_as_proportion(self):
        return (self.remaining_videos() * 1.0 / self.videos_limit())

    def admins_limit(self):
        special_cases = {'basic': 1,
                         'plus': 5}
        default = None
        return special_cases.get(self.tier_name, default)

    def permit_custom_css(self):
        special_cases = {'basic': False}
        default = True
        return special_cases.get(self.tier_name, default)

    def permit_custom_template(self):
        special_cases = {'max': True}
        default = False
        return special_cases.get(self.tier_name, default)

    def permit_newsletter(self):
        special_cases = {}
        default = False
        return special_cases.get(self.tier_name, default)

    def dollar_cost(self):
        special_cases = self.NAME_TO_COST()
        return special_cases[self.tier_name]

class PaymentException(Exception):
    pass

class WrongPaymentSecret(PaymentException):
    pass

class WrongAmount(PaymentException):
    pass

class WrongStartDate(PaymentException):
    pass

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

def post_save_send_queued_mail(sender, instance, **kwargs):
    for (args, kwargs) in instance.get_queued_mail_destructively():
        ### Epic hack :-(
        if args == 'send_welcome_email_hack':
            cmd = commands.send_welcome_email.Command()
            cmd.handle(
                temporarily_override_payment_due_date=(
                    datetime.datetime.utcnow() + datetime.timedelta(days=30)))
        else:
            send_tiers_related_email(*args, **kwargs)

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

def get_paypal_email_address():
    '''If the site is configured to use PayPal, then we return
    the setting from the config:

    PAYPAL_RECEIVER_EMAIL

    Otherwise, we return a string that indicates that PayPal is
    not properly configured.'''
    DEFAULT = 'payal-misconfigured@example.com'
    return getattr(settings, 'PAYPAL_RECEIVER_EMAIL', DEFAULT)

def pre_mark_as_active(sender, active_set, **kwargs):
    """
    Called during task import, to figure out if we should actually approve all
    these videos.  Returns either a Q object, or a dictionary of filters.
    """
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.db_manager(
        sender._state.db).get_current()
    tier = tier_info.get_tier()
    remaining_videos = tier.remaining_videos()
    if remaining_videos > active_set.count():
        # don't need to filter
        return
    elif remaining_videos > 0:
        # approve the earliest videos submitted
        active_set = active_set.order_by('when_submitted')
        when_submitted = active_set[remaining_videos].when_submitted
        return {'when_submitted__lt': when_submitted}
    else:
        # don't approve any videos!
        return {'status': -1}

def submit_finished(sender, **kwargs):
    """
    Called after someone has submitted a video.  We check if the video can't be
    approved.
    """
    import mirocommunity_saas.models
    tier_info = mirocommunity_saas.models.TierInfo.objects.db_manager(
        sender._state.db).get_current()
    tier = tier_info.get_tier()
    if sender.status == Video.ACTIVE and not tier.can_add_more_videos():
        sender.status = Video.UNAPPROVED
        sender.save()
