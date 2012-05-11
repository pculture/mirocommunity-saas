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


"""
This file contains tests of tier-based permissions.

"""

from django.core.exceptions import ValidationError
from django.forms.formsets import TOTAL_FORM_COUNT, INITIAL_FORM_COUNT
from django.forms.models import model_to_dict
from django.http import Http404
from localtv.models import NewsletterSettings, SiteSettings, Video
import mock

from mirocommunity_saas.admin.approve_reject_views import (approve_video,
                                                           feature_video,
                                                           approve_all)
from mirocommunity_saas.admin.forms import (EditSettingsForm, AuthorForm,
                                            VideoFormSet)
from mirocommunity_saas.admin.livesearch_views import approve
from mirocommunity_saas.admin.design_views import newsletter_settings
from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.views import newsletter


class NewsletterTestCase(BaseTestCase):
    def setUp(self):
        """Make sure that a newsletter exists."""
        settings = SiteSettings.objects.get_current()
        NewsletterSettings.objects.create(site_settings=settings,
                                          status=NewsletterSettings.FEATURED)
        BaseTestCase.setUp(self)

    def test_newsletter_view(self):
        """
        The newsletter view should only be accessible if permitted by the
        current tier.

        """
        request = self.factory.get('/')
        self.assertRaises(Http404, newsletter, request)
        tier = self.create_tier(newsletter=True)
        self.create_tier_info(tier)

        response = newsletter(request)
        self.assertEqual(response.status_code, 200)

        tier.newsletter = False
        tier.save()

        self.assertRaises(Http404, newsletter, request)

    def test_newsletter_settings(self):
        """
        The newsletter settings view should only be accessible if permitted
        by the current tier.

        """
        user = self.create_user(username='admin')
        settings = SiteSettings.objects.get_current()
        settings.admins.add(user)

        request = self.factory.get('/', user=user)
        self.assertRaises(Http404, newsletter_settings, request)

        tier = self.create_tier(newsletter=True)
        self.create_tier_info(tier)

        response = newsletter(request)
        self.assertEqual(response.status_code, 200)

        tier.newsletter = False
        tier.save()

        self.assertRaises(Http404, newsletter_settings, request)


class ModerationTestCase(BaseTestCase):
    """Tests related to the moderation queue."""
    def setUp(self):
        self.user = self.create_user(username='admin')
        settings = SiteSettings.objects.get_current()
        settings.admins.add(self.user)
        BaseTestCase.setUp(self)

    @classmethod
    def setUpClass(cls):
        cls._disable_index_updates()
        super(ModerationTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._enable_index_updates()
        super(ModerationTestCase, cls).tearDownClass()

    def test_approve_video(self):
        # make sure the view works if the video doesn't trigger the tiers
        # code.
        video = self.create_video(status=Video.ACTIVE)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = approve_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # Okay, now the base case: it is allowed.
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = approve_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit hasn't been reached, it should go through.
        tier.video_limit = 100
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = approve_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit has been reached, shouldn't go through.
        tier.video_limit = 0
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = approve_video(request)
        self.assertEqual(response.status_code, 402)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.UNAPPROVED)

        # And if there's no tier object?
        tier.delete()
        self.assertRaises(Http404, approve_video, request)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.UNAPPROVED)

    def test_feature_video(self):
        # make sure the view works if the video doesn't trigger the tiers
        # code.
        video = self.create_video(status=Video.ACTIVE)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = feature_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If there's no limit, it should go through.
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = feature_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit hasn't been reached, it should go through.
        tier.video_limit = 100
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = feature_video(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit has been reached, shouldn't go through.
        tier.video_limit = 0
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        response = feature_video(request)
        self.assertEqual(response.status_code, 402)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.UNAPPROVED)

        # And if there's no tier object?
        tier.delete()
        self.assertRaises(Http404, feature_video, request)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.UNAPPROVED)

    def test_approve_all(self):
        self.create_video(status=Video.UNAPPROVED)
        self.create_video(status=Video.UNAPPROVED)
        self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', user=self.user)

        # Should 404 nicely if there's no tier.
        self.assertRaises(Http404, approve_all, request)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(),
                         3)

        # If there's no video limit, let it through.
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)

        response = approve_all(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Video.objects.filter(status=Video.ACTIVE).count(), 3)
        Video.objects.all().update(status=Video.UNAPPROVED)


        # If the limit hasn't been reached, it should go through.
        tier.video_limit = 100
        tier.save()
        response = approve_all(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Video.objects.filter(status=Video.ACTIVE).count(), 3)
        Video.objects.all().update(status=Video.UNAPPROVED)

        # If the limit has been reached, shouldn't go through.
        tier.video_limit = 0
        tier.save()
        response = approve_all(request)
        self.assertEqual(response.status_code, 402)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(),
                         3)


