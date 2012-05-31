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
from localtv.models import NewsletterSettings, SiteSettings, Video
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.forms import (EditSettingsForm, AuthorForm,
                                            VideoFormSet)
from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.tiers import (admins_to_demote,
                                            videos_to_deactivate,
                                            enforce_tier,
                                            limit_import_approvals,
                                            check_submission_approval)
from mirocommunity_saas.views import newsletter


class NewsletterTestCase(BaseTestCase):
    def setUp(self):
        """Make sure that a newsletter exists."""
        site_settings = SiteSettings.objects.get_current()
        NewsletterSettings.objects.create(site_settings=site_settings,
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


class EnforcementTestCase(BaseTestCase):
    """Tests that enforcing a tier DTRT."""
    def test_admins_to_demote(self):
        tier1 = self.create_tier(slug='tier1', admin_limit=None)
        tier2 = self.create_tier(slug='tier2', admin_limit=100)
        tier3 = self.create_tier(slug='tier3', admin_limit=1)
        admin1 = self.create_user(username='admin1', password='admin1')
        admin2 = self.create_user(username='admin2', password='admin2')
        site_settings = SiteSettings.objects.get_current()
        site_settings.admins.add(admin1)
        site_settings.admins.add(admin2)

        self.assertEqual(admins_to_demote(tier1), [])
        self.assertEqual(admins_to_demote(tier2), [])
        self.assertEqual(admins_to_demote(tier3), [admin2])

    def test_videos_to_deactivate(self):
        tier1 = self.create_tier(slug='tier1', video_limit=None)
        tier2 = self.create_tier(slug='tier2', video_limit=100)
        tier3 = self.create_tier(slug='tier3', video_limit=1)
        video1 = self.create_video(name='video1', update_index=False)
        video2 = self.create_video(name='video2', update_index=False)

        self.assertEqual(videos_to_deactivate(tier1), [])
        self.assertEqual(videos_to_deactivate(tier2), [])
        self.assertEqual(videos_to_deactivate(tier3), [video1])

    @override_settings(ADMINS=(('Admin1', 'admin@localhost')))
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
            videos.append(self.create_video(name='video{0}'.format(i),
                                            update_index=False))

        site = Site.objects.get_current()
        site.domain = 'custom.nu'
        site.save()

        theme = self.create_theme(default=True)

        # Case 1: Everything is allowed; nothing should change.
        self.assertEqual(set(site_settings.admins.all()), set(admins))
        self.assertEqual(set(Video.objects.filter(status=Video.ACTIVE)),
                         set(videos))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Theme.objects.get_default(), theme)
        self.assertEqual(Site.objects.get_current().domain, 'custom.nu')
        tier = self.create_tier(video_limit=None, admin_limit=None,
                                custom_domain=True, custom_themes=True)
        tier_info = self.create_tier_info(tier, site_name='test')
        enforce_tier(tier)
        self.assertEqual(set(site_settings.admins.all()), set(admins))
        self.assertEqual(set(Video.objects.filter(status=Video.ACTIVE)),
                         set(videos))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Theme.objects.get_default(), theme)
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
        self.assertRaises(Theme.DoesNotExist, Theme.objects.get_default)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Site.objects.get_current().domain,
                         'test.mirocommunity.org')


class FeedImportTestCase(BaseTestCase):
    def test_limit_import_approvals(self):
        """
        limit_import_approvals returns a dictionary of filters if not all
        of the videos given can be used.

        """
        tier = self.create_tier(video_limit=20)
        self.create_tier_info(tier)
        start = datetime.datetime.now() - datetime.timedelta(10)
        for i in xrange(10):
            video = self.create_video(name='video{0}'.format(i),
                                      update_index=False,
                                      status=Video.UNAPPROVED,
                                      site_id=settings.SITE_ID)
            video.when_submitted = start + datetime.timedelta(i)
            video.save()
        for i in xrange(10):
            video = self.create_video(name='video{0}-1'.format(i),
                                      update_index=False,
                                      site_id=settings.SITE_ID + 1)
            video.when_submitted = start + datetime.timedelta(i)
            video.save()

        active_set = Video.objects.filter(site=settings.SITE_ID
                                 ).order_by('when_submitted')
        # The sender is technically usually a SourceImport instance, but it's
        # only used for its database.
        response = limit_import_approvals(active_set[0], active_set)
        self.assertTrue(response is None)

        tier.video_limit = 10
        tier.save()
        response = limit_import_approvals(active_set[0], active_set)
        self.assertTrue(response is None)

        tier.video_limit = 5
        tier.save()
        response = limit_import_approvals(active_set[0], active_set)
        self.assertEqual(response,
                         {'when_submitted__lt': active_set[5].when_submitted})

        tier.video_limit = 0
        tier.save()
        response = limit_import_approvals(active_set[0], active_set)
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
