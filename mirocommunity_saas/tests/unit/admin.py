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

from django.http import Http404
import mock

from mirocommunity_saas.admin.forms import (TierChangeForm,
                                            DowngradeConfirmationForm,
                                            PayPalCancellationForm,
                                            PayPalSubscriptionForm)
from mirocommunity_saas.admin.views import (TierView, TierChangeView,
                                            DowngradeConfirmationView)
from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.tiers import make_tier_change_token


class TierViewUnitTestCase(BaseTestCase):
    def setUp(self):
        super(TierViewUnitTestCase, self).setUp()
        self.tier1 = self.create_tier(name='Tier1', slug='tier1', price=0)
        self.tier2 = self.create_tier(name='Tier2', slug='tier2', price=20)
        self.tier3 = self.create_tier(name='Tier3', slug='tier3', price=40)

    def test_get_context_data__tier1(self):
        """
        Context data should include forms for the higher tiers which are not
        paypal-based.

        """
        tier_info = self.create_tier_info(self.tier1,
                                          available_tiers=[self.tier2,
                                                           self.tier3],
                                          enforce_payments=False)
        context_data = TierView().get_context_data()
        self.assertEqual(context_data['tier_info'], tier_info)
        forms = context_data['forms']
        self.assertEqual(forms.keys()[0], self.tier1)
        self.assertEqual(forms.keys()[1], self.tier2)
        self.assertEqual(forms.keys()[2], self.tier3)
        self.assertTrue(forms.values()[0] is None)
        self.assertIsInstance(forms.values()[1], TierChangeForm)
        self.assertIsInstance(forms.values()[2], TierChangeForm)

    def test_get_context_data__tier1__enforced(self):
        """
        Context data should include forms for the higher tiers which are
        paypal-based.

        """
        tier_info = self.create_tier_info(self.tier1,
                                          available_tiers=[self.tier2,
                                                           self.tier3],
                                          enforce_payments=True)
        context_data = TierView().get_context_data()
        self.assertEqual(context_data['tier_info'], tier_info)
        forms = context_data['forms']
        self.assertEqual(forms.keys()[0], self.tier1)
        self.assertEqual(forms.keys()[1], self.tier2)
        self.assertEqual(forms.keys()[2], self.tier3)
        self.assertTrue(forms.values()[0] is None)
        self.assertIsInstance(forms.values()[1], PayPalSubscriptionForm)
        self.assertIsInstance(forms.values()[2], PayPalSubscriptionForm)

    def test_get_context_data__tier2(self):
        """
        If the tier2 is selected, the context data should include a downgrade
        confirmation form for tier1 and a tier change form for tier3.

        """
        tier_info = self.create_tier_info(self.tier2,
                                          available_tiers=[self.tier1,
                                                           self.tier3],
                                          enforce_payments=False)
        context_data = TierView().get_context_data()
        self.assertEqual(context_data['tier_info'], tier_info)
        forms = context_data['forms']
        self.assertEqual(forms.keys()[0], self.tier1)
        self.assertEqual(forms.keys()[1], self.tier2)
        self.assertEqual(forms.keys()[2], self.tier3)
        self.assertIsInstance(forms.values()[0], DowngradeConfirmationForm)
        self.assertTrue(forms.values()[1] is None)
        self.assertIsInstance(forms.values()[2], TierChangeForm)

    def test_get_context_data__tier2__enforced(self):
        """
        If the tier2 is selected and payments are enforced, the context data
        should include a downgrade confirmation form for tier1 and a tier
        change form for tier3.

        """
        tier_info = self.create_tier_info(self.tier2,
                                          available_tiers=[self.tier1,
                                                           self.tier3],
                                          enforce_payments=True)
        context_data = TierView().get_context_data()
        self.assertEqual(context_data['tier_info'], tier_info)
        forms = context_data['forms']
        self.assertEqual(forms.keys()[0], self.tier1)
        self.assertEqual(forms.keys()[1], self.tier2)
        self.assertEqual(forms.keys()[2], self.tier3)
        self.assertIsInstance(forms.values()[0], DowngradeConfirmationForm)
        self.assertTrue(forms.values()[1] is None)
        self.assertIsInstance(forms.values()[2], PayPalSubscriptionForm)

    def test_get_context_data__tier3(self):
        """
        If the tier3 is selected, the context data should include a downgrade
        confirmation form for tier1 and tier2.

        """
        tier_info = self.create_tier_info(self.tier3,
                                          available_tiers=[self.tier1,
                                                           self.tier2],
                                          enforce_payments=True)
        context_data = TierView().get_context_data()
        self.assertEqual(context_data['tier_info'], tier_info)
        forms = context_data['forms']
        self.assertEqual(forms.keys()[0], self.tier1)
        self.assertEqual(forms.keys()[1], self.tier2)
        self.assertEqual(forms.keys()[2], self.tier3)
        self.assertIsInstance(forms.values()[0], DowngradeConfirmationForm)
        self.assertIsInstance(forms.values()[1], DowngradeConfirmationForm)
        self.assertTrue(forms.values()[2] is None)


