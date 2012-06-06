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

from django.core.urlresolvers import reverse
from django.http import Http404
from localtv.models import NewsletterSettings, SiteSettings, Video
import mock
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.approve_reject_views import (approve_video,
                                                       feature_video,
                                                       _video_limit_wrapper,
                                                       approve_all)
from mirocommunity_saas.admin.design_views import newsletter_settings
from mirocommunity_saas.admin.livesearch_views import approve
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


class VideoLimitWrapperTestCase(BaseTestCase):
    """
    Tests that the VideoLimitWrapper (used on the approve_video and
    feature_video views) works as it should.

    """
    def setUp(self):
        BaseTestCase.setUp(self)
        self.mock = mock.MagicMock(__name__='function')
        self.view = _video_limit_wrapper(self.mock)

    def test_passthrough(self):
        """
        If the video is already active, then the underlying view should be
        called.

        """
        video = self.create_video(status=Video.ACTIVE)
        request = self.factory.get('/', {'video_id': video.pk})
        response = self.view(request)
        self.assertTrue(self.mock.called)

    def test_no_limit(self):
        """
        If the video is not yet active, and there is no limit, then the
        original view should be called.

        """
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk})
        response = self.view(request)
        self.assertTrue(self.mock.called)

    def test_below_limit(self):
        """
        If the video is not yet active, and the limit hasn't been reached,
        then the original view should be called.

        """
        tier = self.create_tier(video_limit=100)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk})
        response = self.view(request)
        self.assertTrue(self.mock.called)

    def test_below_limit__exact(self):
        """
        If the video is not yet active, and there is still space for exactly
        one more video, then the original view should be called.

        """
        tier = self.create_tier(video_limit=1)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk})
        response = self.view(request)
        self.assertTrue(self.mock.called)

    def test_at_limit(self):
        """
        If the video is not yet active, and the limit has been reached, then
        the original view shouldn't be called, and we should get a 402
        response.

        """
        tier = self.create_tier(video_limit=0)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk})
        response = self.view(request)
        self.assertFalse(self.mock.called)
        self.assertEqual(response.status_code, 402)

    def test_no_tier(self):
        """
        If no tier object exists, then a 404 should be raised.
        """
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk})
        with self.assertRaises(Http404):
            self.view(request)
        self.assertFalse(self.mock.called)


class ApproveAllTestCase(BaseTestCase):
    def setUp(self):
        self.user = self.create_user(username='admin')
        settings = SiteSettings.objects.get_current()
        settings.admins.add(self.user)
        BaseTestCase.setUp(self)
        self.create_video(status=Video.UNAPPROVED)
        self.create_video(status=Video.UNAPPROVED)
        self.create_video(status=Video.UNAPPROVED)
        patcher = mock.patch('mirocommunity_saas.admin.approve_reject_views.'
                             '_approve_all')
        self.approve_all = patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_tier(self):
        """
        Should 404 nicely if there's no tier and not call the underlying view.

        """
        request = self.factory.get('/', user=self.user)
        self.assertRaises(Http404, approve_all, request)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(), 3)
        self.assertFalse(self.approve_all.called)

    def test_no_limit(self):
        """
        If there's no limit, the underlying view should be called.

        """
        request = self.factory.get('/', user=self.user)
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)

        approve_all(request)
        self.approve_all.assert_called_with(request)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(), 3)

    def test_below_limit(self):
        """
        If the limit hasn't been reached, the underlying view should be
        called.

        """
        request = self.factory.get('/', user=self.user)
        tier = self.create_tier(video_limit=100)
        self.create_tier_info(tier)

        approve_all(request)
        self.approve_all.assert_called_with(request)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(), 3)

    def test_below_limit__exact(self):
        """
        If the number of videos remaining is exactly equal to the space left,
        the underlying view should be called.

        """
        request = self.factory.get('/', user=self.user)
        tier = self.create_tier(video_limit=3)
        self.create_tier_info(tier)

        approve_all(request)
        self.approve_all.assert_called_with(request)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(), 3)

    def test_above_limit(self):
        """
        If the limit has been reached, we should get a 402 and the
        underlying view shouldn't be called.

        """
        request = self.factory.get('/', user=self.user)
        tier = self.create_tier(video_limit=0)
        self.create_tier_info(tier)

        response = approve_all(request)
        self.assertFalse(self.approve_all.called)
        self.assertEqual(response.status_code, 402)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED
                                     ).count(), 3)

    def test_pagination_exception(self):
        """
        If an error is raised during pagination, then the underlying view
        should be called.

        """
        request = self.factory.get('/', user=self.user)
        tier = self.create_tier(video_limit=0)
        self.create_tier_info(tier)
        with mock.patch('localtv.admin.approve_reject_views.Paginator.page',
                        side_effect=Exception):
            approve_all(request)
        self.approve_all.assert_called_with(request)


class LiveSearchTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        self.user = self.create_user(username='admin')
        settings = SiteSettings.objects.get_current()
        settings.admins.add(self.user)

    def test_approve__no_tier(self):
        """
        If there's no tier object, we should get a 404.

        """
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch('mirocommunity_saas.admin.livesearch_views.'
                        'LiveSearchApproveVideoView.get') as get:
            with self.assertRaises(Http404):
                approve(request)
            self.assertFalse(get.called)

    def test_approve__no_limit(self):
        """
        If there's no limit, the underlying view should be called.

        """
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch('mirocommunity_saas.admin.livesearch_views.'
                        'LiveSearchApproveVideoView.get') as get:
            approve(request)
            self.assertTrue(get.called)

    def test_approve__below_limit(self):
        """
        If limit hasn't been reached, the underlying view should be called.

        """
        tier = self.create_tier(video_limit=100)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch('mirocommunity_saas.admin.livesearch_views.'
                        'LiveSearchApproveVideoView.get') as get:
            approve(request)
            self.assertTrue(get.called)

    def test_approve__below_limit__exact(self):
        """
        If there is exactly one video space left, the underlying view should
        be called.

        """
        tier = self.create_tier(video_limit=1)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch('mirocommunity_saas.admin.livesearch_views.'
                        'LiveSearchApproveVideoView.get') as get:
            approve(request)
            self.assertTrue(get.called)

    def test_approve__above_limit(self):
        """
        If the limit has been reached, the underlying view shouldn't be
        called; instead, we should get a 402.

        """
        tier = self.create_tier(video_limit=0)
        self.create_tier_info(tier)
        video = self.create_video(status=Video.UNAPPROVED)
        request = self.factory.get('/', {'video_id': video.pk},
                                   user=self.user)
        with mock.patch('mirocommunity_saas.admin.livesearch_views.'
                        'LiveSearchApproveVideoView.get') as get:
            response = approve(request)
            self.assertFalse(get.called)


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

    def test_set_default__no_custom(self):
        """
        If custom themes are not allowed, only "bundled" themes can be
        selected as default.

        """
        index_url = reverse('uploadtemplate-index')
        theme1 = self.create_theme(name='Theme1', bundled=False)
        theme2 = self.create_theme(name='Theme2', bundled=True)

        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)

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

    def test_set_default__custom(self):
        """
        If custom themes are not allowed, both "bundled" and "non-bundled"
        themes can be selected as default.

        """
        index_url = reverse('uploadtemplate-index')
        theme1 = self.create_theme(name='Theme1', bundled=False)
        theme2 = self.create_theme(name='Theme2', bundled=True)

        tier = self.create_tier(custom_themes=True)
        self.create_tier_info(tier)

        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_default)
        url = reverse('uploadtemplate-set-default', args=(theme1.pk,))
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_default(), theme1)

        url = reverse('uploadtemplate-set-default', args=(theme2.pk,))
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_default(), theme2)


class FlatPagesTestCase(BaseTestCase):
    def test_admin(self):
        """
        Tests that the flatpages admin is only accessible if the tier allows
        it.

        """
        url = reverse('localtv_admin_flatpages')
        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        self.client.logout()
        tier.custom_themes = True
        tier.save()
        self.assertRequiresAuthentication(url)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
