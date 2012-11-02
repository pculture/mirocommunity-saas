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
from paypal.standard.ipn.signals import (payment_was_successful,
                                         payment_was_flagged,
                                         subscription_signup,
                                         subscription_modify,
                                         subscription_cancel,
                                         subscription_eot)

from mirocommunity_saas.models import Tier
from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.tiers import (set_tier,
                                            record_new_ipn)


@override_settings(MANAGERS=(('Manager', 'manager@localhost'),))
class SetTierByPaymentTestCase(BaseTestCase):
    def setUp(self):
        super(SetTierByPaymentTestCase, self).setUp()
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

        set_tier(tier.price)

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

        set_tier(tier.price)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['manager@localhost'])
        self.assertEqual(self.tier_info.tier, tier)
        self._enforce_tier.assert_called_with(tier)

    def test_invalid_change(self):
        """
        If the change is invalid, Tier.DoesNotExist should be raised.

        """
        tier = self.tier_info.tier
        self.assertEqual(len(mail.outbox), 0)

        with self.assertRaises(Tier.DoesNotExist):
            set_tier(40)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier.called)

    def test_duplicate_change(self):
        """
        If the price matches the current tier, Tier.MultipleObjectsReturned
        should be raised.

        """
        tier = self.tier_info.tier
        self.assertEqual(len(mail.outbox), 0)

        duplicate_tier = self.create_tier(price=30, slug='tier30-2')
        self.tier_info.available_tiers.add(duplicate_tier)

        with self.assertRaises(Tier.MultipleObjectsReturned):
            set_tier(30)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.tier_info.tier, tier)
        self.assertFalse(self._enforce_tier.called)


class RecordNewIpnTestCase(BaseTestCase):
    def test_receiver(self):
        """
        record_new_ipn should be a receiver for every relevant ipn signal
        except for subscription_eot - that's part of expiration_handler.

        """
        for signal in (payment_was_successful, payment_was_flagged,
                       subscription_cancel, subscription_modify,
                       subscription_signup, subscription_eot):
            self.assertTrue(record_new_ipn in signal._live_receivers(None))

    def test(self):
        ipn = self.create_ipn(txn_type="subscr_signup")
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)
        self.assertEqual(tier_info.subscription, None)
        record_new_ipn(ipn)
        self.assertEqual(ipn, tier_info.ipn_set.all()[0])
        self.assertEqual(tier_info.subscription.signup_or_modify, ipn)