class DowngradeConfirmationViewUnitTestCase(BaseTestCase):
    def setUp(self):
        super(DowngradeConfirmationViewUnitTestCase, self).setUp()
        self.tier1 = self.create_tier(name='Tier1', slug='tier1', price=0)
        self.tier2 = self.create_tier(name='Tier2', slug='tier2', price=20)
        self.tier_info = self.create_tier_info(self.tier2,
                                               available_tiers=[self.tier1])

    def test_get_context_data__bad_slug(self):
        """
        If the slug doesn't represent an available tier, a 404 should be
        raised.

        """
        tier3 = self.create_tier(name='Tier3', slug='tier3', price=10)
        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier3'})
        self.assertRaises(Http404, view.get_context_data)

    def test_get_context_data__bad_price(self):
        """
        If the tier isn't a downgrade, a 404 should be raised.

        """
        tier3 = self.create_tier(name='Tier3', slug='tier3', price=40)
        self.tier_info.available_tiers.add(tier3)
        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier3'})
        self.assertRaises(Http404, view.get_context_data)

    def test_get_context_data(self):
        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier1'})
        data = view.get_context_data()
        self.assertIsInstance(data.get('form'), TierChangeForm)
        self.assertEqual(data.get('tier'), self.tier1)
        self.assertEqual(data.get('tier_info'), self.tier_info)
        self.assertIsInstance(data.get('admins_to_demote'), list)
        self.assertIsInstance(data.get('videos_to_deactivate'), list)
        self.assertIsInstance(data.get('have_theme'), bool)

    def test_get_context_data__enforced(self):
        """
        If payments are enforced, a paypal-based form should be used.
        """
        self.tier_info.enforce_payments = True
        self.tier_info.save()
        self.tier1.price = 10
        self.tier1.save()

        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier1'})
        data = view.get_context_data()
        self.assertIsInstance(data.get('form'), PayPalSubscriptionForm)
        self.assertEqual(data.get('tier'), self.tier1)
        self.assertEqual(data.get('tier_info'), self.tier_info)
        self.assertIsInstance(data.get('admins_to_demote'), list)
        self.assertIsInstance(data.get('videos_to_deactivate'), list)
        self.assertIsInstance(data.get('have_theme'), bool)

    def test_get_context_data__enforced__cancellation(self):
        """
        If payments are enforced, a paypal-based form should be used.
        """
        self.tier_info.enforce_payments = True
        self.tier_info.save()
        self.tier_info._subscription = self.create_ipn()

        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier1'})
        data = view.get_context_data()
        self.assertIsInstance(data.get('form'), PayPalCancellationForm)
        self.assertEqual(data.get('tier'), self.tier1)
        self.assertEqual(data.get('tier_info'), self.tier_info)
        self.assertIsInstance(data.get('admins_to_demote'), list)
        self.assertIsInstance(data.get('videos_to_deactivate'), list)
        self.assertIsInstance(data.get('have_theme'), bool)

    def test_get_context_data__enforced__cancellation__no_subscription(self):
        """
        If payments are enforced, but there is no active subscription, a
        non-paypal-based form should be used.
        """
        self.tier_info.enforce_payments = True
        self.tier_info.save()

        view = DowngradeConfirmationView()
        view.request = self.factory.get('/', data={'tier': 'tier1'})
        data = view.get_context_data()
        self.assertIsInstance(data.get('form'), TierChangeForm)
        self.assertEqual(data.get('tier'), self.tier1)
        self.assertEqual(data.get('tier_info'), self.tier_info)
        self.assertIsInstance(data.get('admins_to_demote'), list)
        self.assertIsInstance(data.get('videos_to_deactivate'), list)
        self.assertIsInstance(data.get('have_theme'), bool)


