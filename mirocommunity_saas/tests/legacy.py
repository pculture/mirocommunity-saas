"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

import datetime
import mock
import feedparser
from urllib import quote_plus, urlencode
import vidscraper

from django.contrib.auth.models import User
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.test.utils import override_settings
from django.core import mail

from mirocommunity_saas import tiers, zendesk
from mirocommunity_saas.admin import views
from mirocommunity_saas.models import TierInfo
from mirocommunity_saas.management.commands import (
    check_frequently_for_invalid_tiers_state,
    clear_tiers_state,
    nightly_tiers_events,
    send_welcome_email
   )

from localtv.tests.base import BaseTestCase
from localtv.models import Video, SiteSettings, Source, FeedImport

from uploadtemplate.models import Theme


NAME_TO_COST = tiers.Tier.NAME_TO_COST()
PLUS_COST = NAME_TO_COST['plus']
PREMIUM_COST = NAME_TO_COST['premium']
MAX_COST = NAME_TO_COST['max']

class Fakedatetime(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return cls(2011, 2, 20, 12, 35, 0)


class AdministrationBaseTestCase(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        BaseTestCase.setUp(self)
        self.site_settings = SiteSettings.objects.create(
            site_id=settings.SITE_ID)

        self.admin = self.create_user(username='admin',
                                      email='admin@testserver.local')
        self.admin.set_password('admin')
        self.admin.save()
        self.site_settings.admins.add(self.admin)

        self.tier_info = TierInfo.objects.create(
            site_settings=self.site_settings,
            tier_name='max')

        self.enforce_tiers_patch = mock.patch(
            'mirocommunity_saas.models.TierInfo.enforce_tiers',
            mock.Mock(return_value=True))
        self.enforce_tiers_patch.start()
        zendesk.outbox = []

    def tearDown(self):
        self.enforce_tiers_patch.stop()

    def assertRequiresAuthentication(self, url, *args,
                                     **kwargs):
        """
        Assert that the given URL requires the user to be authenticated.

        If additional arguments are passed, they are passed to the Client.get
        method

        If keyword arguments are present, they're passed to Client.login before
        the URL is accessed.

        @param url_or_reverse: the URL to access
        """
        c = Client()

        if kwargs:
            c.login(**kwargs)

        response = c.get(url, *args)
        if args and args[0]:
            url = '%s?%s' % (url, urlencode(args[0]))
        self.assertStatusCodeEquals(response, 302)
        self.assertEqual(response['Location'],
                          'http://%s%s?next=%s' %
                          ('testserver',
                           settings.LOGIN_URL,
                           quote_plus(url, safe='/')))

class ApproveRejectAdministrationTestCase(AdministrationBaseTestCase):

    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos',
                mock.Mock(return_value=0))
    def test_GET_approve_fails_when_over_limit(self):
        video = self.create_video(status=Video.UNAPPROVED)
        url = reverse('localtv_admin_approve_video')
        self.assertRequiresAuthentication(url, {'video_id': video.pk})

        c = Client()
        c.login(username='admin', password='admin')
        response = c.get(url, {'video_id': str(video.pk)},
                         HTTP_REFERER='http://referer.com')
        self.assertStatusCodeEquals(response, 402)

    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos',
                mock.Mock(return_value=0))
    def test_GET_feature_fails_outside_video_limit(self):
        """
        A GET request to the feature_video view should approve the video and
        redirect back to the referrer.  The video should be specified by
        GET['video_id'].  If the video is unapproved, it should become
        approved.
        """
        video = self.create_video(status=Video.UNAPPROVED)
        url = reverse('localtv_admin_feature_video')
        self.assertRequiresAuthentication(url, {'video_id': video.pk})

        c = Client()
        c.login(username='admin', password='admin')
        response = c.get(url, {'video_id': str(video.pk)},
                         HTTP_REFERER='http://referer.com')
        self.assertStatusCodeEquals(response, 402)

class SearchAdministrationTestCase(AdministrationBaseTestCase):

    url = reverse('localtv_admin_search')

    @mock.patch('mirocommunity_saas.tiers.Tier.can_add_more_videos',
                mock.Mock(return_value=False))
    def test_GET_approve_refuses_when_limit_exceeded(self):
        """
        A GET request to the approve view should create a new video object from
        the search and redirect back to the referrer.  The video should be
        removed from subsequent search listings.
        """
        c = Client()
        c.login(username='admin', password='admin')

        response = c.get(reverse('localtv_admin_search_video_approve'),
                         {'q': 'search string',
                          'video_id': 1},
                         HTTP_REFERER="http://www.getmiro.com/")
        self.assertStatusCodeEquals(response, 402)


# ----------------------------------
# Administration tests with tiers
# ----------------------------------

def naysayer(*args, **kwargs):
    return False

class EditSettingsDeniedSometimesTestCase(AdministrationBaseTestCase):

    url = reverse('localtv_admin_settings')

    def setUp(self):
        AdministrationBaseTestCase.setUp(self)
        self.POST_data = {
            'title': self.site_settings.site.name,
            'tagline': self.site_settings.tagline,
            'about_html': self.site_settings.about_html,
            'sidebar_html': self.site_settings.sidebar_html,
            'footer_html': self.site_settings.footer_html,
            'css': self.site_settings.css}

    @mock.patch('mirocommunity_saas.tiers.Tier.permit_custom_css', naysayer)
    def test_POST_css_failure(self):
        """
        When CSS is not permitted, the POST should fail with a validation error.
        """
        c = Client()
        c.login(username='admin', password='admin')
        self.POST_data['css'] = 'new css'
        POST_response = c.post(self.url, self.POST_data)

        self.assertStatusCodeEquals(POST_response, 200)
        self.assertEqual(POST_response.templates[0].name,
                          'localtv/admin/edit_settings.html')
        self.assertFalse(POST_response.context['form'].is_valid())

    @mock.patch('mirocommunity_saas.tiers.Tier.permit_custom_css', naysayer)
    def test_POST_css_succeeds_when_same_as_db_contents(self):
        """
        When CSS is not permitted, but we send the same CSS as what
        is in the database, the form should be valid.
        """
        c = Client()
        c.login(username='admin', password='admin')
        POST_response = c.post(self.url, self.POST_data)

        # We know from the HTTP 302 that it worked.
        self.assertStatusCodeEquals(POST_response, 302)

class EditUsersDeniedSometimesTestCase(AdministrationBaseTestCase):
    url = reverse('localtv_admin_users')

    def test_POST_rejects_first_admin_beyond_superuser(self):
        """
        A POST to the users view with a POST['submit'] of 'Add' and a
        successful form should create a new user and redirect the user back to
        the management page.  If the password isn't specified,
        User.has_unusable_password() should be True.
        """
        superuser = self.create_user(username='superuser',
                                     email='superuser@gmail.com',
                                     is_superuser=True)
        superuser.set_password('superuser')
        superuser.save()
        self.tier_info.tier_name = 'basic'
        self.tier_info.save()
        c = Client()
        c.login(username="superuser", password="superuser")
        POST_data = {
            'submit': 'Add',
            'username': 'new',
            'email': 'new@testserver.local',
            'role': 'admin',
            }
        response = c.post(self.url, POST_data)
        self.assertStatusCodeEquals(response, 200)
        self.assertFalse(response.context['add_user_form'].is_valid())

        # but with 'premium' it works
        self.tier_info.tier_name = 'premium'
        self.tier_info.save()

        c = Client()
        c.login(username="admin", password="admin")
        POST_data = {
            'submit': 'Add',
            'username': 'new',
            'email': 'new@testserver.local',
            'role': 'admin',
            }
        response = c.post(self.url, POST_data)
        self.assertStatusCodeEquals(response, 302)


@mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers',
            mock.Mock(return_value=True))
