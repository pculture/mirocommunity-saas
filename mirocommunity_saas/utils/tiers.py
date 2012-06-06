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

from django.conf import settings
from django.contrib.sites.models import Site
from django.dispatch import receiver
from django.utils.crypto import constant_time_compare, salted_hmac
from localtv.models import SiteSettings, Video
from localtv.signals import pre_mark_as_active, submit_finished
from paypal.standard.ipn.signals import (payment_was_successful,
                                         payment_was_flagged,
                                         subscription_signup,
                                         subscription_modify,
                                         subscription_cancel,
                                         subscription_eot)
from uploadtemplate.models import Theme

from mirocommunity_saas.models import SiteTierInfo, Tier
from mirocommunity_saas.utils.mail import send_mail


def admins_to_demote(tier):
    """
    Given a tier, returns a list of admins for a given site (or the current
    site if none is given) to demote in order to meet the tier's
    :attr:`admin_limit`.

    """
    # If there is no limit, we're done.
    if tier.admin_limit is None:
        return []

    site_settings = SiteSettings.objects.get_current()
    admins = site_settings.admins.exclude(is_superuser=True
                                ).exclude(is_active=False)
    # If the number of admins is already below the limit, we're done.
    demotee_count = admins.count() - tier.admin_limit
    if demotee_count <= 0:
        return []

    # Okay, we have to demote them. Doesn't really matter which ones get
    # demoted... just take the most recently created users.
    return list(admins.order_by('-pk')[:demotee_count])


def videos_to_deactivate(tier):
    """
    Given a tier, returns a list of videos for the current site which will
    need to be deactivated in order to meet the tier's :attr:`video_limit`.

    """
    # If there is no limit, we're done.
    if tier.video_limit is None:
        return []

    videos = Video.objects.filter(status=Video.ACTIVE, site=settings.SITE_ID)
    # If the number of videos is already below the limit, we're done.
    deactivate_count = videos.count() - tier.video_limit
    if deactivate_count <= 0:
        return []

    # Okay, we have to deactivate some videos. We take the oldest videos in
    # the hope that they're receiving less attention than the new videos.
    return list(videos.order_by('when_approved')[:deactivate_count])


def enforce_tier(tier):
    """
    Enforces a tier's limits for the current site. This includes:

    - Demoting extra admins.
    - Deactivating extra videos.
    - Deactivating custom themes.
    - Deactivating custom domains. (Or at least emailing support to do so.)

    """
    demotees = admins_to_demote(tier)
    site_settings = SiteSettings.objects.get_current()
    site = site_settings.site
    for demotee in demotees:
        site_settings.admins.remove(demotee)

    deactivate_pks = [v.pk for v in videos_to_deactivate(tier)]
    if deactivate_pks:
        Video.objects.filter(pk__in=deactivate_pks).update(
                                                    status=Video.UNAPPROVED)

    if (not tier.custom_domain and
        not site.domain.endswith(".mirocommunity.org")):
        send_mail('mirocommunity_saas/mail/disable_domain/subject.txt',
                  'mirocommunity_saas/mail/disable_domain/body.md')
        tier_info = SiteTierInfo.objects.get_current()
        if tier_info.site_name:
            site.domain = "{0}.mirocommunity.org".format(tier_info.site_name)
            site.save()

    if not tier.custom_themes:
        Theme.objects.set_default(None)


def make_tier_change_token(new_tier):
    site = Site.objects.get_current()
    tier_info = SiteTierInfo.objects.get_current()
    # We hash on the site domain to make sure we stay on the same site, and on
    # the tier_name/tier_changed so that the link will stop working once it's
    # used.
    value = (unicode(new_tier.id) + settings.SECRET_KEY + site.domain +
             unicode(tier_info.tier_id) + tier_info.tier_changed.isoformat())
    key_salt = "mirocommunity_saas.views.TierView"
    return salted_hmac(key_salt, value).hexdigest()[::2]


def check_tier_change_token(new_tier, token):
    return constant_time_compare(make_tier_change_token(new_tier), token)