class LiveSearchTestCase(BaseTestCase):
    def setUp(self):
        self.user = self.create_user(username='admin')
        settings = SiteSettings.objects.get_current()
        settings.admins.add(self.user)
        BaseTestCase.setUp(self)

    @classmethod
    def setUpClass(cls):
        cls._disable_index_updates()
        super(LiveSearchTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._enable_index_updates()
        super(LiveSearchTestCase, cls).tearDownClass()

    def test_approve(self):
        # For these tests, we mock get_object to simply return the relevant
        # video, and we mock form so that it seems valid. This lets us
        # avoid dealing with setting up sessions etc. when that's not what
        # we're testing here.
        mock_path = 'mirocommunity_saas.admin.livesearch_views.LiveSearchApproveVideoView.get_object'
        mock_path_2 = 'mirocommunity_saas.admin.livesearch_views.LiveSearchApproveVideoView.form'
        # 404 if there's no tier object.
        video = self.create_video(status=Video.ACTIVE)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch(mock_path, return_value=video):
            with mock.patch(mock_path_2, create=True):
                self.assertRaises(Http404, approve, request)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # Okay, now the base case: it is allowed.
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch(mock_path, return_value=video):
            with mock.patch(mock_path_2, create=True):
                response = approve(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit hasn't been reached, it should go through.
        tier.video_limit = 100
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch(mock_path, return_value=video):
            with mock.patch(mock_path_2, create=True):
                response = approve(request)
        self.assertEqual(response.status_code, 200)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.ACTIVE)

        # If the limit has been reached, shouldn't go through.
        tier.video_limit = 0
        tier.save()
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch(mock_path, return_value=video):
            with mock.patch(mock_path_2, create=True):
                response = approve(request)
        self.assertEqual(response.status_code, 402)
        video = Video.objects.get(pk=video.pk)
        self.assertEqual(video.status, Video.UNAPPROVED)


class FormTestCase(BaseTestCase):
    def test_settings_form(self):
        """
        The settings form shouldn't allow css to be submitted if it's
        disallowed.

        """
        site_settings = SiteSettings.objects.get_current()
        data = {'css': 'hi'}
        tier = self.create_tier(custom_css=False)
        self.create_tier_info(tier)

        form = EditSettingsForm(data, instance=site_settings)
        form.cleaned_data = data
        self.assertRaises(ValidationError, form.clean_css)

        form.instance.css = data['css']
        self.assertEqual(form.clean_css(), data['css'])

        tier.custom_css = True
        tier.save()

        form = EditSettingsForm(data, instance=site_settings)
        form.cleaned_data = data
        self.assertEqual(form.clean_css(), data['css'])

    def test_author_form(self):
        """The author form should respect tier limits."""
        site_settings = SiteSettings.objects.get_current()
        tier = self.create_tier(admin_limit=1)
        self.create_tier_info(tier)
        user = self.create_user(username='user', is_active=True)
        admin = self.create_user(username='admin', is_active=True)
        old_admin = self.create_user(username='admin2', is_active=False)
        superuser = self.create_user(username='superuser', is_active=True,
                                     is_superuser=True)
        old_superuser = self.create_user(username='superuser2',
                                         is_active=False, is_superuser=True)
        site_settings.admins.add(admin)
        site_settings.admins.add(old_admin)
        site_settings.admins.add(superuser)
        site_settings.admins.add(old_superuser)

        # Even if no admins are allowed, user role can be set.
        form = AuthorForm({'role': 'user'}, instance=user)
        form.cleaned_data = {'role': 'user'}
        self.assertEqual(form.clean_role(), 'user')

        # Even if no admins are allowed, anyone who is an admin can stay
        # that way (as far as this form is concerned.)
        form = AuthorForm({'role': 'admin'}, instance=user,
                          initial={'role': 'admin'})
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')

        # If they're not an admin and there isn't room, it's a validation
        # error.
        form = AuthorForm({'role': 'admin'}, instance=user)
        form.cleaned_data = {'role': 'admin'}
        self.assertRaises(ValidationError, form.clean_role)

        # Admin assignment is allowed if there's room.
        tier.admin_limit = 2
        tier.save()
        form = AuthorForm({'role': 'admin'}, instance=user)
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')

        tier.admin_limit = None
        tier.save()
        form = AuthorForm({'role': 'admin'}, instance=user)
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')

    def test_video_form_set(self):
        """The bulk edit video form should respect tier limits."""
        self._disable_index_updates()
        for i in range(3):
            self.create_video(status=Video.UNAPPROVED,
                              name='video{0}'.format(i),
                              file_url='http://google.com/{0}'.format(i))

        prefix = 'pfx'
        default = {
            '{0}-{1}'.format(prefix, TOTAL_FORM_COUNT): 4,
            '{0}-{1}'.format(prefix, INITIAL_FORM_COUNT): 3
        }
        qs = Video.objects.all()

        for i, v in enumerate(list(qs) + [Video()]):
            default.update(dict(('{0}-{1}-{2}'.format(prefix, i, k), v)
                                for k, v in model_to_dict(v).iteritems()))
            default['{0}-{1}-{2}'.format(prefix, i, 'BULK')] = True

        approve_data = {'bulk_action': 'feature'}
        feature_data = {'bulk_action': 'approve'}
        approve_data.update(default)
        feature_data.update(default)

        # Should go through if there's no limit.
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)

        for data in [approve_data, feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=prefix)
            self.assertTrue(formset.is_valid())
            self.assertTrue(all(form.instance.status == Video.ACTIVE
                                for form in formset.initial_forms))

        # Should go through if the limit is high enough.
        tier.video_limit = 3
        tier.save()

        for data in [approve_data, feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=prefix)
            self.assertTrue(formset.is_valid())
            self.assertTrue(all(form.instance.status == Video.ACTIVE
                                for form in formset.initial_forms))

        # Should fail if there are not enough slots left.
        tier.video_limit = 2
        tier.save()

        for data in [approve_data, feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=prefix)
            self.assertFalse(formset.is_valid())

        self._enable_index_updates()
