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
from uploadtemplate.models import Theme

from mirocommunity_saas.models import Tier, SiteTierInfo


def admins_to_demote(site, tier):
    """
    Given a site and a tier, returns a list of admins to demote in order to
    meet the tier's :attr:`admin_limit`.

    """
    # If there is no limit, we're done.
    if tier.admin_limit is None:
        return []

    site_settings = SiteSettings.objects.get(site=site)
    admins = site_settings.admins.exclude(is_superuser=True, is_active=True)
    # If the number of admins is already below the limit, we're done.
    demotee_count = admins.count() - tier.admin_limit
    if demotee_count <= 0:
        return []

    # Okay, we have to demote them. Doesn't really matter which ones get
    # demoted... just take the most recently created users.
    return list(admins.order_by('-pk')[:demotee_count])


def videos_to_deactivate(site, tier):
    """
    Given a site and a tier, returns a list of videos to deactivate in order
    to meet the tier's :attr:`admin_limit`.

    """
    # If there is no limit, we're done.
    if tier.video_limit is None:
        return []

    videos = Video.objects.filter(status=Video.ACTIVE, site=site)
    # If the number of videos is already below the limit, we're done.
    deactivate_count = videos.count() - tier.video_limit
    if deactivate_count <= 0:
        return []

    # Okay, we have to deactivate some videos. Let's take the most recently
    # approved videos, since they're 
    return list(videos.order_by('-when_approved')[:deactivate_count])


def enforce_tier(site, tier):
    """
    Enforces a tier's limits for the given site. This includes:

    - Demoting extra admins.
    - Deactivating extra videos.
    - Deactivating custom themes.
    - Deactivating custom domains. (Or at least emailing support to do so.)

    """
    demotees = admins_to_demote(site, tier)
    site_settings = SiteSettings.objects.get(site=site)
    for demotee in demotees:
        site_settings.admins.remove(demotee)

    deactivate_pks = [v.pk for v in videos_to_deactivate(site, tier)]
    if deactivate_pks:
        Video.objects.filter(pk__in=deactivate_pks).update(
                                                    status=Video.UNAPPROVED)

    if not tier.custom_domain:
        # TODO: Email support, or automatically remove the custom domain.
        # Probably also reset the current site's domain name.
        pass

    if not tier.custom_themes:
        Theme.objects.filter(default=True).update(default=False)


def make_tier_change_token(new_tier):
    site = Site.objects.get_current()
    tier_info = SiteTierInfo.objects.get(site=site)
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
    filters.

    """
    # We use the sender's db; this is part of the HACK that is the settings
    # patching. TODO: Remove that hack ;-)
    # Perhaps this should be done by just running tiers enforcement after the
    # import?
    using = sender._state.db
    tier = Tier.objects.db_manager(using).get(
                                          sitetierinfo__site=settings.SITE_ID)
    videos = Video.objects.using(using).filter(status=Video.ACTIVE)
    remaining_count = tier.video_limit - videos.count()
    if remaining_count > active_set.count():
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
    tier = Tier.objects.db_manager(using).get(
                                          sitetierinfo__site=settings.SITE_ID)
    videos = Video.objects.using(using).filter(status=Video.ACTIVE)
    remaining_count = tier.video_limit - videos.count()
    if remaining_count < 0:
        sender.status = Video.UNAPPROVED
        sender.save()

### register pre-save handler for Tiers and payment due dates
#models.signals.pre_save.connect(tiers.pre_save_adjust_resource_usage,
#                                sender=TierInfo)
