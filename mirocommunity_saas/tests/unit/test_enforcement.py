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

import datetime

from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import ValidationError
from django.forms.formsets import TOTAL_FORM_COUNT, INITIAL_FORM_COUNT
from django.forms.models import model_to_dict
from django.http import Http404
from django.test.utils import override_settings
from localtv.models import SiteSettings, Video
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.forms import (EditSettingsForm, AuthorForm,
                                            VideoFormSet)
from mirocommunity_saas.tests import BaseTestCase
from mirocommunity_saas.utils.tiers import (admins_to_demote,
                                            videos_to_deactivate,
                                            enforce_tier,
                                            limit_import_approvals,
                                            check_submission_approval)


class SettingsFormTestCase(BaseTestCase):
    def test_no_custom(self):
        """
        The settings form should be invalid if css is disallowed, but is
        submitted anyway, and if that css doesn't match what's set already.

        """
        tier = self.create_tier(custom_css=False)
        self.create_tier_info(tier)

        data = {'css': 'foo'}
        site_settings = SiteSettings.objects.get_current()
        site_settings.css = 'bar'
        form = EditSettingsForm(data, instance=site_settings)
        form.cleaned_data = data
        self.assertRaises(ValidationError, form.clean_css)
        self.assertEqual(form.data['css'], site_settings.css)

    def test_no_custom__match(self):
        """
        Even if custom css isn't allowed, we do let it through if it matches
        the css that is already stored.

        """
        tier = self.create_tier(custom_css=False)
        self.create_tier_info(tier)

        data = {'css': 'foo'}
        site_settings = SiteSettings.objects.get_current()
        site_settings.css = data['css']
        form = EditSettingsForm(data, instance=site_settings)
        form.cleaned_data = data
        self.assertEqual(form.clean_css(), data['css'])

    def test_custom(self):
        """
        If custom css is allowed, changes to the css don't raise a validation
        error.

        """
        tier = self.create_tier(custom_css=True)
        self.create_tier_info(tier)

        data = {'css': 'foo'}
        site_settings = SiteSettings.objects.get_current()
        site_settings.css = 'bar'
        form = EditSettingsForm(data, instance=site_settings)
        form.cleaned_data = data
        self.assertEqual(form.clean_css(), data['css'])


class AuthorFormTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        site_settings = SiteSettings.objects.get_current()
        self.user = self.create_user(username='user', is_active=True)
        self.admin = self.create_user(username='admin', is_active=True)
        self.old_admin = self.create_user(username='admin2', is_active=False)
        self.superuser = self.create_user(username='superuser',
                                          is_active=True,
                                          is_superuser=True)
        self.old_superuser = self.create_user(username='superuser2',
                                              is_active=False,
                                              is_superuser=True)
        site_settings.admins.add(self.admin)
        site_settings.admins.add(self.old_admin)
        site_settings.admins.add(self.superuser)
        site_settings.admins.add(self.old_superuser)

    def test_at_limit__user_role(self):
        """
        Even if no more admins are allowed, the user role can be set.

        """
        tier = self.create_tier(admin_limit=1)
        self.create_tier_info(tier)
        form = AuthorForm({'role': 'user'}, instance=self.user)
        form.cleaned_data = {'role': 'user'}
        self.assertEqual(form.clean_role(), 'user')

    def test_at_limit__already_admin(self):
        """
        Even if no more admins are allowed, anyone who is an admin can stay
        that way (as far as this form is concerned.)

        """
        tier = self.create_tier(admin_limit=1)
        self.create_tier_info(tier)
        form = AuthorForm({'role': 'admin'}, instance=self.user,
                          initial={'role': 'admin'})
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')

    def test_at_limit(self):
        """
        If they're not an admin and there isn't room for more admins, it's
        a validation error.

        """
        tier = self.create_tier(admin_limit=1)
        self.create_tier_info(tier)
        form = AuthorForm({'role': 'admin'}, instance=self.user)
        form.cleaned_data = {'role': 'admin'}
        self.assertRaises(ValidationError, form.clean_role)

    def test_below_limit(self):
        """
        Admin assignment is allowed if there's room.

        """
        tier = self.create_tier(admin_limit=2)
        self.create_tier_info(tier)

        form = AuthorForm({'role': 'admin'}, instance=self.user)
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')

    def test_no_limit(self):
        """
        Admin assignment is allowed if there's no limit.

        """
        tier = self.create_tier(admin_limit=None)
        self.create_tier_info(tier)
        form = AuthorForm({'role': 'admin'}, instance=self.user)
        form.cleaned_data = {'role': 'admin'}
        self.assertEqual(form.clean_role(), 'admin')


class VideoFormSetTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        for i in range(3):
            self.create_video(status=Video.UNAPPROVED,
                              name='video{0}'.format(i),
                              file_url='http://google.com/{0}'.format(i))

        self.prefix = 'pfx'
        default = {
            '{0}-{1}'.format(self.prefix, TOTAL_FORM_COUNT): 4,
            '{0}-{1}'.format(self.prefix, INITIAL_FORM_COUNT): 3
        }
        qs = Video.objects.all()

        for i, v in enumerate(list(qs) + [Video()]):
            default.update(dict(('{0}-{1}-{2}'.format(self.prefix, i, k), v)
                                for k, v in model_to_dict(v).iteritems()))
            default['{0}-{1}-{2}'.format(self.prefix, i, 'BULK')] = True

        self.approve_data = {'bulk_action': 'feature'}
        self.feature_data = {'bulk_action': 'approve'}
        self.approve_data.update(default)
        self.feature_data.update(default)

    def test_no_limit(self):
        """
        If there's no limit, all of the videos should be approved.

        """
        tier = self.create_tier(video_limit=None)
        self.create_tier_info(tier)

        for data in [self.approve_data, self.feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=self.prefix)
            self.assertTrue(formset.is_valid())
            self.assertTrue(all(form.instance.status == Video.ACTIVE
                                for form in formset.initial_forms))

    def test_below_limit(self):
        """
        If the limit is high enough, the videos should be approved.

        """
        tier = self.create_tier(video_limit=3)
        self.create_tier_info(tier)

        for data in [self.approve_data, self.feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=self.prefix)
            self.assertTrue(formset.is_valid())
            self.assertTrue(all(form.instance.status == Video.ACTIVE
                                for form in formset.initial_forms))

    def test_above_limit(self):
        """
        If the limit isn't high enough, none of the videos should be approved.
        (The formset isn't valid.)

        """
        tier = self.create_tier(video_limit=2)
        self.create_tier_info(tier)

        for data in [self.approve_data, self.feature_data]:
            formset = VideoFormSet(data, queryset=Video.objects.all(),
                                   prefix=self.prefix)
            self.assertFalse(formset.is_valid())


class EnforcementTestCase(BaseTestCase):
    """Tests that enforcing a tier DTRT."""
    def test_admins_to_demote(self):
        tier1 = self.create_tier(slug='tier1', admin_limit=None)
        tier2 = self.create_tier(slug='tier2', admin_limit=100)
        tier3 = self.create_tier(slug='tier3', admin_limit=2)
        tier4 = self.create_tier(slug='tier4', admin_limit=1)
        admin1 = self.create_user(username='admin1')
        admin2 = self.create_user(username='admin2')
        inactive_admin = self.create_user(username='admin3', is_active=False)
        superuser = self.create_user(username='superuser', is_superuser=True)
        site_settings = SiteSettings.objects.get_current()
        site_settings.admins.add(admin1)
        site_settings.admins.add(admin2)
        site_settings.admins.add(inactive_admin)
        site_settings.admins.add(superuser)

        self.assertEqual(admins_to_demote(tier1), [])
        self.assertEqual(admins_to_demote(tier2), [])
        self.assertEqual(admins_to_demote(tier3), [])
        self.assertEqual(admins_to_demote(tier4), [admin2])

    def test_videos_to_deactivate(self):
        tier1 = self.create_tier(slug='tier1', video_limit=None)
        tier2 = self.create_tier(slug='tier2', video_limit=100)
        tier3 = self.create_tier(slug='tier3', video_limit=2)
        tier4 = self.create_tier(slug='tier4', video_limit=1)
        video1 = self.create_video(name='video1')
        video2 = self.create_video(name='video2')

        self.assertEqual(videos_to_deactivate(tier1), [])
        self.assertEqual(videos_to_deactivate(tier2), [])
        self.assertEqual(videos_to_deactivate(tier3), [])
        self.assertEqual(videos_to_deactivate(tier4), [video1])

    @override_settings(MANAGERS=(('Manager', 'manager@localhost'),))
    def test_enforce_tier(self):
        """
        Tests that enforcing a tier demotes extra admins, deactivates extra
        videos, deactivates custom themes, and emails support to deactivate
        custom domains.

        """
        site_settings = SiteSettings.objects.get_current()
        admins = []
        for i in xrange(2):
            admin = self.create_user(username='admin{0}'.format(i))
            site_settings.admins.add(admin)
            admins.append(admin)

        videos = []
        for i in xrange(2):
            videos.append(self.create_video(name='video{0}'.format(i)))

        site = Site.objects.get_current()
        site.domain = 'custom.nu'
        site.save()

        theme = self.create_theme(default=True)

        # Case 1: Everything is allowed; nothing should change.
        self.assertEqual(set(site_settings.admins.all()), set(admins))
        self.assertEqual(set(Video.objects.filter(status=Video.ACTIVE)),
                         set(videos))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Theme.objects.get_current(), theme)
        self.assertEqual(Site.objects.get_current().domain, 'custom.nu')
        tier = self.create_tier(video_limit=None, admin_limit=None,
                                custom_domain=True, custom_themes=True)
        tier_info = self.create_tier_info(tier, site_name='test')
        enforce_tier(tier)
        self.assertEqual(set(site_settings.admins.all()), set(admins))
        self.assertEqual(set(Video.objects.filter(status=Video.ACTIVE)),
                         set(videos))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Theme.objects.get_current(), theme)
        self.assertEqual(Site.objects.get_current().domain, 'custom.nu')
        tier.delete()

        # Case 2: Nothing is allowed; everything should change.
        tier = self.create_tier(video_limit=1, admin_limit=1,
                                custom_domain=False, custom_themes=False)
        self.create_tier_info(tier, site_name='test')
        enforce_tier(tier)
        self.assertEqual(set(site_settings.admins.all()), set(admins[:1]))
        self.assertEqual(set(Video.objects.filter(status=Video.ACTIVE)),
                         set(videos[1:]))
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_current)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['manager@localhost'])
        self.assertEqual(Site.objects.get_current().domain,
                         'test.mirocommunity.org')


