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
import mock
from paypal.standard.ipn.models import PayPalIPN
from paypal.standard.ipn.signals import (payment_was_successful,
                                         subscription_eot)

from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.tiers import set_tier_by_payment


@override_settings(ADMINS=(('Admin', 'admin@localhost'),))
class SetTierByPaymentTestCase(BaseTestCase):
    def setUp(self):
        self._enforce_tier_called = False
        self._enforce_tier_tier = None
        def mark_enforce_tier_called(new_tier):
            self._enforce_tier_called = True
            self._enforce_tier_tier = new_tier
        patcher = mock.patch('mirocommunity_saas.utils.tiers.enforce_tier',
                             mark_enforce_tier_called)
        patcher.start()
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
        self.assertFalse(self._enforce_tier_called)
        self.assertTrue(self._enforce_tier_tier is None)

        set_tier_by_payment(tier.price)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier_called)
        self.assertTrue(self._enforce_tier_tier is None)

    def test_valid_change(self):
        """
        If the change is valid, the tier should change and be enforced, and
        admins should be notified.

        """
        tier = self.tiers[30]
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self._enforce_tier_called)
        self.assertTrue(self._enforce_tier_tier is None)
        self.assertNotEqual(self.tier_info.tier, tier)

        set_tier_by_payment(tier.price)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self.assertTrue(self._enforce_tier_called)
        self.assertEqual(self._enforce_tier_tier, tier)

    def test_invalid_change(self):
        """
        If the change is invalid, nothing should happen other than notifying
        the site devs.

        """
        tier = self.tier_info.tier
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self._enforce_tier_called)

        set_tier_by_payment(40)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier_called)
        self.assertTrue(self._enforce_tier_tier is None)

        duplicate_tier = self.create_tier(price=30, slug='tier30-2')
        self.tier_info.available_tiers.add(duplicate_tier)

        set_tier_by_payment(30)

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['admin@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier_called)
        self.assertTrue(self._enforce_tier_tier is None)


class IPNHandlerTestCase(BaseTestCase):
    def setUp(self):
        self._set_tier_by_payment_called = False
        self._set_tier_by_payment_payment = None
        def mark_set_tier_by_payment_called(payment):
            self._set_tier_by_payment_called = True
            self._set_tier_by_payment_payment = payment
        patcher = mock.patch('mirocommunity_saas.utils.tiers.'
                             'set_tier_by_payment',
                             mark_set_tier_by_payment_called)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_payment_handler(self):
        """
        Successful payments should cause set_tier_by_payment to be called.

        """
        ipn = PayPalIPN(mc_gross=20)
        self.assertFalse(self._set_tier_by_payment_called)
        self.assertTrue(self._set_tier_by_payment_payment is None)
        payment_was_successful.send(ipn)
        self.assertTrue(self._set_tier_by_payment_called)
        self.assertEqual(self._set_tier_by_payment_payment, 20)

    def test_expiration_handler(self):
        self.assertFalse(self._set_tier_by_payment_called)
        self.assertTrue(self._set_tier_by_payment_payment is None)

        # If the ipn is flagged, do nothing.
        ipn = PayPalIPN(flag=True)
        subscription_eot.send(ipn)
        self.assertFalse(self._set_tier_by_payment_called)
        self.assertTrue(self._set_tier_by_payment_payment is None)

        # If they have an active subscription even after the expiration, do
        # nothing.
        ipn = PayPalIPN()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)
        with mock.patch.object(tier_info, 'get_current_subscription',
                               return_value=(PayPalIPN(), None)):
            subscription_eot.send(ipn)
        self.assertFalse(self._set_tier_by_payment_called)
        self.assertTrue(self._set_tier_by_payment_payment is None)

        # Otherwise, go through with the downgrade.
        ipn = PayPalIPN()
        with mock.patch.object(tier_info, 'get_current_subscription',
                               return_value=(None, None)):
            subscription_eot.send(ipn)
        self.assertTrue(self._set_tier_by_payment_called)
        self.assertEqual(self._set_tier_by_payment_payment, 0)
