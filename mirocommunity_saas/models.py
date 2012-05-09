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

from django.contrib.sites.models import Site
from django.db import models
from paypal.standard.ipn.models import PayPalIPN


class Tier(models.Model):
    #: Human-readable name.
    name = models.CharField(max_length=30)
    #: Slug. Not enforced as unique, but should be unique on a per-site basis
    #: as unique among the available tiers.
    slug = models.SlugField(max_length=30)

    #: Price (USD) for the tier.
    price = models.PositiveIntegerField(default=0)

    #: Maximum number of admins allowed by this tier (excluding superusers).
    #: If blank, unlimited admins can be chosen.
    admin_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Maximum number of videos for this tier. If blank, videos are unlimited.
    video_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Whether custom css is permitted for this tier.
    custom_css = models.BooleanField(default=False)

    #: Whether custom themes are permitted for this tier.
    custom_themes = models.BooleanField(default=False)

    #: Whether a custom domain is allowed for this tier.
    custom_domain = models.BooleanField(default=False)

    #: Whether users at this level are allowed to run advertising.
    ads_allowed = models.BooleanField(default=False)

    #: Whether the crappy newsletter feature is enabled for this tier.
    #: Included for completeness.
    newsletter = models.BooleanField(default=False)


class SiteTierInfo(models.Model):
    site = models.OneToOneField(Site)

    #: A list of tiers that the site admin can choose from.
    available_tiers = models.ManyToManyField(Tier,
                                             related_name='site_available_set')
    #: The current selected tier (based on the admin's choice).
    tier = models.ForeignKey(Tier)

    #: Date and time when the tier was last changed.
    tier_changed = models.DateTimeField()

    #: A list of payment objects for this site. This can be used, for example,
    #: to check the next due date for the subscription.
    ipn_set = models.ManyToManyField(PayPalIPN, blank=True)

    #: Whether or not the current tier should be enforced by making sure
    #: payments are coming in.
    enforce_payments = models.BooleanField(default=False)

    #: The datetime when the welcome email was sent to this site's owner.
    #: TODO: is this really a tiers issue?
    welcome_email_sent = models.DateTimeField(blank=True, null=True)

    #: The datetime when a "free trial ending" email was sent to the site's
    #: owner.
    free_trial_ending_sent = models.DateTimeField(blank=True, null=True)

    #: The last datetime when a warning was sent to the site's owner to let
    #: them know they're approaching their video limit.
    video_limit_warning_sent = models.DateTimeField(blank=True, null=True)

    #: The video count for the site the last time that the site's owner
    #: received a video limit warning.
    video_count_when_warned = models.PositiveIntegerField(blank=True, null=True)

    def get_current_subscription(self):
        """
        Returns ``None`` if there is no active subscription, or a tuple where
        the first item is the ipn that started the subscription and the second
        item is either the most recent payment, or ``None`` if there have not
        been any payments.

        """
        # For reference - the way that we use paypal is that a new
        # subscription is started before the old subscription is ended. PayPal
        # will send subscr_cancel followed by subscr_eot for cancelled
        # subscriptions. Subscr_modify isn't used by us, and subscr_failed
        # isn't really relevant here.
        signups = self.ipn_set.filter(flag=False,
                                      txn_type='subscr_signup')

        try:
            latest_signup = signups.order_by('-created_at')[0]
        except IndexError:
            return (None, None)

        try:
            # We use eot as the ending since (in theory) we could have
            # subscriptions that actually do run out.
            self.ipn_set.get(subscr_id=latest_signup.subscr_id,
                             flag=False,
                             txn_type='subscr_eot')
        except PayPalIPN.DoesNotExist:
            pass
        else:
            return (None, None)

        try:
            latest_payment = self.ipn_set.filter(flag=False,
                                            txn_type='subscr_payment',
                                            subscr_id=latest_signup.subscr_id)
        except PayPalIPN.DoesNotExist:
            latest_payment = None

        return (latest_signup, latest_payment)

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = self.get_current_subscription()
        return self._subscription

    def _period_to_timedelta(self, period_str):
        """
        Converts an IPN period string to a timedelta representing that string.
        """
        period_len, period_unit = period_str.split(' ')
        period_len = int(period_len)
        if period_unit == 'D':
            period_unit = datetime.timedelta(1)
        else:
            # We don't support other periods at the moment...
            raise ValueError("Unknown period unit: {0}".format(period_unit))

        return period_len * period_unit

    @property
    def payments_expected(self):
        """
        ``True`` if payments are being enforced and the site is on a paid
        tier; ``False`` otherwise.
        """
        return self.enforce_payments and self.tier.price > 0

    def get_next_due_date(self):
        """
        Returns the datetime when the next payment is expected, or ``None`` if
        there is not an active subscription. This does not take into account
        whether payments are actually enforced, or whether the current tier is
        paid.

        """
        latest_signup, latest_payment = self.subscription

        if latest_signup is None:
            return None

        if latest_payment is None:
            return self.get_free_trial_end()

        period = self._period_to_timedelta(latest_signup.period3)
        return latest_payment.payment_date + period

    def get_free_trial_end(self):
        """
        Returns the datetime when the current subscription's free trial ends
        or ended. If there is no current subscription, returns ``None``; if
        the subscription does not include a free trial, returns the start of
        the subscription. This does not take into account whether payments are
        actually enforced, or whether the current tier is paid.

        """
        latest_signup = self.subscription[0]

        # If they have no signup, then the question is meaningless.
        if latest_signup is None:
            return None

        start = latest_signup.subscr_date

        # If there is no free trial, then return the start of the
        # subscription.
        if not latest_signup.period1:
            return start

        period = self._period_to_timedelta(latest_signup.period1)
        return start + period

    @property
    def in_free_trial(self):
        """
        Returns ``True`` if the site is currently in a free trial and
        ``False`` otherwise.  This does not take into account whether payments
        are actually enforced, or whether the current tier is paid.

        """
        end = self.get_free_trial_end()

        # If there's no subscription, there can't be a free trial.
        if end is None:
            return False

        return datetime.datetime.now() < end

    @property
    def gets_free_trial(self):
        """
        Returns ``True`` if the site has never had a subscription and
        ``False`` otherwise.

        """
        return self.subscription[0] is None