class CannotApproveVideoIfLimitExceeded(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        BaseTestCase.setUp(self)
        u = self.create_user(
            username='admin',
            is_superuser=True)
        u.set_password('admin')
        u.save()

    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit',
                mock.Mock(return_value=2))
    def test_videos_over_new_limit(self):
        # Let there be one video already approved
        self.create_video(site_id=settings.SITE_ID,
                          status=Video.ACTIVE)
        # Create two in the queue
        for k in range(2):
            self.create_video(site_id=settings.SITE_ID,
                              status=Video.UNAPPROVED)

        first_video_id, second_video_id = [v.id for v in
                                           Video.objects.filter(
                                               status=Video.UNAPPROVED)]

        # Try to activate all of them, but that would take us over the limit.
        c = Client()
        c.login(username='admin', password='admin')
        response = c.get(reverse('localtv_admin_approve_all'),
                         {'page': '1'})
        self.assertStatusCodeEquals(response, 402)

        # Try to activate the first one -- should work fine.
        c = Client()
        c.login(username='admin', password='admin')
        response = c.get(reverse('localtv_admin_approve_video'),
                         {'video_id': str(first_video_id)})
        self.assertStatusCodeEquals(response, 200)

        # Try to activate the second one -- you're past the limit.
        # HTTP 402: Payment Required
        c = Client()
        c.login(username='admin', password='admin')
        response = c.get(reverse('localtv_admin_approve_video'),
                         {'video_id': str(second_video_id)})
        self.assertStatusCodeEquals(response, 402)


