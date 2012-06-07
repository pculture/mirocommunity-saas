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
    def test_handle_form__valid(self):
        """
        The handle form method should instantiate a TierChangeForm and, if
        it's valid, save it.

        """
        tier = self.create_tier()
        self.create_tier_info(tier)
        view = TierChangeView()
        with mock.patch.object(TierChangeForm, 'is_valid',
                               return_value=True) as is_valid:
            with mock.patch.object(TierChangeForm, 'save') as save:
                view.handle_form({'key': 'value'})
                self.assertTrue(is_valid.called)
                self.assertTrue(save.called)

    def test_handle_form__invalid(self):
        """
        The handle form method should instantiate a TierChangeForm and, if
        it's invalid, not save it.

        """
        tier = self.create_tier()
        self.create_tier_info(tier)
        view = TierChangeView()
        with mock.patch.object(TierChangeForm, 'is_valid',
                               return_value=False) as is_valid:
            with mock.patch.object(TierChangeForm, 'save') as save:
                view.handle_form({'key': 'value'})
                self.assertTrue(is_valid.called)
                self.assertFalse(save.called)

    def test_get(self):
        """
        The get method should pass the GET data to the handle_form method,
        then return the result of the finished() method.

        """
        view = TierChangeView()
        data = {'key': 'value', 'token': 'token'}
        request = self.factory.get('/', data)
        return_value = object()
        with mock.patch.object(view, 'handle_form') as handle_form:
            with mock.patch.object(view, 'finished',
                                   return_value=return_value) as finished:
                response = view.get(request)
                handle_form.assert_called_with(request.GET)
                finished.assert_called_with()
                self.assertEqual(response, return_value)

    def test_post(self):
        """
        The post method should pass the POST data to the handle_form method,
        then return the result of the finished() method.

        """
        view = TierChangeView()
        request = self.factory.post('/', {'tier': 'tier1', 'key': 'value'})
        return_value = object()
        with mock.patch.object(view, 'handle_form') as handle_form:
            with mock.patch.object(view, 'finished',
                                   return_value=return_value) as finished:
                response = view.post(request)
                handle_form.assert_called_with(request.POST)
                finished.assert_called_with()
                self.assertEqual(response, return_value)

    def test_finished(self):
        """The finished method should return a redirect to the tier index."""
        response = TierChangeView().finished()
        self.assertRedirects(response, '/admin/upgrade/', '')


class TierChangeFormTestCase(BaseTestCase):
    def setUp(self):
        super(TierChangeFormTestCase, self).setUp()
        self.tier1 = self.create_tier(name='Tier1', slug='tier1', price=10)
        self.tier2 = self.create_tier(name='Tier2', slug='tier2', price=20)
        self.tier_changed = datetime.datetime.now()
        self.tier_info = self.create_tier_info(self.tier2,
                                               available_tiers=[self.tier1],
                                               tier_changed=self.tier_changed)

    def test_bad_slug(self):
        """
        The form should be invalid if the slug given doesn't refer to an
        available tier.

        """
        tier3 = self.create_tier(name='Tier3', slug='tier3', price=30)
        token = make_tier_change_token(tier3)
        form = TierChangeForm({'tier': tier3.slug, 'token': token})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.keys(), ['tier'])

    def test_same_tier(self):
        """
        The form should be invalid if the tier we're changing to is the same
        as the current tier.

        """
        self.assertEqual(self.tier_info.tier, self.tier2)
        token = make_tier_change_token(self.tier2)
        form = TierChangeForm({'tier': self.tier2.slug, 'token': token})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.keys(), ['tier'])

    def test_bad_token(self):
        """
        The form should be invalid if the token is invalid.

        """
        self.assertNotEqual(self.tier_info.tier, self.tier1)
        token = 'not_a_token'
        form = TierChangeForm({'tier': self.tier1.slug, 'token': token})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.keys(), ['__all__'])

    def test_valid(self):
        """
        If everything is right, the form should come back valid.

        """
        token = make_tier_change_token(self.tier1)
        form = TierChangeForm({'tier': self.tier1.slug, 'token': token})
        self.assertTrue(form.is_valid())

    def test_save(self):
        """
        Saving the form should update the last tier changed date and actually
        change the tier.

        """
        token = make_tier_change_token(self.tier1)
        form = TierChangeForm({'tier': self.tier1.slug, 'token': token})
        self.assertTrue(form.is_valid())
        self.assertEqual(self.tier_info.tier, self.tier2)
        old_tier_changed = self.tier_info.tier_changed
        form.save()
        self.assertEqual(self.tier_info.tier, self.tier1)
        self.assertGreater(self.tier_info.tier_changed, old_tier_changed)