class FeedImportTestCase(BaseTestCase):
    def setUp(self):
        start = datetime.datetime.now() - datetime.timedelta(10)
        for i in xrange(10):
            video = self.create_video(name='video{0}'.format(i),
                                      status=Video.UNAPPROVED,
                                      site_id=settings.SITE_ID)
            video.when_submitted = start + datetime.timedelta(i)
            video.save()
        for i in xrange(10):
            video = self.create_video(name='video{0}-1'.format(i),
                                      site_id=settings.SITE_ID + 1)
            video.when_submitted = start + datetime.timedelta(i)
            video.save()

        self.active_set = Video.objects.filter(site=settings.SITE_ID
                                      ).order_by('when_submitted')

    def test_below_limit(self):
        """
        If approving the videos would leave us below the limit, then none of
        them should be filtered out.

        """
        tier = self.create_tier(video_limit=20)
        self.create_tier_info(tier)
        # The sender is technically usually a SourceImport instance, but it's
        # only used for its database.
        response = limit_import_approvals(self.active_set[0], self.active_set)
        self.assertTrue(response is None)

    def test_at_limit(self):
        """
        If approving the videos would leave us at the limit, then none of them
        should be filtered out.

        """
        tier = self.create_tier(video_limit=10)
        self.create_tier_info(tier)
        # The sender is technically usually a SourceImport instance, but it's
        # only used for its database.
        response = limit_import_approvals(self.active_set[0], self.active_set)
        self.assertTrue(response is None)

    def test_partially_over_limit(self):
        """
        If approving the videos would put us over the limit (but we aren't
        over or at the limit yet) we should approve the earliest-submitted
        videos.

        """
        tier = self.create_tier(video_limit=5)
        self.create_tier_info(tier)
        response = limit_import_approvals(self.active_set[0], self.active_set)
        self.assertEqual(response,
                    {'when_submitted__lt': self.active_set[5].when_submitted})

    def test_over_limit(self):
        """
        If we're already at the limit, none of the videos should be approved.

        """
        tier = self.create_tier(video_limit=0)
        self.create_tier_info(tier)
        response = limit_import_approvals(self.active_set[0], self.active_set)
        self.assertEqual(response, {'status': -1})


class SubmissionTestCase(BaseTestCase):
    def test_submission_approval(self):
        """
        Marks a video as inactive if no more videos can be approved.

        """
        tier = self.create_tier(video_limit=1)
        self.create_tier_info(tier)
        video = self.create_video(name='video')
        check_submission_approval(video)
        self.assertEqual(video.status, Video.ACTIVE)

        tier.video_limit = 0
        tier.save()
        check_submission_approval(video)
        self.assertEqual(video.status, Video.UNAPPROVED)
