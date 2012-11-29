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
from operator import attrgetter

from paypal.standard.ipn.models import PayPalIPN


def _period_to_timedelta(period_str):
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


class Subscription(object):
    """
    An abstract representation of a subscription, compiled from several ipn
    instances.

    :param signup_or_modify: This is treated as the most recent subscr_signup
                             or subscr_modify ipn for this subscription.
    :param payments: A queryset of payments for this subscription.
    :param cancel: The subscr_cancel ipn for this subscription, if any.

    """
    def __init__(self, signup_or_modify=None, payments=None, cancel=None):
        self.signup_or_modify = signup_or_modify
        self.payments = (sorted(payments, key=lambda p: p.payment_date, reverse=True)
                         if payments else PayPalIPN.objects.none())
        self.cancel = cancel

    @property
    def is_cancelled(self):
        return self.cancel is not None

    @property
    def start(self):
        if self.signup_or_modify is None:
            return datetime.datetime.min

        return (self.signup_or_modify.subscr_effective or
                self.signup_or_modify.subscr_date)

    @property
    def free_trial_end(self):
        """
        Returns the datetime when this subscription's free trial ends or
        ended. If the subscription has no free trial, returns the start of
        the subscription.

        """
        if self.signup_or_modify is None or not self.signup_or_modify.period1:
            return self.start

        period = _period_to_timedelta(self.signup_or_modify.period1)
        return self.start + period

    @property
    def in_free_trial(self):
        """
        ``True`` if the free trial for this subscription ends in the future;
        ``False`` otherwise.
        """
        return self.free_trial_end > datetime.datetime.now()

    @property
    def price(self):
        """
        The normal price for this subscription.

        """
        if self.signup_or_modify is not None:
            return self.signup_or_modify.amount3
        elif self.payments:
            return self.payments[0].mc_gross
        elif self.cancel is not None:
            return self.cancel.amount3
        else:
            raise AttributeError

    @property
    def next_due_date(self):
        """
        Returns the datetime when the next payment is expected.

        """
        if not self.payments:
            return self.free_trial_end

        if self.signup_or_modify is not None:
            period = _period_to_timedelta(self.signup_or_modify.period3)
        else:
            try:
                period = (self.payments[0].payment_date - self.payments[1].payment_date).days
            except IndexError:
                period = datetime.timedelta(days=30)
        return self.payments[0].payment_date + period


def get_subscriptions(ipn_set):
    """
    Returns a list of :class:`Subscription` instances corresponding to
    unexpired subscriptions represented by the given ipn_set (a queryset of
    :class:`PayPalIPN` instances.)

    """
    ipn_set = ipn_set.filter(flag=False)
    eot_ids = list(ipn_set.filter(txn_type='subscr_eot'
                         ).values_list('subscr_id', flat=True))
    ipn_set = ipn_set.exclude(subscr_id__in=eot_ids)
    signups_or_modifies = ipn_set.filter(txn_type__in=('subscr_signup',
                                                       'subscr_modify'))
    payments = ipn_set.filter(txn_type='subscr_payment')
    cancels = ipn_set.filter(txn_type='subscr_cancel')

    subscription_dict = {}

    for ipn in signups_or_modifies:
        subscription_dict.setdefault(ipn.subscr_id, {})['signup_or_modify'] = ipn

    for ipn in payments:
        subscription_dict.setdefault(ipn.subscr_id, {}).setdefault('payments', []).append(ipn)

    for ipn in cancels:
        subscription_dict.setdefault(ipn.subscr_id, {})['cancel'] = ipn

    subscriptions = []
    for kwargs in subscription_dict.itervalues():
        subscriptions.append(Subscription(**kwargs))

    return subscriptions


def get_current_subscription(subscriptions):
    """
    Picks out the subscription which is considered current out of a list
    of subscriptions. This is the most recently started subscription with
    the highest cost. Returns ``None`` if the list of subscriptions is empty.

    """
    if not subscriptions:
        return None
    # Secondary sort: date created.
    subscriptions = sorted(subscriptions,
                           key=lambda s: s.start,
                           reverse=True)
    # Primary sort: price.
    subscriptions.sort(key=attrgetter('price'),
                       reverse=True)
    return subscriptions[0]
