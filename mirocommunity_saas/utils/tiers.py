import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.dispatch import receiver
from django.utils.crypto import constant_time_compare, salted_hmac
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
    from localtv.models import SiteSettings
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

    from localtv.models import Video
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
    from localtv.models import SiteSettings, Video
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
                  'mirocommunity_saas/mail/disable_domain/body.md',
                  to=settings.MANAGERS)
        tier_info = SiteTierInfo.objects.get_current()
        if tier_info.site_name:
            site.domain = "{0}.mirocommunity.org".format(tier_info.site_name)
            site.save()

    if not tier.custom_themes:
        try:
            theme = Theme.objects.get_current()
        except Theme.DoesNotExist:
            pass
        else:
            theme.default = False
            theme.save()


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
    from localtv.models import Video
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
    from localtv.models import Video
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


def set_tier(price):
    """
    Given a price, ensures that it matches the price of the current tier.
    If not, tries to set and enforce an available tier with that price,
    and emails the site devs if it works or if something unexpected
    happens (like the tier not existing).

    """
    tier_info = SiteTierInfo.objects.get_current()

    # We only need to take action if the payment doesn't match the current
    # tier's price.
    if price != tier_info.tier.price:
        old_tier = tier_info.tier
        # Let errors propagate.
        tier_info.tier = tier_info.available_tiers.get(price=price)
        tier_info.save()
        enforce_tier(tier_info.tier)
        # Email site managers to let them know about the change.
        send_mail('mirocommunity_saas/mail/tier_change/subject.txt',
                  'mirocommunity_saas/mail/tier_change/body.md',
                  to=settings.MANAGERS,
                  extra_context={
                    'old_tier': old_tier,
                  })


@receiver(payment_was_successful)
@receiver(payment_was_flagged)
@receiver(subscription_signup)
@receiver(subscription_modify)
@receiver(subscription_cancel)
@receiver(subscription_eot)
def record_new_ipn(sender, **kwargs):
    """
    Adds the sending ipn to the ``ipn_set`` of the current ``SiteTierInfo``
    and clears the subscription cache.

    """
    tier_info = SiteTierInfo.objects.get_current()
    tier_info.ipn_set.add(sender)

    if not sender.flag:
        try:
            del tier_info.subscriptions
        except AttributeError:
            pass

        try:
            del tier_info.subscription
        except AttributeError:
            pass

        if tier_info.enforce_payments:
            price = (0 if tier_info.subscription is None
                     else tier_info.subscription.signup_or_modify.amount3)
            try:
                set_tier(price)
            except Tier.DoesNotExist:
                logging.error('No tier matching current subscription.',
                              exc_info=True)
            except Tier.MultipleObjectsReturned:
                logging.error('Multiple tiers found matching current'
                              'subscription.', exc_info=True)
