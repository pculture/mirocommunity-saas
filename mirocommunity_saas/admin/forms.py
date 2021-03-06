import datetime
import urllib

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse, reverse_lazy
from django.forms.models import modelformset_factory
from django.template.defaultfilters import pluralize
from localtv.admin.forms import (EditSettingsForm as _EditSettingsForm,
                                 AuthorForm as _AuthorForm,
                                 BulkEditVideoFormSet as _BulkEditVideoFormSet,
                                 BulkEditVideoForm)
from localtv.models import Video
from paypal.standard.conf import (POSTBACK_ENDPOINT,
                                  SANDBOX_POSTBACK_ENDPOINT,
                                  RECEIVER_EMAIL,
                                  TEST as PAYPAL_TEST)
from paypal.standard.forms import PayPalPaymentsForm

from mirocommunity_saas.models import SiteTierInfo, Tier
from mirocommunity_saas.utils.mail import send_welcome_email
from mirocommunity_saas.utils.tiers import (make_tier_change_token,
                                            check_tier_change_token)


class EditSettingsForm(_EditSettingsForm):
    def __init__(self, *args, **kwargs):
        _EditSettingsForm.__init__(self, *args, **kwargs)
        self.tier = SiteTierInfo.objects.get_current().tier
        if not self.tier.custom_css:
            # Uh-oh: custom CSS is not permitted!
            #
            # To handle only letting certain paid users edit CSS,
            # we do two things.
            #
            # 1. Cosmetically, we set the CSS editing box's CSS class
            # to be 'hidden'. (We have some CSS that makes it not show
            # up.) SB: Not sure why we don't just remove the field...
            css_field = self.fields['css']
            css_field.label += ' (upgrade to enable this form field)'
            css_field.widget.attrs['readonly'] = True
            #
            # 2. In validation, we make sure that changing the CSS is
            # rejected as invalid if the site does not have permission
            # to do that.

    def clean_css(self):
        css = self.cleaned_data.get('css')
        # Does the current tier permit custom CSS? If so, return the data the
        # user submitted.
        if self.tier.custom_css:
            return css # no questions asked

        # We permit the value if it's the same as self.instance has:
        # SB: Leaving this for now, for backwards-compatibility, but again:
        # if css isn't allowed, we should probably not be storing it. This is
        # probably only here because we didn't remove the field on __init__.
        if self.instance.css == css:
            return css

        # Otherwise, reject the change.
        self.data['css'] = self.instance.css
        raise ValidationError(
            "To edit CSS for your site, you have to upgrade.")

class AuthorForm(_AuthorForm):
    def __init__(self, *args, **kwargs):
        _AuthorForm.__init__(self, *args, **kwargs)
        ## Add a note to the 'role' help text indicating how many admins
        ## are permitted with this kind of account.
        self.tier = SiteTierInfo.objects.get_current().tier
        if self.tier.admin_limit is not None:
            # For backwards-compatibility, pretend the site owner (a
            # superuser) counts toward the limit.
            limit = self.tier.admin_limit + 1
            message = ('With a {tier_name}, you may have {limit} '
                       'administrator{s}.').format(tier_name=self.tier.name,
                                                   limit=limit,
                                                   s=pluralize(limit))
            self.fields['role'].help_text = message

    def clean_role(self):
        role = self.cleaned_data['role']

        # Nothing to check if they aren't being set to admin.
        if role != 'admin':
            return role

        # Nothing to check if there is no admin limit.
        if self.tier.admin_limit is None:
            return role

        # Nothing to check if the user is already an admin.
        if 'role' not in self.changed_data:
            return role

        # And finally, we're good if there's room for another admin.
        admin_count = self.site_settings.admins.exclude(is_superuser=True
                                              ).exclude(is_active=False
                                              ).count()
        if (admin_count + 1) <= self.tier.admin_limit:
            return role

        # For backwards-compatibility, pretend the site owner (a
        # superuser) counts toward the limit.
        limit = self.tier.admin_limit + 1
        raise ValidationError("You already have {limit} admin{s} in your "
                              "site. Upgrade to have access to more.".format(
                                        limit=limit, s=pluralize(limit)))


AuthorFormSet = modelformset_factory(User,
                                     form=AuthorForm,
                                     can_delete=True,
                                     extra=0)

class BulkEditVideoFormSet(_BulkEditVideoFormSet):
    def clean(self):
        tier = SiteTierInfo.objects.get_current().tier
        self.approval_count = 0
        _BulkEditVideoFormSet.clean(self)
        if tier.video_limit is not None:
            video_count = Video.objects.filter(status=Video.ACTIVE,
                                               site=settings.SITE_ID
                                      ).count()
            remaining = tier.video_limit - video_count
            if remaining < 0:
                raise ValidationError('You already have {0} videos over your '
                                      'limit ({1}). Upgrade to approve '
                                      'more.'.format(-1 * remaining,
                                                     tier.video_limit))
            elif self.approval_count > remaining:
                raise ValidationError('You can only approve {0} videos, '
                                      'but tried to approve {1} instead. '
                                      'Upgrade to approve more.'.format(
                                      remaining, self.approval_count))

    def action_approve(self, form):
        if form.instance.status != Video.ACTIVE:
            self.approval_count += 1
        _BulkEditVideoFormSet.action_approve(self, form)

    def action_feature(self, form):
        if form.instance.status != Video.ACTIVE:
            self.approval_count += 1
        _BulkEditVideoFormSet.action_feature(self, form)

VideoFormSet = modelformset_factory(
    Video,
    form=BulkEditVideoForm,
    formset=BulkEditVideoFormSet,
    can_delete=True,
    extra=1)