class DowngradingDisablesThings(AdministrationBaseTestCase):

    def setUp(self):
        AdministrationBaseTestCase.setUp(self)
        self.superuser = User(
            username='superuser',
            email='superuser@testserver.local',
            is_superuser=True)
        self.superuser.set_unusable_password()
        self.superuser.save()

    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit',
                mock.Mock(return_value=2))
    def test_videos_over_new_limit(self):
        # Create two videos
        for k in range(3):
            Video.objects.create(site_id=self.site_settings.site_id,
                                 status=Video.ACTIVE)
        self.assertTrue('videos' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit',
                mock.Mock(return_value=2))
    def test_videos_within_new_limit(self):
        # Create just one video
        Video.objects.create(site_id=self.site_settings.site_id)
        self.assertTrue('videos' not in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

    def test_go_to_basic_from_max_warn_about_css_loss(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Delete user #2 so that we have only 1 admin, the super-user
        self.assertEqual(2,
                         tiers.number_of_admins_including_superuser())
        self.admin.delete()

        # Add some CSS to the site_settings
        self.site_settings.css = '* { display: none; }'
        self.site_settings.save()

        # Go to basic, noting that we will see an 'advertising' message
        # Now, make sure that the downgrade helper notices and complains
        self.assertTrue(
            'css' in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_from_max_skip_warn_about_css_loss(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Delete user #2 so that we have only 1 admin, the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())
        self.admin.delete()

        # Because there is no custom CSS, a transition to 'basic' would not
        # generate a warning.

        # Go to basic, noting that we will see an 'advertising' message
        # Now, make sure that the downgrade helper notices and complains
        self.assertTrue(
            'css' not in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_from_max_lose_advertising(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Delete user #2 so that we have only 1 admin, the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())
        self.admin.delete()

        # Go to basic, noting that we will see an 'advertising' message
        # Now, make sure that the downgrade helper notices and complains
        self.assertTrue(
            'advertising' in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_from_plus_no_advertising_msg(self):
        # Start out in Plus
        self.tier_info.tier_name = 'plus'
        self.tier_info.save()

        # Delete user #2 so that we have only 1 admin, the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())
        self.admin.delete()

        # Go to basic, noting that we will no 'advertising' message
        self.assertTrue(
            'advertising' not in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_from_max_lose_custom_domain(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Make our site.domain be myawesomesite.example.com
        self.site_settings.site.domain = 'myawesomesite.example.com'
        self.site_settings.site.save()

        # Get warnings for downgrade.
        self.assertTrue(
            'customdomain' in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_from_max_with_a_noncustom_domain(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Make our site.domain be within mirocommunity.org
        self.site_settings.site.domain = 'myawesomesite.mirocommunity.org'
        self.site_settings.site.save()

        # Get warnings for downgrade.
        self.assertFalse(
            'customdomain' in
            tiers.user_warnings_for_downgrade(new_tier_name='basic'))

    def test_go_to_basic_with_one_admin(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Delete user #2 so that we have only 1 admin, the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())
        self.admin.delete()

        # Now we have 1 admin, namely the super-user
        self.assertEqual(1, tiers.number_of_admins_including_superuser())

        # Verify that the basic account type only permits 1
        self.assertEqual(1, tiers.Tier('basic').admins_limit())

        # Now check what messages we would generate if we dropped down
        # to basic.
        self.assertTrue(
            'admins' not in tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

        # Try pushing the number of admins down to 1, which should change
        # nothing.
        self.assertFalse(tiers.push_number_of_admins_down(1))
        # Still one admin.
        self.assertEqual(1, tiers.number_of_admins_including_superuser())

    def test_go_to_basic_with_two_admins(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Verify that we started with 2 admins, including the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())

        # Verify that the basic account type only permits 1
        self.assertEqual(1, tiers.Tier('basic').admins_limit())

        # Now check what messages we would generate if we dropped down
        # to basic.
        self.assertTrue('admins' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

        # Try pushing the number of admins down to 1, which should change
        # nothing.
        usernames = tiers.push_number_of_admins_down(1)
        self.assertEqual(set(['admin']), usernames)
        # Still two admins -- the above does a dry-run by default.
        self.assertEqual(2, tiers.number_of_admins_including_superuser())

        # Re-do it for real.
        usernames = tiers.push_number_of_admins_down(
            1, actually_demote_people=True)
        self.assertEqual(set(['admin']), usernames)
        self.assertEqual(1, tiers.number_of_admins_including_superuser())

    def test_non_active_users_do_not_count_as_admins(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Verify that we started with 2 admins, including the super-user
        self.assertEqual(2, tiers.number_of_admins_including_superuser())

        # If we make the 'admin' person not is_active, now there is only "1"
        # admin
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(1, tiers.number_of_admins_including_superuser())

    def test_go_to_basic_with_a_custom_theme(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Create two themes -- one bundled, and one not.
        Theme.objects.create(name='a bundled guy', bundled=True,
                             site_id=self.site_settings.site_id)
        Theme.objects.create(name='a custom guy', default=True,
                             site_id=self.site_settings.site_id)

        # Now, make sure that the downgrade helper notices and complains
        self.assertTrue('customtheme' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='premium'))

        # For now, the default theme is still the bundled one.
        self.assertFalse(Theme.objects.get_default().bundled)

        # "Transition" from max to max, to make sure the theme stays
        self.tier_info.save()
        self.assertFalse(Theme.objects.get_default().bundled)

        # Now, force the transition
        self.tier_info.tier_name = 'premium'
        self.tier_info.save()
        # Check that the user is now on a bundled theme
        self.assertTrue(Theme.objects.get_default().bundled)

    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit',
                mock.Mock(return_value=2))
    def test_go_to_basic_with_too_many_videos(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Create three published videos
        for k in range(3):
            Video.objects.create(site_id=self.site_settings.site_id,
                                 status=Video.ACTIVE)
        self.assertTrue('videos' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

        # We can find 'em all, right?
        self.assertEqual(3, Video.objects.filter(status=Video.ACTIVE).count())

        # Do the downgrade -- there should only be two active videos now
        self.tier_info.tier_name = 'basic'
        self.tier_info.save()
        self.assertEqual(2, Video.objects.filter(status=Video.ACTIVE).count())

        # Make sure it's video 0 that is disabled
        self.assertEqual(Video.UNAPPROVED,
                         Video.objects.all().order_by('pk')[0].status)

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers',
                mock.Mock(return_value=False))
    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit',
                mock.Mock(return_value=2))
    def test_go_to_basic_with_too_many_videos_but_do_not_enforce(self):
        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Create three published videos
        for k in range(3):
            Video.objects.create(site_id=self.site_settings.site_id,
                                 status=Video.ACTIVE)
        self.assertTrue('videos' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

        # We can find 'em all, right?
        self.assertEqual(3,Video.objects.filter(status=Video.ACTIVE).count())

        # Do the downgrade -- there should still be three videos because
        # enforcement is disabled
        self.tier_info.tier_name = 'basic'
        self.tier_info.save()
        self.assertEqual(3,Video.objects.filter(status=Video.ACTIVE).count())

    def test_go_to_basic_with_a_custom_theme_that_is_not_enabled(self):
        '''Even if the custom themes are not the default ones, if they exist,
        we should let the user know that it won't be accessible anymore.'''

        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        # Create two themes -- one bundled, and one not.
        Theme.objects.create(name='a bundled guy', bundled=True, default=True,
                             site_id=self.site_settings.site_id)
        Theme.objects.create(name='a custom guy', default=False,
                             site_id=self.site_settings.site_id)

        # Now, make sure that the downgrade helper notices and complains
        self.assertTrue('customtheme' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='premium'))

    def test_no_theme_warning_if_not_used(self):
        '''If the custom themes are not the default ones, and if the
        current tier does not permit custom themes, then do not bother
        telling the user that they may not use them.'''
        # Start out in Plus, where default themes are disabled.
        self.tier_info.tier_name = 'plus'
        self.tier_info.save()

        # Create two themes -- one bundled, and one not. Default is bundled.
        Theme.objects.create(name='a bundled guy', default=True, bundled=True,
                             site_id=self.site_settings.site_id)
        Theme.objects.create(name='a custom guy', default=False,
                             site_id=self.site_settings.site_id)

        # Now, make sure that the downgrade helper doesn't complain
        self.assertTrue('customtheme' not in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

    def test_no_theme_warning_if_upgrading(self):
        '''If an admin is upgrading, no warning about custom themes should be
        sent.'''
        # Start out in Plus, where default themes are disabled.
        self.tier_info.tier_name = 'plus'
        self.tier_info.save()

        # Create two themes -- one bundled, and one not. Default is bundled.
        Theme.objects.create(name='a bundled guy', default=True, bundled=True,
                             site_id=self.site_settings.site_id)
        Theme.objects.create(name='a custom guy', default=False,
                             site_id=self.site_settings.site_id)

        # Now, make sure that the downgrade helper doesn't complain
        self.assertTrue('customtheme' not in
                        tiers.user_warnings_for_downgrade(new_tier_name='max'))



class NoEnforceMode(BaseTestCase):

    def setUp(self):
        BaseTestCase.setUp(self)
        self.tier_info = TierInfo.objects.get_current()
        self.tier_info.tier_name = 'basic'
        self.tier_info.save()

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
            return_value=True))
    def test_theme_uploading_with_enforcement(self):
        permit = self.tier_info.enforce_permit_custom_template()
        self.assertFalse(permit)

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
            return_value=False))
    def test_theme_uploading_without_enforcement(self):
        permit = self.tier_info.enforce_permit_custom_template()
        self.assertTrue(permit)

class DowngradingSevenAdmins(AdministrationBaseTestCase):

    def test_go_to_plus_with_seven_admins(self):
        # XXX create 5 more admins

        # Start out in Executive mode, by default
        self.assertEqual(self.tier_info.tier_name, 'max')

        for i in range(6):
            self.site_settings.admins.add(
                self.create_user(username='admin%i' % i))

        # Verify that we started with 2 admins, including the super-user
        self.assertEqual(7, tiers.number_of_admins_including_superuser())

        # Verify that the plus account type only permits 5
        self.assertEqual(5, tiers.Tier('plus').admins_limit())

        # Now check what messages we would generate if we dropped down
        # to basic.
        self.assertTrue('admins' in
                        tiers.user_warnings_for_downgrade(
                new_tier_name='basic'))

        # Well, good -- that means we have to deal with them.  Try pushing the
        # number of admins down to 1, which should change nothing.
        usernames = tiers.push_number_of_admins_down(5)
        self.assertEqual(set(['admin4', 'admin5']), usernames)
        # Still two admins -- the above does a dry-run by default.
        self.assertEqual(7, tiers.number_of_admins_including_superuser())

        # Re-do it for real.
        usernames = tiers.push_number_of_admins_down(
            5, actually_demote_people=True)
        self.assertEqual(set(['admin4', 'admin5']), usernames)
        self.assertEqual(5, tiers.number_of_admins_including_superuser())

class NightlyTiersEmails(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        super(NightlyTiersEmails, self).setUp()
        self.assertEqual(len(mail.outbox), 0)
        self.admin = self.create_user(username='admin',
                                      email='admin@testserver.local',
                                      is_superuser=True)
        self.admin.last_login = datetime.datetime.utcnow()
        self.admin.save()

        self.tiers_cmd = nightly_tiers_events.Command()

    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos_as_proportion',
                mock.Mock(return_value=0.2))
    def test_video_allotment(self):
        # First, it sends an email. But it saves a note in the SiteSettings...
        self.tiers_cmd.handle()
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox = []

        # ..so that the next time, it doesn't send any email.
        self.tiers_cmd.handle()
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch(
        'mirocommunity_saas.models.TierInfo.time_until_free_trial_expires',
        mock.Mock(return_value=datetime.timedelta(days=7)))
    def test_free_trial_nearly_up_notification_false(self):
        self.tiers_cmd.handle()
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch(
        'mirocommunity_saas.models.TierInfo.time_until_free_trial_expires',
        mock.Mock(return_value=datetime.timedelta(days=5)))
    def test_free_trial_nearly_up_notification_true(self):
        self.tiers_cmd.handle()
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox = []

        # Make sure it does not want to send it again
        self.tiers_cmd.handle()
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch(
        'mirocommunity_saas.models.TierInfo.time_until_free_trial_expires',
        mock.Mock(return_value=datetime.timedelta(days=-1)))
    def test_free_trial_negative(self):
        self.assertRaises(ValueError, self.tiers_cmd.handle, ())
        self.assertEqual(len(mail.outbox), 0)
        mail.outbox = []

class SendWelcomeEmailTest(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        BaseTestCase.setUp(self)
        self.create_user(username='admin',
                         email='admin@testserver.local',
                         is_superuser=True)

    def test(self):
        cmd = send_welcome_email.Command()
        cmd.handle()
        self.assertEqual(len(mail.outbox), 1)

    def test_do_not_send_twice(self):
        self.test()
        mail.outbox = []
        cmd = send_welcome_email.Command()
        cmd.handle()
        self.assertEqual(len(mail.outbox), 0) # zero this time.

class SendWelcomeEmailTestForSiteStartedAsBasic(BaseTestCase):
    target_tier_name = 'basic'
    urls = 'mirocommunity_saas.urls'

    @mock.patch('mirocommunity_saas.management.commands.send_welcome_email.'
                'Command.actually_send')
    def test_delayed_welcome_email_with_flag_with_successful_upgrade(
        self, mock_send):
        # When we create a site in a paid tier, we set the
        # should_send_welcome_email_on_paypal_event flag to True.
        #
        # This signifies that we are waiting for the user to go to
        # PayPal before we send the welcome email. So there are two
        # cases:
        #
        # This test method tests the case where the user successfully gets
        # through the process and calls the _paypal_return admin view.
        #
        # (Note that, in theory, the user could rig things carefully so
        # that _paypal_return() gets called, since we don't validate the
        # IPN stuff through _paypal_return(). But the IPN/subscription
        # validation stuff is handled in a separate part of code.)

        # We mock out send_welcome_email's .handle() so that we know if it
        # gets called.

        # No call yet.
        self.assertFalse(mock_send.called)
        self.assertFalse(TierInfo.objects.get_current(
                ).already_sent_welcome_email)

        # Prerequisite:
        ti = TierInfo.objects.get_current()
        ti.should_send_welcome_email_on_paypal_event = True
        ti.save()

        # No call yet.
        self.assertFalse(mock_send.called)
        self.assertTrue(TierInfo.objects.get_current(
                ).should_send_welcome_email_on_paypal_event)

        # Whatever changes the user makes to the SiteSettings should not
        # cause sending, so long as they don't adjust the tier_name.
        site_settings = SiteSettings.objects.get_current()
        site_settings.tagline = 'my site rules'
        site_settings.save()
        # No call yet. Tier Info still retains the flag.
        self.assertFalse(mock_send.called)
        ti = TierInfo.objects.get_current()
        self.assertTrue(ti.should_send_welcome_email_on_paypal_event)
        self.assertEqual('basic', ti.tier_name)

        # Now, call _paypal_return() as if the user got there from PayPal.
        views._paypal_return('plus')

        # Make sure the email got sent
        self.assertTrue(mock_send.called)
        # Make sure the tier_name is plus, really, and that the flag is
        # now set to False.
        ti = TierInfo.objects.get_current()
        self.assertEqual('plus', ti.tier_name)
        self.assertFalse(ti.should_send_welcome_email_on_paypal_event)

    @mock.patch('mirocommunity_saas.management.commands.send_welcome_email.'
                'Command.actually_send')
    def test_delayed_welcome_email_with_flag_with_unsuccessful_upgrade(
        self, mock_send):
        # Okay, so let's say that you thought you were going to sign
        # up for a 'plus' account.
        #
        # But then you go to PayPal and realize you forgot your password.
        # "Whatever," you figure, and you log in and use the new MC site.
        #
        # What should happen is:
        # - Your site got created as 'basic' at the start.
        # - We don't send you the welcome email because we hoped you would
        #   finish the sign-up process in a non-basic tier.
        # - Then the twice-an-hour cron job runs.
        # - First, it runs when the time delta is less than 30 minutes, in
        #   which case we're still hoping that you will finish up with PayPal.
        # - Then it runs again, and it's more than 30 minutes. So we send you
        #   a welcome email for the tier you are in (basic), and we remove the
        #   flag that says we are expecting you to finish the PayPal process.

        # Setup
        # Pre-requisite:
        NOW = datetime.datetime.utcnow()
        PLUS_THIRTY_MIN = NOW + datetime.timedelta(minutes=30)
        ti = TierInfo.objects.get_current()
        ti.should_send_welcome_email_on_paypal_event = True
        ti.waiting_on_payment_until = PLUS_THIRTY_MIN
        ti.save()

        self.assertFalse(mock_send.called)
        self.assertEqual(ti.tier_name, 'basic')

        # Whatever changes the user makes to the SiteSettings should not
        # cause sending, so long as they don't adjust the tier_name.
        site_settings = SiteSettings.objects.get_current()
        site_settings.tagline = 'my site rules'
        site_settings.save()
        # No call yet. Tier Info still retains the flag.
        self.assertFalse(mock_send.called)
        ti = TierInfo.objects.get_current()
        self.assertTrue(ti.should_send_welcome_email_on_paypal_event)
        self.assertEqual('basic', ti.tier_name)

        PLUS_TEN_MIN = NOW + datetime.timedelta(minutes=10)
        PLUS_FORTY_MIN = NOW + datetime.timedelta(minutes=40)

        cmd = check_frequently_for_invalid_tiers_state.Command()
        cmd.stop_waiting_if_we_have_to(PLUS_TEN_MIN)

        # Should be no change + no email
        self.assertFalse(mock_send.called)

        # re-call even later
        cmd.stop_waiting_if_we_have_to(PLUS_FORTY_MIN)
        self.assertTrue(mock_send.called)
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.should_send_welcome_email_on_paypal_event)
        self.assertFalse(ti.waiting_on_payment_until)

class TestDisableEnforcement(BaseTestCase):

    def testTrue(self):
        self.assertTrue(TierInfo.enforce_tiers(override_setting=False))

    def testFalse(self):
        self.assertFalse(TierInfo.enforce_tiers(override_setting=True))

class DowngradingCanNotifySupportAboutCustomDomain(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        BaseTestCase.setUp(self)
        self.superuser = self.create_user(username='superuser',
                                          email='superuser@testserver.local',
                                          is_active=True,
                                          is_superuser=True)

    @mock.patch('mirocommunity_saas.models.TierInfo.use_zendesk',
                mock.Mock(return_value=True))
    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers',
                mock.Mock(return_value=True))
    def test(self):
        # Start out in Executive mode
        tier_info = TierInfo.objects.get_current()
        tier_info.tier_name = 'max'
        tier_info.save()
        mail.outbox = []

        # Give the site a custom domain
        site = tier_info.site_settings.site
        site.domain = 'custom.example.com'
        site.save()

        # Make sure it stuck
        self.assertEqual(tier_info.site_settings.site.domain,
                         'custom.example.com')

        # There are no emails in the outbox yet
        self.assertEqual([], mail.outbox)

        # Bump down to 'basic'.
        tier_info.tier_name = 'basic'
        tier_info.save()

        self.assertEqual([], mail.outbox)
        self.assertEqual(1, len(zendesk.outbox))

@mock.patch('mirocommunity_saas.models.TierInfo.use_zendesk',
            mock.Mock(return_value=True))
@mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers',
            mock.Mock(return_value=True))
class IpnIntegration(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        # Call superclass setUp()
        super(IpnIntegration, self).setUp()

        self.superuser = self.create_user(
            username='superuser',
            email='superuser@testserver.local',
            is_superuser=True)
        self.superuser.set_password('superuser')
        self.superuser.save()

        # Set current tier to 'basic'
        self.tier_info = TierInfo.objects.get_current()
        self.tier_info.tier_name = 'basic'

        # At the start of this test, we have no current recurring payment
        # profile
        self.assertFalse(self.tier_info.current_paypal_profile_id)

        # Make sure there is a free trial available
        self.tier_info.free_trial_available = True
        self.tier_info.free_trial_started_on = None
        self.tier_info.should_send_welcome_email_on_paypal_event = True
        self.already_sent_welcome_email = False
        self.tier_info.save()

        self.c = Client()
        self.c.login(username='superuser', password='superuser')

        zendesk.outbox = []

    def upgrade_and_submit_ipn(self):
        self.assertTrue(TierInfo.objects.get_current().free_trial_available)

        # GET the begin_free_trial element...
        url = reverse('localtv_admin_begin_free_trial',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})
        self.c.get(url, {'target_tier_name': 'plus'})

        # Make sure we switched
        new_tier_info = TierInfo.objects.get_current()
        self.assertEqual('plus', new_tier_info.tier_name)

        # Discover that we still have no paypal profile, because PayPal took a
        # few sec to submit the IPN...
        self.assertFalse(new_tier_info.current_paypal_profile_id)

        # Check that we are in a free trial (should be!)
        self.assertTrue(new_tier_info.in_free_trial)
        self.assertFalse(new_tier_info.free_trial_available)
        message = mail.outbox[0].body
        self.assertFalse('until midnight on None' in message)

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # Now, PayPal sends us the IPN.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_signup',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'30 D',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJK',
                    u'amount3': unicode(PLUS_COST),
                    u'amount1': u'0.00',
                    u'mc_amount3': unicode(PLUS_COST),
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        Client().post(url,
                      ipn_data)


    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def test_upgrade_and_submit_ipn_skipping_free_trial_post(self):
        # If the user upgrades but neglects to POST to the begin_free_trial
        # handler
        tier_info = TierInfo.objects.get_current()
        self.assertFalse(tier_info.current_paypal_profile_id)
        self.assertFalse(tier_info.in_free_trial)
        self.assertTrue(tier_info.free_trial_available)

        self.upgrade_and_submit_ipn_skipping_free_trial_post()

        # Make sure TierInfo recognizes we are in 'plus'
        tier_info = TierInfo.objects.get_current()
        self.assertEqual(tier_info.tier_name, 'plus')

        # Make sure we are in a free trial, etc.
        self.assertTrue(tier_info.in_free_trial)
        self.assertFalse(tier_info.free_trial_available)

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def upgrade_and_submit_ipn_skipping_free_trial_post(self,
                                                        override_amount3=None):
        if override_amount3:
            amount3 = override_amount3
        else:
            amount3 = unicode(PLUS_COST)

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # Now, PayPal sends us the IPN.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_signup',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'30 D',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJK',
                    u'amount3': amount3,
                    u'amount1': u'0.00',
                    u'mc_amount3': amount3,
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        response = Client().post(url,
                      ipn_data)
        self.assertEqual('OKAY', response.content.strip())

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def upgrade_including_prorated_duration_and_amount(self, amount1,
                                                       amount3, period1):
        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': amount1,
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_signup',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'prorated change',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': period1,
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJK',
                    u'amount3': amount3,
                    u'amount1': amount1,
                    u'mc_amount3': amount3,
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 20, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        response = Client().post(url,
                      ipn_data)
        self.assertEqual('OKAY', response.content.strip())

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def submit_ipn_subscription_modify(self, override_amount3=None,
                                       override_subscr_id=None):
        if override_amount3:
            amount3 = override_amount3
        else:
            amount3 = unicode(PLUS_COST)

        if override_subscr_id:
            subscr_id = override_subscr_id
        else:
            subscr_id = u'I-MEBGA2YXPNJK'

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # Now, PayPal sends us the IPN.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_modify',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'30 D',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': subscr_id,
                    u'amount3': amount3,
                    u'amount1': u'0.00',
                    u'mc_amount3': amount3,
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        response = Client().post(url,
                      ipn_data)
        self.assertEqual('OKAY', response.content.strip())

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def submit_ipn_subscription_cancel(self, override_subscr_id=None):
        if override_subscr_id:
            subscr_id = override_subscr_id
        else:
            subscr_id = u'I-MEBGA2YXPNJK'

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # Now, PayPal sends us the IPN.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_cancel',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'30 D',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': subscr_id,
                    u'amount1': u'0.00',
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        response = Client().post(url,
                      ipn_data)
        self.assertEqual('OKAY', response.content.strip())

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def test_upgrade_between_paid_tiers(self):
        self.test_success()
        ti = TierInfo.objects.get_current()
        self.assertEqual(ti.tier_name, 'plus')

        self.upgrade_between_paid_tiers()

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def upgrade_between_paid_tiers(self):
        # Now, we get an IPN for $35, which should move us to 'premium'
        # Now, PayPal sends us the IPN.
        mail.outbox = []
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_signup',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': u'1',
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJR',
                    u'amount3': unicode(PREMIUM_COST),
                    u'amount1': u'0.00',
                    u'mc_amount3': unicode(PREMIUM_COST),
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        Client().post(url,
                      ipn_data)

        # Make sure TierInfo recognizes we are in 'premium'
        ti = TierInfo.objects.get_current()
        self.assertEqual(ti.tier_name, 'premium')

        self.assertEqual(ti.current_paypal_profile_id,
                         'I-MEBGA2YXPNJR') # the new one
        self.assertTrue(ti.payment_due_date >
                        datetime.datetime(2011, 3, 19, 0, 0, 0))
        self.assertEqual(len([msg for msg in zendesk.outbox
                              if 'cancel a recurring payment profile' in
                              msg['subject']]), 1)
        zendesk.outbox = []
        mail.outbox = []

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # PayPal eventually sends us the IPN cancelling the old subscription,
        # because someone in the MC team ends it.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US',
                    u'mc_amount1': u'0.00',
                    u'invoice': u'premium',
                    u'payer_status': u'verified',
                    u'txn_type': u'subscr_cancel',
                    u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0',
                    u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'period3': u'1 M',
                    u'period1': u'30 D',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm'
                                     u'39KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJK',
                    u'amount3': unicode(PLUS_COST),
                    u'amount1': u'0.00',
                    u'mc_amount3': unicode(PLUS_COST),
                    u'mc_currency': u'USD',
                    u'subscr_date': u'12:06:48 Feb 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        Client().post(url,
                      ipn_data)

        # Make sure TierInfo still recognizes we are in 'premium'
        ti = TierInfo.objects.get_current()
        self.assertEqual(ti.tier_name, 'premium')

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def test_success(self):
        self.upgrade_and_submit_ipn()

        # Make sure SiteSettings recognizes we are in 'plus'
        tier_info = TierInfo.objects.get_current()

        self.assertEqual(tier_info.tier_name, 'plus')
        self.assertTrue(tier_info.in_free_trial)
        self.assertFalse(tier_info.free_trial_available)

        self.assertEqual(tier_info.current_paypal_profile_id, 'I-MEBGA2YXPNJK')

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='VERIFIED'))
    def test_payment_success(self):
        self.upgrade_and_submit_ipn()
        tier_info = TierInfo.objects.get_current()
        self.assertEqual(tier_info.current_paypal_profile_id, 'I-MEBGA2YXPNJK')

        test_ipn = u'1' if getattr(settings, 'PAYPAL_TEST', False) else u'0'

        # Send ourselves a payment IPN.
        ipn_data = {u'last_name': u'User',
                    u'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
                    u'residence_country': u'US', u'mc_amount1': u'0.00',
                    u'invoice': u'premium', u'payer_status': u'verified',
                    u'txn_type': u'subscr_payment',
                    u'txn_id':u'S-4LF64589B35985347',
                    u'payment_status': 'Completed', u'first_name': u'Test',
                    u'item_name': u'Miro Community subscription (plus)',
                    u'charset': u'windows-1252',
                    u'custom': u'plus for example.com',
                    u'notify_version': u'3.0', u'recurring': u'1',
                    u'test_ipn': test_ipn,
                    u'business': settings.PAYPAL_RECEIVER_EMAIL,
                    u'payer_id': u'SQRR5KCD7Z266',
                    u'verify_sign': (u'AKcOzwh6cb1eCtGrfvM.18Ri5hWDAWoRIoMoZm3'
                                     u'9KHDsLIoVZyWJDM7B'),
                    u'subscr_id': u'I-MEBGA2YXPNJK',
                    u'payment_gross': unicode(PLUS_COST),
                    u'payment_date': u'12:06:48 Mar 17, 2011 PST',
                    u'payer_email': u'paypal_1297894110_per@s.asheesh.org',
                    u'reattempt': u'1'}
        url = reverse('localtv_admin_ipn_endpoint',
                      kwargs={'payment_secret':
                                  self.tier_info.get_payment_secret()})

        Client().post(url,
                      ipn_data)
        tier_info_new = TierInfo.objects.get_current()
        self.assertEqual(tier_info_new.current_paypal_profile_id,
                         'I-MEBGA2YXPNJK')
        # make sure that they've pushed the due date into the future
        self.assertTrue(tier_info_new.payment_due_date >
                        tier_info.payment_due_date)

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback', mock.Mock(
            return_value='FAILURE'))
    def test_failure(self):
        tier_info = TierInfo.objects.get_current()
        self.assertFalse(tier_info.current_paypal_profile_id) # Should be false
                                                              # at the start

        self.upgrade_and_submit_ipn()
        tier_info = TierInfo.objects.get_current()

        # Because the IPN submitted was invalid, the payment profile ID has not
        # changed.
        self.assertTrue(tier_info.tier_name, 'basic')
        self.assertFalse(tier_info.current_paypal_profile_id)

    @mock.patch('paypal.standard.ipn.models.PayPalIPN._postback',
                mock.Mock(return_value='VERIFIED'))
    def test_downgrade_during_free_trial(self):
        # First, upgrade to 'premium' during the free trial.
        self.upgrade_and_submit_ipn_skipping_free_trial_post(
            unicode(PREMIUM_COST))
        # Make sure it worked
        tierinfo = TierInfo.objects.get_current()
        self.assertEqual('premium', tierinfo.tier_name)
        self.assertTrue(tierinfo.in_free_trial)

        # Now, submit an IPN event for changing the payment amount to '15.00'
        # This should move us down to 'plus'
        self.submit_ipn_subscription_modify(unicode(PLUS_COST))
        # Make sure it worked
        tierinfo = TierInfo.objects.get_current()
        self.assertEqual('plus', tierinfo.tier_name)
        self.assertFalse(tierinfo.in_free_trial)

class TestMidMonthPaymentAmounts(BaseTestCase):
    def test_start_of_month(self):
        data = views.generate_payment_amount_for_upgrade(
            start_tier_name='plus', target_tier_name='premium',
            current_payment_due_date=datetime.datetime(2011, 1, 30, 0, 0, 0),
            todays_date=datetime.datetime(2011, 1, 1, 12, 0, 0))
        expected = {'recurring': PREMIUM_COST,
                    'cost_for_prorated_period': int(PREMIUM_COST * 0.44),
                    'days_covered_by_prorating': 28}
        self.assertEqual(data, expected)

    def test_end_of_month(self):
        data = views.generate_payment_amount_for_upgrade(
            start_tier_name='plus', target_tier_name='premium',
            current_payment_due_date=datetime.datetime(2011, 2, 1, 0, 0, 0),
            todays_date=datetime.datetime(2011, 1, 31, 12, 0, 0))
        expected = {'recurring': PREMIUM_COST, 'cost_for_prorated_period': 0,
                    'days_covered_by_prorating': 0}
        self.assertEqual(data, expected)

@mock.patch('mirocommunity_saas.models.TierInfo.use_zendesk',
            mock.Mock(return_value=True))
class TestUpgradePage(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        self.ipn_integration = None
        super(TestUpgradePage, self).setUp()
        # Always start in 'basic' with a free trial
        c = clear_tiers_state.Command()
        zendesk.outbox = []
        c.handle_noargs()

    def tearDown(self):
        # Note: none of these tests should cause email to be sent.
        self.assertEqual([],
                         [str(k.body) for k in mail.outbox])

    ## assertion helpers
    def _assert_upgrade_extra_payments_always_false(self, response):
        extras = response.context['upgrade_extra_payments']
        for thing in extras:
            self.assertFalse(extras[thing])

    def _assert_modify_always_false(self, response):
        self.assertEqual({'basic': False,
                          'plus': False,
                          'premium': False,
                          'max': False},
                         response.context['can_modify_mapping'])

    def _run_method_from_ipn_integration_test_case(self, methodname, *args):
        if self.ipn_integration is None:
            self.ipn_integration = IpnIntegration(methodname)
            self.ipn_integration.setUp()
        getattr(self.ipn_integration, methodname)(*args)

    ## Action helpers
    def _log_in_as_superuser(self):
        c = Client()
        self.assertTrue(c.login(username='superuser', password='superuser'))
        return c

    ## Tests of various cases of the upgrade page
    def test_first_upgrade(self):
        self.assertTrue(TierInfo.objects.get_current().free_trial_available)
        u = self.create_user(username='superuser',
                             email='superuser@testserver.local',
                             is_superuser=True)
        u.set_password('superuser')
        u.save()
        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertTrue(response.context['offer_free_trial'])
        self._assert_modify_always_false(response)

    def test_upgrade_when_no_free_trial(self):
        ti = TierInfo.objects.get_current()
        ti.free_trial_available = False
        ti.save()
        u = self.create_user(username='superuser',
                             email='superuser@testserver.local',
                             is_superuser=True)
        u.set_password('superuser')
        u.save()
        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])
        self._assert_modify_always_false(response)

    def test_upgrade_when_within_a_free_trial(self):
        # We start in 'basic' with a free trial.  The pre-requisite for this
        # test is that we have transitioned into a tier.  So borrow a method
        # from IpnIntegration
        self._run_method_from_ipn_integration_test_case(
            'test_upgrade_and_submit_ipn_skipping_free_trial_post')
        mail.outbox = [] # remove "Congratulations" email

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertTrue(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)

        # We are in 'plus'. Let's consider what happens when
        # we want to upgrade to 'premium'
        self.assertEqual('plus', ti.tier_name)

        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])

        # This should be False because PayPal will not let us substantially
        # increase a recurring payment amount.
        self.assertFalse(response.context['can_modify_mapping']['premium'])

        # There should be no upgrade_extra_payments value, because we are
        # in a free trial.
        self.assertFalse(response.context['upgrade_extra_payments']['premium'])

        # Okay, so go through the PayPal dance.

        # First, pretend the user went to the paypal_return view, and adjusted
        # the tier name, but without actually receiving the IPN.
        views._paypal_return('premium')
        ti = TierInfo.objects.get_current()
        self.assertEqual(ti.tier_name, 'premium')
        self.assertEqual('plus', ti.fully_confirmed_tier_name)
        # The tier name is updated, so the backend updates its state.
        # That means we sent a "Congratulations" email:
        message, = [str(k.body) for k in mail.outbox]
        self.assertTrue('Congratulations' in message)
        mail.outbox = []
        ti = TierInfo.objects.get_current()
        self.assertTrue(ti.in_free_trial)

        # Actually do the upgrade
        self._run_method_from_ipn_integration_test_case(
            'upgrade_between_paid_tiers')

        # The above method checks that we successfully send an email to
        # support@ suggesting that the user cancel the old payment.
        #
        # It also simulates a support staff person actually cancelling the
        # old payment.
        ti = TierInfo.objects.get_current()
        self.assertEqual('premium', ti.tier_name)
        self.assertEqual('', ti.fully_confirmed_tier_name)

        # Now, make sure the backend knows that we are not in a free trial
        self.assertFalse(ti.in_free_trial)

    def test_upgrade_when_within_a_free_trial_with_super_quick_ipn(self):
        # We start in 'basic' with a free trial.  The pre-requisite for this
        # test is that we have transitioned into a tier.  So borrow a method
        # from IpnIntegration
        self._run_method_from_ipn_integration_test_case(
            'test_upgrade_and_submit_ipn_skipping_free_trial_post')
        mail.outbox = [] # remove "Congratulations" email

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertTrue(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)
        self.assertEqual('plus', ti.tier_name)

        # We are in 'plus'. Let's consider what happens when
        # we want to upgrade to 'premium'

        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])

        # This should be False because PayPal will not let us substantially
        # increase a recurring payment amount.
        self.assertFalse(response.context['can_modify_mapping']['premium'])

        # There should be no upgrade_extra_payments value, because we are
        # in a free trial.
        self.assertFalse(response.context['upgrade_extra_payments']['premium'])

        # Okay, so go through the PayPal dance.

        # Actually do the upgrade
        self._run_method_from_ipn_integration_test_case(
            'upgrade_between_paid_tiers')

        # The above method checks that we successfully send an email to
        # support@ suggesting that the user cancel the old payment.
        #
        # It also simulates a support staff person actually cancelling the
        # old payment.
        ti = TierInfo.objects.get_current()
        self.assertEqual('premium', ti.tier_name)
        self.assertEqual('', ti.fully_confirmed_tier_name)

        # First, pretend the user went to the paypal_return view, and adjusted
        # the tier name, but without actually receiving the IPN.
        views._paypal_return('premium')
        ti = TierInfo.objects.get_current()
        self.assertEqual(ti.tier_name, 'premium')
        self.assertEqual('', ti.fully_confirmed_tier_name)
        # The tier name was already updated, so the backend need not update its
        # state.  Therefore, we do a "Congratulations" email:
        self.assertEqual([], mail.outbox)

        # Now, make sure the backend knows that we are not in a free trial
        self.assertFalse(ti.in_free_trial)

    def test_upgrade_from_basic_when_not_within_a_free_trial(self):
        # The pre-requisite for this test is that we have transitioned into a
        # tier.  So borrow a method from IpnIntegration
        self._run_method_from_ipn_integration_test_case(
            'test_upgrade_and_submit_ipn_skipping_free_trial_post')
        mail.outbox = [] # remove "Congratulations" email

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertTrue(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)

        # Cancelling the subscription should put empty out the current paypal
        # ID.
        self._run_method_from_ipn_integration_test_case(
            'submit_ipn_subscription_cancel', ti.current_paypal_profile_id)
        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertFalse(ti.in_free_trial)
        self.assertFalse(ti.current_paypal_profile_id)
        # We are in 'basic' now.
        self.assertEqual('basic', ti.tier_name)

        # If we upgrade to a paid tier...
        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])
        self._assert_modify_always_false(response)
        self._assert_upgrade_extra_payments_always_false(response)

    def test_upgrade_from_paid_when_within_a_free_trial(self):
        # The pre-requisite for this test is that we have transitioned into a
        # tier.  So borrow a method from IpnIntegration
        self._run_method_from_ipn_integration_test_case(
            'test_upgrade_and_submit_ipn_skipping_free_trial_post')
        mail.outbox = [] # remove "Congratulations" email

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertTrue(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)
        first_profile = ti.current_paypal_profile_id
        self.assertEqual('plus', ti.tier_name)

        # If we want to upgrade... let's look at the upgrade page state:
        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])
        self._assert_upgrade_extra_payments_always_false(response)
        self._assert_modify_always_false(response) # no modify possible from
                                                   # 'plus'

        # This means that if someone changes the payment amount to $35/mo
        # we will be at 'premium'.
        self._run_method_from_ipn_integration_test_case(
            'upgrade_between_paid_tiers')
        ti = TierInfo.objects.get_current()
        self.assertEqual('premium', ti.tier_name)
        self.assertNotEqual(ti.current_paypal_profile_id, first_profile)

    def test_upgrade_from_paid_when_not_within_a_free_trial(self):
        # First, upgrade and downgrade...
        self.test_downgrade_to_paid_not_during_a_trial()

        ti = TierInfo.objects.get_current()
        self.assertEqual('plus', ti.tier_name)

        # Travel to the future
        with mock.patch('datetime.datetime', Fakedatetime):
            # Now, we have some crazy prorating stuff.
            c = self._log_in_as_superuser()
            response = c.get(reverse('localtv_admin_tier'))

        ti = TierInfo.objects.get_current()
        self.assertFalse(response.context['offer_free_trial'])
        # For the prorating...
        extras = response.context['upgrade_extra_payments']
        premium = extras['premium']
        # The adjusted due date is, like, about 1 day different.
        self.assertTrue(abs((Fakedatetime.utcnow() - (
                        ti.payment_due_date - datetime.timedelta(
                            premium['days_covered_by_prorating']))).days) <= 1)
        # The one-time money bump is more than 2/3 of the difference.
        entire_difference = PREMIUM_COST - PLUS_COST
        self.assertTrue(premium['cost_for_prorated_period'] >= (
                0.667 * entire_difference))
        self._assert_modify_always_false(response) # no modify possible from
                                                   # 'plus'

        # Let's try paying.
        # NOTE: We don't check here what happens if you pay with the wrong
        # pro-rating amount.
        with mock.patch('datetime.datetime', Fakedatetime):
            self._run_method_from_ipn_integration_test_case(
                'upgrade_including_prorated_duration_and_amount',
                '%d.00' % premium['cost_for_prorated_period'],
                str(PREMIUM_COST),
                '%d D' % premium['days_covered_by_prorating'])
            ti = TierInfo.objects.get_current()
            self.assertEqual('premium', ti.tier_name)
            # Also, no emails.
            self.assertEqual(set(['superuser@testserver.local']),
                             set([x.to[0] for x in mail.outbox]))
            self.assertEqual(1, len(zendesk.outbox))
            mail.outbox = []

    def test_downgrade_to_paid_during_a_trial(self):
        # The test gets initialized in 'basic' with a free trial available.
        # First, switch into a free trial of 'max'.
        self._run_method_from_ipn_integration_test_case(
            'upgrade_and_submit_ipn_skipping_free_trial_post', str(MAX_COST))
        mail.outbox = [] # remove "Congratulations" email

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertTrue(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)
        self.assertEqual('max', ti.tier_name)

        old_profile = ti.current_paypal_profile_id

        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])

        # This should be False. The idea is that we cancel the old, trial-based
        # subscription. We will create a new subscription so that it can start
        # immediately.
        self.assertFalse(response.context['can_modify_mapping']['premium'])

        self._run_method_from_ipn_integration_test_case(
            'upgrade_between_paid_tiers')

        ti = TierInfo.objects.get_current()
        self.assertNotEqual(old_profile, ti.current_paypal_profile_id)
        self.assertEqual([], mail.outbox)
        self.assertFalse(ti.in_free_trial)
        self.assertEqual(ti.tier_name, 'premium')

    def test_downgrade_to_paid_not_during_a_trial(self):
        # Let's say the user started at 'max' and free trial, and then switched
        # down to 'premium' which ended the trial.
        self.test_downgrade_to_paid_during_a_trial()

        # Sanity-check the free trial state.
        ti = TierInfo.objects.get_current()
        self.assertFalse(ti.free_trial_available)
        self.assertFalse(ti.in_free_trial)
        self.assertTrue(ti.current_paypal_profile_id)
        self.assertEqual('premium', ti.tier_name)
        old_profile = ti.current_paypal_profile_id

        # We are in 'premium'. Let's consider what happens when
        # we want to downgrade to 'plus'


        c = self._log_in_as_superuser()
        response = c.get(reverse('localtv_admin_tier'))
        self.assertFalse(response.context['offer_free_trial'])

        # This should be False. There is no reason to provide extra payment
        # data; we're just going to modify the subscription amount.
        self.assertFalse(response.context['upgrade_extra_payments']['plus'])

        # This should be True. This is a simple PayPal subscription
        # modification case.
        self.assertTrue(response.context['can_modify_mapping']['plus'])

        # Go to the Downgrade Confirm page
        response = c.post(reverse('localtv_admin_downgrade_confirm'),
                          {'target_tier_name': 'plus'})

        self.assertTrue(response.context['can_modify'])
        self.assertTrue('"modify" value="1"' in response.content)

        self._run_method_from_ipn_integration_test_case(
            'submit_ipn_subscription_modify', str(PLUS_COST), old_profile)

        ti = TierInfo.objects.get_current()
        self.assertEqual(old_profile, ti.current_paypal_profile_id)
        self.assertEqual([], mail.outbox)
        self.assertFalse(ti.in_free_trial)
        self.assertEqual('plus', ti.tier_name)

