
from django.core.urlresolvers import reverse
from django.http import Http404
from localtv.models import SiteSettings, Video
import mock
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.approve_reject_views import (_video_limit_wrapper,
                                                           approve_all)
from mirocommunity_saas.admin.livesearch_views import approve
from mirocommunity_saas.tests import BaseTestCase


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
        self.view(request)
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
        self.view(request)
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
        self.view(request)
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
        self.view(request)
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
            approve(request)
            self.assertFalse(get.called)


class ThemeTestCase(BaseTestCase):
    def test_get(self):
        """
        If custom themes are disallowed, all uploadtemplate paths should 404
        for GET requests.

        """
        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)
        theme = self.create_theme()
        urls = (
            reverse('uploadtemplate-index'),
            reverse('uploadtemplate-create'),
            reverse('uploadtemplate-update', kwargs={'pk': theme.pk}),
            reverse('uploadtemplate-delete', args=(theme.pk,)),
            reverse('uploadtemplate-unset_default'),
            reverse('uploadtemplate-set_default', args=(theme.pk,))
        )
        incorrect = ()
        for url in urls:
            response = self.client.get(url)
            if response.status_code != 404:
                incorrect += ((url, response.status_code))
        if incorrect:
            raise AssertionError("Incorrect responses:\n{incorrect}".format(incorrect=incorrect))

    def test_create__custom(self):
        """
        POST requests to the create view should work if custom themes are allowed.

        """
        index_url = reverse('uploadtemplate-index')
        tier = self.create_tier(custom_themes=True)
        self.create_tier_info(tier)
        url = reverse('uploadtemplate-create')
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')

        self.assertEqual(Theme.objects.count(), 0)
        response = self.client.post(url, {'name': 'theme'})
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.count(), 1)

    def test_create__no_custom(self):
        """
        POST requests to the create view should 404 if custom themes are not allowed.

        """
        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)
        url = reverse('uploadtemplate-create')
        # If this works, we can't check whether auth is required.
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')

        self.assertEqual(Theme.objects.count(), 0)
        response = self.client.post(url, {'name': 'theme'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Theme.objects.count(), 0)

    def test_update__custom(self):
        """
        POST requests to the create view should work if custom themes are allowed.

        """
        index_url = reverse('uploadtemplate-index')
        tier = self.create_tier(custom_themes=True)
        self.create_tier_info(tier)
        theme = self.create_theme(name='theme1')
        url = reverse('uploadtemplate-update', kwargs={'pk': theme.pk})
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')

        response = self.client.post(url, {'name': 'theme2'})
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get(pk=theme.pk).name, 'theme2')

    def test_update__no_custom(self):
        """
        POST requests to the create view should 404 if custom themes are not allowed.

        """
        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)
        theme = self.create_theme(name='theme1')
        url = reverse('uploadtemplate-update', kwargs={'pk': theme.pk})
        # If this works, we can't check whether auth is required.
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')

        response = self.client.post(url, {'name': 'theme2'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Theme.objects.get(pk=theme.pk).name, 'theme1')

    def test_set_default__no_custom(self):
        """
        If custom themes are not allowed, no themes can be selected.

        """
        theme = self.create_theme()

        tier = self.create_tier(custom_themes=False)
        self.create_tier_info(tier)

        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_current)
        url = reverse('uploadtemplate-set_default', args=(theme.pk,))
        # If this works, we can't check whether auth is required.
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_current)

    def test_set_default__custom(self):
        """
        If custom themes are allowed, themes can be selected as default.

        """
        index_url = reverse('uploadtemplate-index')
        theme = self.create_theme(name='Theme1')

        tier = self.create_tier(custom_themes=True)
        self.create_tier_info(tier)

        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_current)
        url = reverse('uploadtemplate-set_default', args=(theme.pk,))
        self.assertRequiresAuthentication(url)
        self.create_user(username='admin', password='admin',
                         is_superuser=True)
        self.client.login(username='admin', password='admin')
        response = self.client.get(url)
        self.assertRedirects(response, index_url)
        self.assertEqual(Theme.objects.get_current(), theme)


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
