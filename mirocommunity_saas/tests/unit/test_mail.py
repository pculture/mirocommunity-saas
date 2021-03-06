import datetime

from django.core import mail, management
from localtv.models import SiteSettings
import mock

from mirocommunity_saas.tests import BaseTestCase
from mirocommunity_saas.utils.mail import (send_free_trial_ending,
                                           send_video_limit_warning,
                                           send_welcome_email)


class MailTestCase(BaseTestCase):
    def setUp(self):
        super(MailTestCase, self).setUp()
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
        # Creating users sends welcome emails, so we need to explicitly reset
        # the mail outbox here.
        mail.outbox = []

    def test_free_trial_ending__sent(self):
        """
        If the free trial ending warning was already sent, we shouldn't send
        it again, even if all other conditions are met.

        """
        now = datetime.datetime.now()
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier, free_trial_ending_sent=now)

        trial_end = now + datetime.timedelta(2)
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'subscription',
                               free_trial_end=trial_end):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

    def test_free_trial_ending__early(self):
        """
        If we're before the warning period, the free trial ending warning
        shouldn't be sent, even if all other conditions are met.

        """
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)

        trial_end = datetime.datetime.now() + datetime.timedelta(7)
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'subscription',
                               free_trial_end=trial_end):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

    def test_free_trial_ending__late(self):
        """
        If we're past the warning period, the free trial ending warning
        shouldn't be sent, even if all other conditions are met.

        """
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)

        trial_end = datetime.datetime.now() - datetime.timedelta(2)
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'subscription',
                               free_trial_end=trial_end):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

    def test_free_trial_ending__no_free_trial(self):
        """
        If there is no active subscription, the ending warning shouldn't be
        sent.

        """
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)

        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'subscription', None):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 0)

    def test_free_trial_ending(self):
        """
        If all conditions are met, the site owner(s) should be emailed.

        """
        tier = self.create_tier()
        tier_info = self.create_tier_info(tier)

        trial_end = datetime.datetime.now() + datetime.timedelta(2)
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch.object(tier_info, 'subscription',
                               mock.Mock(free_trial_end=trial_end)):
            send_free_trial_ending()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(tier_info.free_trial_ending_sent)
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


class VideoLimitWarningTestCase(BaseTestCase):
    def setUp(self):
        self.create_user(email='superuser@localhost', is_superuser=True)
        BaseTestCase.setUp(self)

    def test_initial_warning(self):
        """
        If the site is getting close to its video limit and the warning hasn't
        been sent before, it should be sent.

        """
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier)
        for i in xrange(7):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertTrue(tier_info.video_limit_warning_sent is None)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(tier_info.video_count_when_warned, 7)
        self.assertTrue(tier_info.video_limit_warning_sent)

    def test_followup_warning(self):
        """
        If the site is getting closer to its video limit after an initial
        warning, an email should be sent.

        """
        last_sent = datetime.datetime.now() - datetime.timedelta(10)
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier,
                                          video_count_when_warned=7,
                                          video_limit_warning_sent=last_sent)
        for i in xrange(9):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(tier_info.video_count_when_warned, 9)
        self.assertGreater(tier_info.video_limit_warning_sent, last_sent)

    def test_followup_warning__decrease(self):
        """
        If the site has fewer videos than when it was last warned, no email
        should be sent, and the new count should be recorded.

        """
        last_sent = datetime.datetime.now() - datetime.timedelta(10)
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier,
                                          video_count_when_warned=8,
                                          video_limit_warning_sent=last_sent)
        for i in xrange(7):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(tier_info.video_count_when_warned, 7)
        self.assertEqual(tier_info.video_limit_warning_sent, last_sent)

    def test_followup_warning__small_increase(self):
        """
        If the number of videos has increased (but not significantly) since
        the last warning, no email should be sent, and the old count should be
        preserved.

        """
        last_sent = datetime.datetime.now() - datetime.timedelta(10)
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier,
                                          video_count_when_warned=7,
                                          video_limit_warning_sent=last_sent)
        for i in xrange(8):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(tier_info.video_count_when_warned, 7)
        self.assertEqual(tier_info.video_limit_warning_sent, last_sent)

    def test_below_ratio(self):
        """
        If the site is below the warning ratio, the email shouldn't be sent,
        and any previous video counts should be forgotten.

        """
        last_sent = datetime.datetime.now() - datetime.timedelta(10)
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier,
                                          video_count_when_warned=7,
                                          video_limit_warning_sent=last_sent)
        for i in xrange(3):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertEqual(tier_info.video_limit_warning_sent, last_sent)

    def test_no_limit(self):
        """
        If there is no video limit, then no email should be sent.

        """
        tier = self.create_tier(video_limit=None)
        tier_info = self.create_tier_info(tier)
        for i in xrange(7):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertTrue(tier_info.video_limit_warning_sent is None)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertTrue(tier_info.video_limit_warning_sent is None)

    def test_zero_limit(self):
        """
        If the limit is set to 0, then no email should be sent.

        """
        tier = self.create_tier(video_limit=0)
        tier_info = self.create_tier_info(tier)

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertTrue(tier_info.video_limit_warning_sent is None)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertTrue(tier_info.video_limit_warning_sent is None)

    def test_sent_recently(self):
        """
        If a warning email was sent recently, a new email shouldn't be sent.

        """
        last_sent = datetime.datetime.now()
        tier = self.create_tier(video_limit=10)
        tier_info = self.create_tier_info(tier,
                                          video_limit_warning_sent=last_sent)
        for i in xrange(7):
            self.create_video(name='video{0}'.format(i))

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        send_video_limit_warning()
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(tier_info.video_count_when_warned is None)
        self.assertEqual(tier_info.video_limit_warning_sent, last_sent)


class MailCommandTestCase(BaseTestCase):
    def test_free_trial_ending(self):
        """Tests that the command calls the send_free_trial_ending utility."""
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_free_trial_ending.send_free_trial_ending'
                        ) as send_free_trial_ending:
            management.call_command('send_free_trial_ending')
            send_free_trial_ending.assert_called_with()

    def test_video_limit_warning__command(self):
        """
        Tests that the command calls the send_video_limit_warning utility.

        """
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_video_limit_warning.send_video_limit_warning'
                        ) as send_video_limit_warning:
            management.call_command('send_video_limit_warning')
            send_video_limit_warning.assert_called_with()

    def test_welcome_email__command(self):
        """Tests that the command calls the send_welcome_email utility."""
        with mock.patch('mirocommunity_saas.management.commands.'
                        'send_welcome_email.send_welcome_email'
                        ) as send_welcome_email:
            management.call_command('send_welcome_email')
            send_welcome_email.assert_called_with()