class TestFreeTrial(BaseTestCase):

    urls = 'mirocommunity_saas.urls'

    @mock.patch('mirocommunity_saas.admin.views._start_free_trial_for_real')
    def test_does_nothing_if_already_in_free_trial(self, m):
        # If we are already in a free trial, then we refuse to continue:
        ti = TierInfo.objects.get_current()
        ti.in_free_trial = True
        ti.save()
        views._start_free_trial_unconfirmed('basic')
        self.assertFalse(m.called)

# -----------------------------------------------------------------------------
# Site tier tests
# -----------------------------------------------------------------------------
class SiteTierTests(BaseTestCase):

    def setUp(self):
        BaseTestCase.setUp(self)
        self.tier_info = TierInfo.objects.get_current()

    def test_basic_account(self):
        # Create a SiteSettings whose site_tier is set to 'basic'
        self.tier_info.tier_name = 'basic'
        self.tier_info.save()
        tier = self.tier_info.get_tier()
        self.assertEqual(0, tier.dollar_cost())
        self.assertEqual(500, tier.videos_limit())
        self.assertEqual(1, tier.admins_limit())
        self.assertFalse(tier.permit_custom_css())
        self.assertFalse(tier.permit_custom_template())

    def test_plus_account(self):
        # Create a SiteSettings whose site_tier is set to 'plus'
        self.tier_info.tier_name = 'plus'
        self.tier_info.save()
        tier = self.tier_info.get_tier()
        self.assertEqual(PLUS_COST, tier.dollar_cost())
        self.assertEqual(1000, tier.videos_limit())
        self.assertEqual(5, tier.admins_limit())
        self.assertTrue(tier.permit_custom_css())
        self.assertFalse(tier.permit_custom_template())

    def test_premium_account(self):
        # Create a SiteSettings whose site_tier is set to 'premium'
        self.tier_info.tier_name = 'premium'
        self.tier_info.save()
        tier = self.tier_info.get_tier()
        self.assertEqual(PREMIUM_COST, tier.dollar_cost())
        self.assertEqual(5000, tier.videos_limit())
        self.assertEqual(None, tier.admins_limit())
        self.assertTrue(tier.permit_custom_css())
        self.assertFalse(tier.permit_custom_template())

    def test_max_account(self):
        self.tier_info.tier_name = 'max'
        self.tier_info.save()
        tier = self.tier_info.get_tier()
        self.assertEqual(MAX_COST, tier.dollar_cost())
        self.assertEqual(25000, tier.videos_limit())
        self.assertEqual(None, tier.admins_limit())
        self.assertTrue(tier.permit_custom_css())
        self.assertTrue(tier.permit_custom_template())