@receiver(pre_mark_as_active)
def limit_import_approvals(sender, active_set, **kwargs):
    """
    Called towards the end of an import to figure out which videos (if any)
    should actually be approved. Returns either a Q object or a dictionary of
    filters. ``sender`` is a ``SourceImport`` instance.

    """
    # We use the sender's db; this is part of the HACK that is the settings
    # patching. TODO: Remove that hack ;-)
    # Perhaps this should be done by just running tiers enforcement after the
    # import?
    using = sender._state.db
    tier = SiteTierInfo.objects.db_manager(using).get_current().tier
    videos = Video.objects.using(using).filter(status=Video.ACTIVE,
                                               site=settings.SITE_ID)
    remaining_count = tier.video_limit - videos.count()
    if remaining_count >= active_set.count():
        # don't need to filter.
        return
    elif remaining_count > 0:
        # approve the earlier videos.
        last_video = active_set.order_by('when_submitted')[remaining_count]
        return {'when_submitted__lt': last_video.when_submitted}
    else:
        # Don't approve any videos.
        return {'status': -1}


@receiver(submit_finished)
def check_submission_approval(sender, **kwargs):
    """
    Called after someone has submitted a video. Mark the video unapproved if
    it's active and it put the user over their video limit.

    """
    if sender.status != Video.ACTIVE:
        # Okay, then nothing to do.
        return

    using = sender._state.db
    tier = SiteTierInfo.objects.db_manager(using).get_current().tier
    videos = Video.objects.using(using).filter(status=Video.ACTIVE,
                                               site=settings.SITE_ID)
    remaining_count = tier.video_limit - videos.count()
    if remaining_count < 0:
        sender.status = Video.UNAPPROVED
        sender.save()


def set_tier_by_payment(payment):
    """
    Given a payment amount, checks whether that payment amount matches the
    price of the current tier. If so, does nothing. Otherwise, tries to set
    and enforce an available tier with that price, and emails the site devs if
    it works or if something unexpected happens (like the tier not existing).
    """
    tier_info = SiteTierInfo.objects.get_current()
    tier = tier_info.tier

    # We only need to take action if the payment doesn't match the current
    # tier's price.
    if payment != tier.price:
        try:
            new_tier = tier_info.available_tiers.get(price=payment)
        except Tier.DoesNotExist:
            # Email the site devs to let them know we got a payment for a tier
            # that doesn't seem to exist, and stop processing immediately.
            send_mail('mirocommunity_saas/mail/invalid_payment/subject.txt',
                      'mirocommunity_saas/mail/invalid_payment/body.md',
                      extra_context={
                        'not_found': True,
                        'payment': payment,
                      })
            return
        except Tier.MultipleObjectsReturned:
            # Email the site devs to let them know we got an ambiguous payment
            # and stop processing immediately. At the moment, no ambiguous
            # payments are possible, but we should still catch the case.
            send_mail('mirocommunity_saas/mail/invalid_payment/subject.txt',
                      'mirocommunity_saas/mail/invalid_payment/body.md',
                      extra_context={
                        'multiple_found': True,
                        'payment': payment,
                      })
            return

        tier_info.tier = new_tier
        tier_info.save()
        enforce_tier(new_tier)
        # Email site devs to let them know about the change.
        send_mail('mirocommunity_saas/mail/tier_change/dev_subject.txt',
                  'mirocommunity_saas/mail/tier_change/dev_body.md',
                  extra_context={
                    'old_tier': tier,
                    'payment': payment,
                  })


@receiver(payment_was_successful)
def payment_handler(sender, **kwargs):
    """
    Sets the tier according to the ipn payment.

    """
    # mc_gross is the current field for the total payment (without txn fees
    # taken out). It replaces the older payment_gross field.
    set_tier_by_payment(sender.mc_gross)


@receiver(subscription_eot)
def expiration_handler(sender, **kwargs):
    """
    If a subscription expires (for example, at the end of the month after a
    cancellation) then we should reset to the basic (i.e. free) tier.

    """
    # First, make sure that the ipn is added.
    record_new_ipn(sender, **kwargs)
    # Only continue for non-flagged ipns.
    if not sender.flag:
        # Only continue if the user doesn't have a current active
        # subscription, which could happen if they cancelled an old
        # subscription and then started a new one before the old one expired.
        tier_info = SiteTierInfo.objects.get_current()
        if tier_info.subscription is None:
            set_tier_by_payment(0)


@receiver(payment_was_successful)
@receiver(payment_was_flagged)
@receiver(subscription_cancel)
@receiver(subscription_modify)
@receiver(subscription_signup)
def record_new_ipn(sender, **kwargs):
    """
    Adds the sending ipn to the ``ipn_set`` of the current ``SiteTierInfo``
    and clears the subscription cache.

    """
    tier_info = SiteTierInfo.objects.get_current()
    tier_info.ipn_set.add(sender)
    try:
        del tier_info._subscription
    except AttributeError:
        pass
