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

from django.core import mail
from django.test.utils import override_settings
from mock import patch
from paypal.standard.ipn.models import PayPalIPN
from paypal.standard.ipn.signals import (payment_was_successful,
                                         payment_was_flagged,
                                         subscription_signup,
                                         subscription_modify,
                                         subscription_cancel,
                                         subscription_eot)

from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.tiers import (set_tier_by_payment,
                                            payment_handler,
                                            expiration_handler,
                                            record_new_ipn)


@override_settings(ADMINS=(('Admin', 'admin@localhost'),))
class SetTierByPaymentTestCase(BaseTestCase):
    def setUp(self):
        patcher = patch('mirocommunity_saas.utils.tiers.enforce_tier')
        self._enforce_tier = patcher.start()
        self.addCleanup(patcher.stop)
        self.tiers = {
            20: self.create_tier(price=20, slug='tier20'),
            30: self.create_tier(price=30, slug='tier30')
        }
        self.tier_info = self.create_tier_info(self.tiers[20],
                                          available_tiers=self.tiers.values())

    def test_no_change(self):
        """Nothing should happen if the payment matches the current tier."""
        tier = self.tiers[20]
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.tier_info.tier, tier)

        set_tier_by_payment(tier.price)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier.called)

    def test_valid_change(self):
        """
        If the change is valid, the tier should change and be enforced, and
        admins should be notified.

        """
        tier = self.tiers[30]
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotEqual(self.tier_info.tier, tier)

        set_tier_by_payment(tier.price)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self._enforce_tier.assert_called_with(tier)

    def test_invalid_change(self):
        """
        If the change is invalid, nothing should happen other than notifying
        the site devs.

        """
        tier = self.tier_info.tier
        self.assertEqual(len(mail.outbox), 0)

        set_tier_by_payment(40)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier.called)

        duplicate_tier = self.create_tier(price=30, slug='tier30-2')
        self.tier_info.available_tiers.add(duplicate_tier)

        set_tier_by_payment(30)

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier.called)


class PaymentHandlerTestCase(BaseTestCase):
    def test_receiver(self):
        """
        payment_handler should be a receiver for payment_was_successful.
        """
        self.assertTrue(payment_handler in
                        payment_was_successful._live_receivers(None))

    def test(self):
        """
        Successful payments should simply call set_tier_by_payment with the
        amount paid.

        """
        ipn = self.create_ipn(mc_gross=20)
        with patch('mirocommunity_saas.utils.tiers.'
                   'set_tier_by_payment') as mock:
            payment_handler(ipn)
            mock.assert_called_with(20)


class ExpirationHandlerTestCase(BaseTestCase):
    def setUp(self):
        patcher = patch('mirocommunity_saas.utils.tiers.set_tier_by_payment')
        self._set_tier_by_payment = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('mirocommunity_saas.utils.tiers.record_new_ipn')
        self._record_new_ipn = patcher.start()
        self.addCleanup(patcher.stop)

    def test_receiver(self):
        """expiration_handler should be a receiver for subscription_eot"""
        self.assertTrue(expiration_handler in
                        subscription_eot._live_receivers(None))

    def test_flagged(self):
        """
        If the ipn is flagged, the tier shouldn't be set, but the new ipn
        should be recorded.

        """
        ipn = self.create_ipn(flag=True)
        expiration_handler(ipn)
        self.assertFalse(self._set_tier_by_payment.called)
        self._record_new_ipn.assert_called_with(ipn)

    def test_active_subscription(self):
        """
        If the new ipn (an expiration) leaves the subscriber with an active
        subscription, they may have started a new subscription already; we
        shouldn't do anything. (Except, of course, record the ipn.)

        """
        ipn = self.create_ipn()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)
        with patch.object(tier_info, 'get_current_subscription',
                          return_value=(object(), None)):
            expiration_handler(ipn)
        self.assertFalse(self._set_tier_by_payment.called)
        self._record_new_ipn.assert_called_with(ipn)

    def test_no_problems(self):
        """
        If the new ipn isn't flagged and doesn't leave the subscriber with an
        active subscription, they should be set to the free tier.

        """
        ipn = self.create_ipn()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)
        with patch.object(tier_info, 'get_current_subscription',
                          return_value=(None, None)):
            expiration_handler(ipn)
        self._record_new_ipn.assert_called_with(ipn)
        self._set_tier_by_payment.assert_called_with(0)


class RecordNewIpnTestCase(BaseTestCase):
    def test_receiver(self):
        """
        record_new_ipn should be a receiver for every relevant ipn signal
        except for subscription_eot - that's part of expiration_handler.

        """
        for signal in (payment_was_successful, payment_was_flagged,
                       subscription_cancel, subscription_modify,
                       subscription_signup):
            self.assertTrue(record_new_ipn in signal._live_receivers(None))
        self.assertFalse(record_new_ipn in
                         subscription_eot._live_receivers(None))

    def test(self):
        ipn = self.create_ipn(txn_type="subscr_signup")
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)
        self.assertEqual(tier_info.subscription, (None, None))
        record_new_ipn(ipn)
        self.assertEqual(ipn, tier_info.ipn_set.all()[0])
        self.assertEqual(tier_info.subscription, (ipn, None))