class TierInfoEnablesRestrictionsAfterPayment(BaseTestCase):
    def test_unit(self):
        self.assertFalse(TierInfo.enforce_tiers(override_setting=True))
        tier_info = TierInfo.objects.get_current()
        tier_info.user_has_successfully_performed_a_paypal_transaction = True
        tier_info.save()
        self.assertTrue(TierInfo.enforce_tiers(override_setting=True))

class TierMethodsTests(BaseTestCase):

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
            return_value=False))
    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos', mock.Mock(return_value=0))
    def test_can_add_more_videos(self):
        # This is true because enforcement is off.
        self.assertTrue(tiers.Tier.get().can_add_more_videos())

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
            return_value=True))
    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos', mock.Mock(return_value=0))
    def test_can_add_more_videos_returns_false(self):
        # This is False because the number of videos remaining is zero.
        self.assertFalse(tiers.Tier.get().can_add_more_videos())

    @mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
            return_value=True))
    @mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos', mock.Mock(return_value=1))
    def test_can_add_video_lets_you_add_final_video(self):
        # This is False because the number of videos remaining is zero.
        self.assertTrue(tiers.Tier.get().can_add_more_videos())

    def test_time_until_free_trial_expires_none_when_not_in_free_trial(self):
        ti = TierInfo.objects.get_current()
        ti.in_free_trial = False
        ti.save()
        self.assertEqual(None, ti.time_until_free_trial_expires())

    def test_time_until_free_trial_expires_none_when_no_payment_due(self):
        ti = TierInfo.objects.get_current()
        ti.in_free_trial = True
        ti.payment_due_date = None # Note that this is a kind of insane state.
        ti.save()
        self.assertEqual(None, ti.time_until_free_trial_expires())

    def test_time_until_free_trial_expires(self):
        now = datetime.datetime(2011, 5, 24, 23, 44, 30)
        a_bit_in_the_future = now + datetime.timedelta(hours=5)
        ti = TierInfo.objects.get_current()
        ti.in_free_trial = True
        ti.payment_due_date = a_bit_in_the_future
        ti.save()
        self.assertEqual(datetime.timedelta(hours=5),
                         ti.time_until_free_trial_expires(now=now))

