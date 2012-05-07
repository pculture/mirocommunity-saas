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

from django.db import models


class Tier(models.Model):
    #: Human-readable name.
    name = models.CharField(max_length=30)
    #: Unique slug.
    slug = models.SlugField(max_length=30)

    #: Price (USD) for the tier.
    price = models.PositiveIntegerField()

    #: Maximum number of admins allowed by this tier (excluding superusers).
    #: If blank, unlimited admins can be chosen.
    admin_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Maximum number of videos for this tier. If blank, videos are unlimited.
    video_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Whether custom css is permitted for this tier.
    custom_css = models.BooleanField()

    #: Whether custom themes are permitted for this tier.
    custom_themes = models.BooleanField()

    #: Whether a custom domain is allowed for this tier.
    custom_domain = models.BooleanField()

    #: Whether users at this level are allowed to run advertising.
    ads_allowed = models.BooleanField()

    class Meta:
        unique_together = ('slug', 'tier_set')


class SiteTierInfo(models.Model):
    site = models.ForeignKey(Site)

    #: A list of tiers that the site admin can choose from.
    available_tiers = models.ManyToManyField(Tier,
                                             related_name='site_available_set')
    #: The current selected tier (based on the admin's choice).
    tier = models.ForeignKey(Tier)

    #: Date and time when the tier was last changed.
    tier_changed = models.DateTimeField()

    #: The current actual tier (set automatically based on payments). If the
    #: current tier is changed, but doesn't get confirmed, the site will be
    #: reset to this value. TODO: Can this be handled by just checking the
    #: most recent paypal transaction? Probably.
    #confirmed_tier = models.ForeignKey(Tier)

    #: A list of payment objects for this site. This can be used, for example,
    #: to check the next due date for the subscription.
    payments = models.ManyToManyField(PayPalIPN, blank=True)

    #: Whether or not the current tier should be enforced by making sure
    #: payments are coming in.
    enforce_payments = models.BooleanField(default=False)

    #: Whether this site has ever had a free trial. This can probably be
    #: replaced with a query of IPN data.
    #free_trial_available = models.BooleanField(default=True)

    #: Whether a welcome email has been sent to this site's owner.
    #: TODO: is this really a tiers issue?
    welcome_email_sent = models.BooleanField(default=False)

    #: Whether a warning has been sent to the site's owner to let them know
    #: they're approaching their video limit.
    video_allotment_warning_sent = models.BooleanField(default=False)

    #: Whether this site has ever received a "free trial ending" email.
    free_trial_ending_sent = models.BooleanField(default=False)

    #: Whether this site has already received an "inactive site" warning.
    inactive_site_warning_sent = models.BooleanField(default=False)

    #: Whether this site has already received a "tiers compliance" email.
    tiers_compliance_email_sent = models.BooleanField(default=False)