class TierChangeViewTestCase(BaseTestCase):
    def setUp(self):
        super(TierChangeViewTestCase, self).setUp()
        self.tier1 = self.create_tier(name='Tier1', slug='tier1', price=10)
        self.tier2 = self.create_tier(name='Tier2', slug='tier2', price=20)
        self.tier_changed = datetime.datetime.now()
        self.tier_info = self.create_tier_info(self.tier2,
                                               available_tiers=[self.tier1],
                                               tier_changed=self.tier_changed)

    def test_change_tier__bad_slug(self):
        """
        If the slug given doesn't refer to an available tier, do nothing.

        """
        tier3 = self.create_tier(name='Tier3', slug='tier3', price=30)
        token = make_tier_change_token(tier3)
        view = TierChangeView()
        view.change_tier(tier3.slug, token)
        self.assertEqual(self.tier_info.tier, self.tier2)
        self.assertEqual(self.tier_info.tier_changed, self.tier_changed)

    def test_change_tier__same_id(self):
        """
        If the tier we're changing to is the same as the current tier, do
        nothing.

        """
        token = make_tier_change_token(self.tier2)
        view = TierChangeView()
        view.change_tier(self.tier2.slug, token)
        self.assertEqual(self.tier_info.tier, self.tier2)
        self.assertEqual(self.tier_info.tier_changed, self.tier_changed)

    def test_change_tier__bad_token(self):
        """
        If the token is invalid, do nothing.

        """
        token = ''
        view = TierChangeView()
        view.change_tier(self.tier1.slug, token)
        self.assertEqual(self.tier_info.tier, self.tier2)
        self.assertEqual(self.tier_info.tier_changed, self.tier_changed)

    def test_change_tier(self):
        """
        If everything is right, the tier should be changed and the
        tier_changed date should be set.

        """
        token = make_tier_change_token(self.tier1)
        view = TierChangeView()
        view.change_tier(self.tier1.slug, token)
        self.assertEqual(self.tier_info.tier, self.tier1)
        self.assertNotEqual(self.tier_info.tier_changed, self.tier_changed)

    def test_get(self):
        """
        Calling get should take the slug and token out of the GET params and
        pass them to change_tier, then return the result of the finished()
        method.

        """
        view = TierChangeView()
        request = self.factory.get('/', {'tier': 'tier1', 's': 'token'})
        return_value = object()
        with mock.patch.object(view, 'change_tier') as change_tier:
            with mock.patch.object(view, 'finished',
                                   return_value=return_value) as finished:
                response = view.get(request)
                change_tier.assert_called_with('tier1', 'token')
                finished.assert_called_with()
                self.assertEqual(response, return_value)

    def test_post(self):
        """
        Calling post should take the slug and token out of the POST data and
        pass them to change_tier, then return the result of the finished()
        method.

        """
        view = TierChangeView()
        request = self.factory.post('/', {'tier': 'tier1', 's': 'token'})
        return_value = object()
        with mock.patch.object(view, 'change_tier') as change_tier:
            with mock.patch.object(view, 'finished',
                                   return_value=return_value) as finished:
                response = view.post(request)
                change_tier.assert_called_with('tier1', 'token')
                finished.assert_called_with()
                self.assertEqual(response, return_value)

    def test_finished(self):
        """The finished method should return a redirect to the tier index."""
        response = TierChangeView().finished()
        self.assertRedirects(response, '/admin/upgrade/', '')