@override_settings(CELERY_ALWAYS_EAGER=True)
class FeedImportTestCase(BaseTestCase):

    def setUp(self):
        BaseTestCase.setUp(self)
        self._parsed_feed = list(self._parse_feed('feed.rss'))

    def _parse_feed(self, filename, force_url=False):
        """
        Returns a :class:`vidscraper.suites.base.Feed` for the feed stored as
        <filename> in our testdata.  If `force_url` is True, we'll load the URL
        from the feed and use that to get a suite.
        """
        path = self._data_file(filename)
        if force_url:
            fp = feedparser.parse(path)
            vidscraper_feed = vidscraper.auto_feed(fp.feed.link)
            vidscraper_feed.get_first_url = lambda: path
        else:
            vidscraper_feed = vidscraper.auto_feed(path)
        return vidscraper_feed

    def _update_with_video_iter(self, video_iter, feed):
        feed_import = FeedImport.objects.create(source=feed,
                                                auto_approve=feed.auto_approve)
        Source.update(feed, video_iter, feed_import)

    @mock.patch('mirocommunity_saas.tiers.Tier.videos_limit', lambda *args: 4)
    @mock.patch('localtv.models.Video.save_thumbnail',
                mock.Mock(return_value=None))
    def test_auto_approve_True_when_user_past_video_limit(self):
        """
        If FeedImport.auto_approve is True, but approving the videos in the
        feed would put the site past the video limit, the imported videos
        should be marked as unapproved.

        """
        feed = self.create_feed('http://example.com/feed.rss',
                                auto_approve=True)
        self._update_with_video_iter(self._parsed_feed, feed)
        self.assertEqual(Video.objects.count(), 5)
        self.assertEqual(Video.objects.filter(
                status=Video.ACTIVE).count(), 4)
        self.assertEqual(Video.objects.filter(
                status=Video.UNAPPROVED).count(), 1)

@mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos',
            mock.Mock(return_value=4))
class BulkEditAdministrationTestCase(AdministrationBaseTestCase):

    urls = 'mirocommunity_saas.urls'

    def setUp(self):
        self.videos = []
        for i in range(5):
            self.videos.append(
                self.create_video('Video %i' % i, status=Video.UNAPPROVED,
                                  embed_code='HTML!'))
        AdministrationBaseTestCase.setUp(self)

    def test_approve_exactly_enough_videos(self):
        POST_data = {
            'form-TOTAL_FORMS': 6,
            'form-INITIAL_FORMS': 5,
            'form-MAX_NUM_FORMS': 6}
        for i in range(5):
            video = self.videos[i]
            for field in ('id', 'name', 'file_url', 'description',
                          'embed_code', 'thumbnail_url'):
                POST_data['form-%i-%s' % (i, field)] = getattr(video, field)

        for i in range(4):
            POST_data['form-%i-BULK' % i] = 'yes'
        POST_data['bulk_action'] = 'approve'

        url = reverse('localtv_admin_bulk_edit') + '?filter=unapproved'

        c = Client()
        self.assertTrue(c.login(username='admin', password='admin'))

        response = c.post(url, POST_data)
        self.assertStatusCodeEquals(response, 302)
        self.assertEqual(Video.objects.filter(status=Video.ACTIVE).count(),
                         4)
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED).count(),
                         1)

    def test_approved_too_many_videos(self):
        POST_data = {
            'form-TOTAL_FORMS': 6,
            'form-INITIAL_FORMS': 5,
            'form-MAX_NUM_FORMS': 6}
        for i in range(5):
            video = self.videos[i]
            for field in ('id', 'name', 'file_url', 'description',
                          'embed_code'):
                POST_data['form-%i-%s' % (i, field)] = getattr(video, field)
            POST_data['form-%i-BULK' % i] = 'yes'
        POST_data['bulk_action'] = 'approve'

        url = reverse('localtv_admin_bulk_edit') + '?filter=unapproved'

        c = Client()
        self.assertTrue(c.login(username='admin', password='admin'))

        response = c.post(url, POST_data)
        self.assertStatusCodeEquals(response, 200)
        formset = response.context['formset']
        self.assertFalse(formset.is_valid())
        self.assertEqual(Video.objects.filter(status=Video.UNAPPROVED).count(),
                         5)

@mock.patch('mirocommunity_saas.models.TierInfo.enforce_tiers', mock.Mock(
        return_value=True))
@mock.patch('mirocommunity_saas.tiers.Tier.remaining_videos',
            mock.Mock(return_value=0))
class SubmitVideoViewTestCase(BaseTestCase):

    def test_admin_cant_submit_approved_video(self):
        submit_url = 'http://www.youtube.com/watch?v=JzhlfbWBuQ8'
        u = self.create_user(username='admin',
                             password='admin',
                             is_superuser=True)
        u.set_password('admin')
        u.save()

        data = {'url': submit_url}

        c = Client()
        self.assertTrue(c.login(username='admin', password='admin'))

        # step 1
        c.post(reverse('localtv_submit_video'), data)

        # step 2
        response = c.post(reverse('localtv_submit_scraped_video'), data)

        self.assertStatusCodeEquals(response, 302)

        v = Video.objects.get()
        self.assertEqual(v.status, Video.UNAPPROVED)
