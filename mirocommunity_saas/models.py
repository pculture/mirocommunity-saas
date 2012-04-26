import base64
import datetime
import os

from django.db import models

from localtv.models import SingletonManager, SiteSettings

from mirocommunity_saas import settings as lsettings
from mirocommunity_saas import tiers

class TierInfo(models.Model):
    payment_due_date = models.DateTimeField(null=True, blank=True)
    free_trial_available = models.BooleanField(default=True)
    free_trial_started_on = models.DateTimeField(null=True, blank=True)
    in_free_trial = models.BooleanField(default=False)
    payment_secret = models.CharField(max_length=255, default='',blank=True) # This is part of payment URLs.
    current_paypal_profile_id = models.CharField(max_length=255, default='',blank=True) # NOTE: When using this, fill it if it seems blank.
    video_allotment_warning_sent = models.BooleanField(default=False)
    free_trial_warning_sent = models.BooleanField(default=False)
    already_sent_welcome_email = models.BooleanField(default=False)
    inactive_site_warning_sent = models.BooleanField(default=False)
    user_has_successfully_performed_a_paypal_transaction = models.BooleanField(default=False)
    already_sent_tiers_compliance_email = models.BooleanField(default=False)
    tier_name = models.CharField(max_length=255, default='basic', blank=False,
                                 choices=tiers.CHOICES)
    fully_confirmed_tier_name = models.CharField(max_length=255, default='', blank=True)
    should_send_welcome_email_on_paypal_event = models.BooleanField(default=False)
    waiting_on_payment_until = models.DateTimeField(null=True, blank=True)
    site_settings = models.OneToOneField(SiteSettings,
                                         db_column='sitelocation_id')
    objects = SingletonManager()

    class Meta:
        db_table = 'localtv_tierinfo'

    @staticmethod
    def enforce_tiers(override_setting=None, using='default'):
        '''If the admin has set LOCALTV_DISABLE_TIERS_ENFORCEMENT to a True value,
        then this function returns False. Otherwise, it returns True.'''
        if override_setting is None:
            disabled = lsettings.DISABLE_TIERS_ENFORCEMENT
        else:
            disabled = override_setting

        if disabled:
            # Well, hmm. If the site admin participated in a PayPal transaction, then we
            # actually will enforce the tiers.
            #
            # Go figure.
            tierdata = TierInfo.objects.db_manager(using).get_current()
            if tierdata.user_has_successfully_performed_a_paypal_transaction:
                return True # enforce it.

        # Generally, we just negate the "disabled" boolean.
        return not disabled

    def get_fully_confirmed_tier(self):
        # If we are in a transitional state, then we would have stored
        # the last fully confirmed tier name in an unusual column.
        if self.fully_confirmed_tier_name:
            return tiers.Tier(self.fully_confirmed_tier_name)
        return None

    def get_payment_secret(self):
        '''The secret had better be non-empty. So we make it non-empty right here.'''
        if not self.payment_secret:
            self.payment_secret = base64.b64encode(os.urandom(16))
            self.save()
        return self.payment_secret

    def site_is_subsidized(self):
        return (self.current_paypal_profile_id == 'subsidized')

    def set_to_subsidized(self):
        if self.current_paypal_profile_id:
            raise AssertionError, (
                "Bailing out: " +
                "the site already has a payment profile configured: %s" %
                                   self.current_paypal_profile_id)
        self.current_paypal_profile_id = 'subsidized'

    def time_until_free_trial_expires(self, now = None):
        if not self.in_free_trial:
            return None
        if not self.payment_due_date:
            return None

        if now is None:
            now = datetime.datetime.utcnow()
        return (self.payment_due_date - now)

    def use_zendesk(self):
        '''If the site is configured to, we can send notifications of
        tiers-related changes to ZenDesk, the customer support ticketing
        system used by PCF.

        A non-PCF deployment of localtv would not want to set the
        LOCALTV_USE_ZENDESK setting. Then this method will return False,
        and the parts of the tiers system that check it will avoid
        making calls out to ZenDesk.'''
        return lsettings.USE_ZENDESK

    def get_tier(self):
        return tiers.Tier(self.tier_name, self.site_settings)

    def add_queued_mail(self, data):
        if not hasattr(self, '_queued_mail'):
            self._queued_mail = []
        self._queued_mail.append(data)

    def get_queued_mail_destructively(self):
        ret = getattr(self, '_queued_mail', [])
        self._queued_mail = []
        return ret

    def display_custom_css(self):
        '''This function checks the site tier, and if permitted, returns the
        custom CSS the admin has set.

        If that is not permitted, it returns the empty unicode string.'''
        if (not self.enforce_tiers() or
            self.get_tier().permit_custom_css()):
            return True
        else:
            return False

    def enforce_permit_custom_template(self):
        if not self.enforce_tiers():
            return True
        return self.get_tier().permit_custom_template()

### register pre-save handler for Tiers and payment due dates
models.signals.pre_save.connect(tiers.pre_save_set_payment_due_date,
                                sender=TierInfo)
models.signals.pre_save.connect(tiers.pre_save_adjust_resource_usage,
                                sender=TierInfo)
models.signals.post_save.connect(tiers.post_save_send_queued_mail,
                                 sender=TierInfo)

from localtv.tasks import pre_mark_as_active
pre_mark_as_active.connect(tiers.pre_mark_as_active)
