import datetime

from django.contrib.sites.models import Site
from django.db import models
from localtv.managers import SiteRelatedManager
from paypal.standard.ipn.models import PayPalIPN

from mirocommunity_saas.utils.functional import cached_property
from mirocommunity_saas.utils.subscriptions import (get_subscriptions,
                                                    get_current_subscription)


class Tier(models.Model):
    #: Human-readable name.
    name = models.CharField(max_length=30)
    #: A unique slug.
    slug = models.SlugField(max_length=30, unique=True)

    #: Price (USD) for the tier.
    price = models.PositiveIntegerField(default=0)

    #: Maximum number of admins allowed by this tier (excluding superusers).
    #: If blank, unlimited admins can be chosen.
    admin_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Maximum number of videos for this tier. If blank, videos are unlimited.
    video_limit = models.PositiveIntegerField(blank=True, null=True)

    #: Whether custom css is permitted for this tier.
    custom_css = models.BooleanField(default=False)

    #: Whether custom themes are permitted for this tier.
    custom_themes = models.BooleanField(default=False)

    #: Whether a custom domain is allowed for this tier.
    custom_domain = models.BooleanField(default=False)

    #: Whether users at this level are allowed to run advertising.
    ads_allowed = models.BooleanField(default=False)

    def __unicode__(self):
        return u"{name}: {price}".format(name=self.name, price=self.price)


class SiteTierInfoManager(SiteRelatedManager):
    def _new_entry(self, site, using):
        # For now, we assume that the default tier should be a free tier. We
        # also assume that there is only one free tier.
        try:
            tier = Tier.objects.get(price=0)
        except Tier.DoesNotExist:
            raise self.model.DoesNotExist
        return self.db_manager(using).create(site=site, tier=tier,
                                         tier_changed=datetime.datetime.now())


class SiteTierInfo(models.Model):
    site = models.OneToOneField(Site, related_name='tier_info')

    #: The original subdomain for this site.
    site_name = models.CharField(max_length=30, blank=True)

    #: A list of tiers that the site admin can choose from.
    available_tiers = models.ManyToManyField(Tier,
                                             related_name='site_available_set')
    #: The current selected tier (based on the admin's choice).
    tier = models.ForeignKey(Tier)

    #: Date and time when the tier was last changed.
    tier_changed = models.DateTimeField()

    #: A list of payment objects for this site. This can be used, for example,
    #: to check the next due date for the subscription.
    ipn_set = models.ManyToManyField(PayPalIPN, blank=True)

    #: Whether or not the current tier should be enforced by making sure
    #: payments are coming in.
    enforce_payments = models.BooleanField(default=False)

    #: The datetime when the welcome email was sent to this site's owner.
    welcome_email_sent = models.DateTimeField(blank=True, null=True)

    #: The datetime when a "free trial ending" email was sent to the site's
    #: owner.
    free_trial_ending_sent = models.DateTimeField(blank=True, null=True)

    #: The last datetime when a warning was sent to the site's owner to let
    #: them know they're approaching their video limit.
    video_limit_warning_sent = models.DateTimeField(blank=True, null=True)

    #: The video count for the site the last time that the site's owner
    #: received a video limit warning.
    video_count_when_warned = models.PositiveIntegerField(blank=True, null=True)

    objects = SiteTierInfoManager()

    def __unicode__(self):
        return "Tier info for {0}".format(self.site.domain)

    @cached_property
    def subscriptions(self):
        return get_subscriptions(self.ipn_set.all())

    @cached_property
    def subscription(self):
        return get_current_subscription(self.subscriptions)

    @cached_property
    def had_subscription(self):
        """
        Returns ``True`` if the site has ever had a subscription and ``False``
        otherwise.

        """
        subscr_ipns = self.ipn_set.filter(flag=False,
                                          txn_type__in=('subscr_signup',
                                                        'subscr_modify'))
        return self.subscriptions or subscr_ipns.exists()