class DowngradeConfirmationForm(forms.Form):
    """
    This form is designed to get confirmation of a downgrade.

    """
    action = reverse_lazy('localtv_admin_tier_confirm')
    method = "get"

    tier = forms.SlugField(widget=forms.HiddenInput)

    def __init__(self, tier, *args, **kwargs):
        super(DowngradeConfirmationForm, self).__init__(*args, **kwargs)
        self.tier = tier
        self.initial['tier'] = tier.slug


class TierChangeForm(forms.Form):
    """
    This form can be used to change a tier without going through paypal.

    """
    action = reverse_lazy('localtv_admin_tier_change')
    method = "post"

    tier = forms.models.ModelChoiceField(queryset=Tier.objects.all(),
                                         widget=forms.HiddenInput,
                                         to_field_name='slug')
    token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super(TierChangeForm, self).__init__(*args, **kwargs)
        self.tier_info = SiteTierInfo.objects.get_current()
        self.fields['tier'].queryset = self.tier_info.available_tiers.all()
        if 'tier' in self.initial:
            self.initial['token'] = make_tier_change_token(
                                                         self.initial['tier'])

    def clean_tier(self):
        tier = self.cleaned_data['tier']
        if tier == self.tier_info.tier:
            raise ValidationError("Selected tier is the current tier.")
        return tier

    def clean(self):
        if self.errors:
            # If there are already errors, we can't continue with this part
            # of the validation.
            return self.cleaned_data
        token = self.cleaned_data['token']
        tier = self.cleaned_data['tier']
        if not check_tier_change_token(tier, token):
            raise ValidationError("Invalid tier change token.")
        return self.cleaned_data

    def save(self):
        self.tier_info.tier = self.cleaned_data['tier']
        self.tier_info.tier_changed = datetime.datetime.now()
        self.tier_info.save()
        # Run send_welcome_email to get it out of the way if they're
        # arriving after paying on paypal. It won't do anything if it was
        # already sent, and the overhead is minimal.
        send_welcome_email()


class PayPalCancellationForm(forms.Form):
    action = (SANDBOX_POSTBACK_ENDPOINT if PAYPAL_TEST else POSTBACK_ENDPOINT)
    method = "get"

    cmd = forms.CharField(widget=forms.HiddenInput)
    alias = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super(PayPalCancellationForm, self).__init__(*args, **kwargs)
        self.initial.update({
            'cmd': '_subscr-find',
            'alias': RECEIVER_EMAIL,
        })


class PayPalSubscriptionForm(PayPalPaymentsForm):
    action = (SANDBOX_POSTBACK_ENDPOINT if PAYPAL_TEST else POSTBACK_ENDPOINT)
    method = "post"
    return_url = 'localtv_admin_tier_change'
    cancel_return = 'localtv_admin_tier'
    notify_url = 'paypal-ipn'

    def __init__(self, tier, *args, **kwargs):
        super(PayPalSubscriptionForm, self).__init__(*args, **kwargs)
        self.tier = tier
        site = Site.objects.get_current()
        tier_info = SiteTierInfo.objects.get_current()
        # Downgrades are delayed until the subscription expires, so we should
        # only use the return_url (which would immediately change the tier) if
        # this is an upgrade.
        cancel_return = 'http://{domain}{url}'.format(
                                    domain=site.domain,
                                    url=reverse(self.cancel_return))
        if tier.price < tier_info.tier.price:
            return_url = cancel_return
        else:
            return_params = TierChangeForm(initial={'tier': tier}).initial
            return_url = 'http://{domain}{url}?{query}'.format(
                                    domain=site.domain,
                                    url=reverse(self.return_url),
                                    query=urllib.urlencode(return_params))
        # This initial data says: A subscription for the ``RECEIVER_EMAIL``
        # business with the tier's price, paid every thirty days. The
        # subscription should recur indefinitely and payments should be
        # retried if they fail. cancel_return is where they will be sent if
        # they decide not to pay, or if this is a downgrade (the root of their
        # site). return_url is where they will be sent if they decide to do
        # the change and it's an upgrade (the TierChangeView). notify_url is
        # where ipn notifications will be sent. For more information, see
        # the IPN documentation:
        # https://cms.paypal.com/cms_content/US/en_US/files/developer/PP_WebsitePaymentsStandard_IntegrationGuide.pdf
        self.initial = {
            'cmd': '_xclick-subscriptions',
            'business': RECEIVER_EMAIL,
            # TODO: Should probably reference a url on the current site.
            'image_url': "http://www.mirocommunity.org/images/mc_logo.png",
            'a3': unicode(self.tier.price),
            'p3': '30',
            't3': 'D',
            'src': '1',
            'sra': '1',
            'cancel_return': cancel_return,
            'notify_url': 'http://{domain}{url}'.format(
                                   domain=site.domain,
                                   url=reverse(self.notify_url)),
            'return_url': return_url,
            'item_name': ("Miro Community subscription ({name} on "
                          "{domain})").format(
                                   name=tier.name,
                                   domain=site.domain),
        }
        if not tier_info.had_subscription:
            # If they've never had a subscription before, we add a thirty-day
            # free trial.
            self.initial.update({
                'a1': '0',
                'p1': '30',
                't1': 'D'
            })
        elif tier_info.subscription is not None:
            if (not tier_info.subscription.is_cancelled and
                tier.price < tier_info.tier.price):
                # If the current subscription is uncancelled and this is
                # a downgrade, do this as a subscription modification.
                self.initial['modify'] = '2'
            # Any time they are currently subscribed, delay payment
            # until the end of their current subscription by giving a
            # "free trial" until then.
            next_due_date = tier_info.subscription.next_due_date
            self.initial.update({
                'a1': '0',
                'p1': str((next_due_date - datetime.datetime.now()).days),
                't1': 'D',
            })
