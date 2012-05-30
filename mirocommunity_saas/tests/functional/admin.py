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

from StringIO import StringIO
import zipfile

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from localtv.models import NewsletterSettings, SiteSettings, Video
import mock
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.approve_reject_views import (approve_video,
                                                           feature_video,
                                                           approve_all)
from mirocommunity_saas.admin.livesearch_views import approve
from mirocommunity_saas.admin.design_views import newsletter_settings
from mirocommunity_saas.tests.base import BaseTestCase


class NewsletterAdminTestCase(BaseTestCase):
    def setUp(self):
        """Make sure that a newsletter exists."""
        settings = SiteSettings.objects.get_current()
        NewsletterSettings.objects.create(site_settings=settings,
                                          status=NewsletterSettings.FEATURED)
        BaseTestCase.setUp(self)

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

        response = newsletter_settings(request)
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


class ThemeTestCase(BaseTestCase):
    def create_theme_zip(self, name="Test", description="Test description."):
        """
        Creates a zipped theme with the given name and description.
        """
        theme = StringIO()
        theme_zip = zipfile.ZipFile(theme, 'w')
        theme_zip.writestr('meta.ini', """
[Theme]
name={name}
description={description}
""".format(name=name, description=description))
        theme_zip.close()
        theme.name = 'theme.zip'
        return theme

    def create_theme(self, name='Test', site_id=settings.SITE_ID,
                     description='Test description', **kwargs):
        return Theme.objects.create(name=name, site_id=site_id,
                                    description=description, **kwargs)

    def test_upload(self):
        """
        If themes are not allowed, uploading a theme should give a 403 error;
        otherwise, it should go through.

        """
        url = reverse('uploadtemplate-index')
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')

        theme = self.create_theme_zip()

        self.assertEqual(Theme.objects.count(), 0)

        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)
        theme.seek(0)
        response = self.client.post(url, {'theme': theme})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Theme.objects.count(), 0)

        tier.custom_themes = True
        tier.save()
        theme.seek(0)
        response = self.client.post(url, {'theme': theme})
        self.assertRedirects(response, url)
        self.assertEqual(Theme.objects.count(), 1)

    def test_set_default(self):
        """
        If custom themes are not allowed, only "bundled" themes can be
        selected as default.

        """
        index_url = reverse('uploadtemplate-index')
        theme1 = self.create_theme(name='Theme1', bundled=False)
        theme2 = self.create_theme(name='Theme2', bundled=True)

        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)

        # If custom themes are disabled, only the bundled theme can be set as
        # default.
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_default)
        url = reverse('uploadtemplate-set-default', args=(theme1.pk,))
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_default)

        url = reverse('uploadtemplate-set-default', args=(theme2.pk,))
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_default(), theme2)

        # Otherwise, either theme can be set as default.
        tier.custom_themes = True
        tier.save()
        Theme.objects.set_default(None)
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_default)
        url = reverse('uploadtemplate-set-default', args=(theme1.pk,))
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_default(), theme1)

        url = reverse('uploadtemplate-set-default', args=(theme2.pk,))
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_default(), theme2)
