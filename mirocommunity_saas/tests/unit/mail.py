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

from __future__ import with_statement
import datetime

from django.core import mail, management
from localtv.models import SiteSettings, Video
import mock

from mirocommunity_saas.tests.base import BaseTestCase
from mirocommunity_saas.utils.mail import (send_free_trial_ending,
                                           send_video_limit_warning,
                                           send_welcome_email)


class MailTestCase(BaseTestCase):
    def setUp(self):
        site_settings = SiteSettings.objects.get_current()
        self.owner = self.create_user(username='superuser',
                                      email='superuser@localhost',
                                      is_superuser=True)
        self.user = self.create_user(username='user',
                                     email='user@localhost')
        self.inactive_owner = self.create_user(username='superuser2',
                                               email='superuser2@localhost',
                                               is_superuser=True,
                                               is_active=False)
        self.admin = self.create_user(username='admin',
                                      email='admin@localhost')
        site_settings.admins.add(self.admin)
        mail.outbox = []

    def test_free_trial_ending(self):
        now = datetime.datetime.now()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier, free_trial_ending_sent=now)

        # Shouldn't send if it's already been sent, even if all other
        # conditions are met.
        trial_end = now + datetime.timedelta(2)
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'get_free_trial_end',
                              return_value=trial_end):
           send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

        # Shouldn't send if it's not in the right timespan, even if all other
        # conditions are met.
        tier_info.free_trial_ending_sent = None
        tier_info.save()
        trial_end = now + datetime.timedelta(7)
        with mock.patch.object(tier_info, 'get_free_trial_end',
                              return_value=trial_end):
           send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

        # Shouldn't send if they aren't in a free trial, even if all other
        # conditions are met.
        with mock.patch.object(tier_info, 'get_free_trial_end',
                              return_value=None):
           send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

        # Should send if all conditions are met.
        trial_end = now + datetime.timedelta(2)
        with mock.patch.object(tier_info, 'get_free_trial_end',
                               return_value=trial_end):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(tier_info.free_trial_ending_sent)

        # Make sure that the right people were emailed.
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_welcome_email(self):
        now = datetime.datetime.now()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier, welcome_email_sent=now)

        # Shouldn't send if it's already been sent.
        self.assertEqual(len(mail.outbox), 0)
        send_welcome_email()
        self.assertEqual(len(mail.outbox), 0)

        tier_info.welcome_email_sent = None
        tier_info.save()
        send_welcome_email()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(tier_info.welcome_email_sent)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_video_limit_warning(self):
        now = datetime.datetime.now()
        tier = self.create_tier(video_limit=10)
        last_sent = now - datetime.timedelta(10)
        tier_info = self.create_tier_info(tier,
                                          video_limit_warning_sent=last_sent,
                                          video_count_when_warned=7)
        for i in xrange(9):
            self.create_video(name='video{0}'.format(i), update_index=False)

        # Should send if all conditions are met.
        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 1)
        self.assertGreater(tier_info.video_limit_warning_sent, last_sent)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertEqual(tier_info.video_count_when_warned, 9)
        mail.outbox = []

        # Shouldn't send if it's been sent recently, even if all other
        # conditions are met.
        tier_info.video_count_when_warned = 7
        tier_info.save()
        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)

        # Shouldn't send if there is no limit, even if all other conditions
        # are met.
        tier.video_limit = None
        tier.save()
        tier_info.video_limit_warning_sent = last_sent
        tier_info.save()
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)

        # Shouldn't send if the number of videos is too close to the last
        # count.
        for video in Video.objects.all()[7:]:
            video.delete()
        # Typo check/added clarity
        self.assertEqual(tier_info.video_count_when_warned,
                         Video.objects.count())
        tier.video_limit = 10
        tier.save()
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)

        # Should send if the number of videos is high enough and it's never
        # been sent before.
        tier_info.video_count_when_warned = None
        tier_info.save()
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 1)
        tier_info.video_limit_warning_sent = last_sent
        tier_info.save()
        mail.outbox = []

        # Shouldn't send if there aren't enough videos, even if all other
        # conditions are met.
        for video in Video.objects.all()[6:]:
            video.delete()
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)

    def test_free_trial_ending__command(self):
        """Tests that the command calls the send_free_trial_ending utility."""
        self.called = False
        def mark_called():
            self.called = True
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_free_trial_ending.send_free_trial_ending',
                        mark_called):
            management.call_command('send_free_trial_ending')
        self.assertTrue(self.called)

    def test_video_limit_warning__command(self):
        """
        Tests that the command calls the send_video_limit_warning utility.

        """
        self.called = False
        def mark_called():
            self.called = True
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_video_limit_warning.send_video_limit_warning',
                        mark_called):
            management.call_command('send_video_limit_warning')
        self.assertTrue(self.called)

    def test_welcome_email__command(self):
        """Tests that the command calls the send_welcome_email utility."""
        self.called = False
        def mark_called():
            self.called = True
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_welcome_email.send_welcome_email',
                        mark_called):
            management.call_command('send_welcome_email')
        self.assertTrue(self.called)
